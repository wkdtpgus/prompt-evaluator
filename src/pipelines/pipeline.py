"""평가 파이프라인

데이터 로드 → LLM 호출 → 평가 실행 → 결과 집계

두 가지 모드:
1. 로컬 모드: run_pipeline() - 빠른 개발/테스트
2. LangSmith 모드: run_langsmith_experiment() - 정식 평가, 버전 비교
"""

import json
import time
from datetime import datetime
from typing import Any, Literal

from dotenv import load_dotenv
from langsmith import traceable
from langsmith.evaluation import EvaluationResult, evaluate

# Langfuse imports (lazy import for optional dependency)
try:
    from langfuse import Evaluation
    from utils.langfuse_client import (
        get_langfuse_client,
        get_langfuse_handler,
        flush as langfuse_flush,
    )

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

from src.evaluators.rule_based import run_rule_evaluators
from src.loaders import load_evaluation_set
from utils.dataset_sync import upload_dataset, get_dataset
from src.evaluators.adapters import (
    create_langfuse_evaluator,
    create_langsmith_evaluator,
)
from utils.prompt_sync import get_prompt
from utils.models import execution_llm

load_dotenv()

RunMode = Literal["quick", "full"]
Backend = Literal["langsmith", "langfuse"]


@traceable(name="prompt_execution")
def execute_prompt(
    template: str,
    inputs: dict,
    callbacks: list | None = None,
) -> str:
    """프롬프트를 LLM에 실행하고 응답 반환.

    Args:
        template: 프롬프트 템플릿 (플레이스홀더 포함)
        inputs: 템플릿에 채울 입력 데이터
        callbacks: LangChain 콜백 핸들러 목록 (Langfuse 트레이싱 등)

    Returns:
        LLM 응답 텍스트
    """
    # 템플릿에 입력 값 채우기
    # inputs의 모든 키를 플레이스홀더로 사용 (도메인 독립적)
    format_args = {}
    for key, value in inputs.items():
        if isinstance(value, (dict, list)):
            format_args[key] = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            format_args[key] = value

    # Langfuse 스타일 {{var}} → Python .format() 스타일 {var} 변환
    # 입력 키에 해당하는 플레이스홀더만 변환 (JSON 예시의 {{{{...}}}} 보호)
    converted = template
    for key in format_args:
        converted = converted.replace("{{" + key + "}}", "{" + key + "}")

    prompt = converted.format(**format_args)

    invoke_kwargs = {}
    if callbacks:
        invoke_kwargs["config"] = {"callbacks": callbacks}

    response = execution_llm.invoke(prompt, **invoke_kwargs)

    return response.content


@traceable(name="run_evaluation")
def run_evaluation(
    output: str,
    expected: dict,
    inputs: dict,
    mode: RunMode = "quick",
    eval_config: dict | None = None,
) -> dict[str, Any]:
    """출력에 대한 평가 실행.

    Args:
        output: LLM 출력
        expected: 기대 결과 (keywords, forbidden, reference)
        inputs: 원본 입력
        mode: 실행 모드 (quick/full)
        eval_config: 평가 설정

    Returns:
        {
            "rule_based": {...},
            "overall_score": float,
            "passed": bool
        }
    """
    # ============================================================
    # 1. Sanity Checks (pass/fail만, 점수에 미반영)
    # ============================================================
    rule_checks = ["keyword_inclusion", "forbidden_word_check"]
    rule_results = run_rule_evaluators(output, expected, rule_checks, eval_config)

    sanity_all_passed = all(r["passed"] for r in rule_results.values())
    sanity_checks = {
        "checks": rule_results,
        "all_passed": sanity_all_passed,
    }

    # ============================================================
    # 2. 점수 (로컬 파이프라인에서는 scoring 없음, 어댑터 경로에서 LLM Judge 실행)
    # ============================================================
    overall_score = None
    passed = sanity_all_passed
    fail_reason = None if sanity_all_passed else "sanity_check_failed"

    return {
        "sanity_checks": sanity_checks,
        "overall_score": overall_score,
        "passed": passed,
        "fail_reason": fail_reason,
    }


@traceable(name="evaluate_case")
def evaluate_single_case(
    template: str,
    test_case: dict,
    expected: dict,
    mode: RunMode = "quick",
    eval_config: dict | None = None,
) -> dict[str, Any]:
    """단일 테스트 케이스 평가.

    Args:
        template: 프롬프트 템플릿
        test_case: 테스트 케이스 데이터
        expected: 기대 결과
        mode: 실행 모드
        eval_config: 평가 설정

    Returns:
        {
            "case_id": str,
            "output": str,
            "evaluation": dict,
            "duration_ms": int
        }
    """
    start = time.time()

    case_id = test_case.get("id", "unknown")
    inputs = test_case.get("inputs", {})

    # LLM 실행
    output = execute_prompt(template, inputs)

    # 평가 실행
    evaluation = run_evaluation(output, expected, inputs, mode, eval_config)

    duration_ms = int((time.time() - start) * 1000)

    return {
        "case_id": case_id,
        "description": test_case.get("description", ""),
        "output": output,
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }


def run_pipeline(
    prompt_name: str,
    mode: RunMode = "quick",
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    """전체 평가 파이프라인 실행.

    Args:
        prompt_name: 평가 세트 이름 (예: "prep_analyzer")
        mode: 실행 모드 (quick/standard/full)
        case_ids: 특정 케이스만 실행 (None이면 전체)

    Returns:
        {
            "prompt_name": str,
            "mode": str,
            "timestamp": str,
            "cases": list[dict],
            "summary": {
                "total": int,
                "passed": int,
                "failed": int,
                "pass_rate": float,
                "avg_score": float
            }
        }
    """
    # 데이터 로드
    data = load_evaluation_set(prompt_name)
    template = data["template"]
    test_cases = data["test_cases"]
    expected_all = data["expected"]
    eval_config = data["eval_config"]

    # 케이스 필터링
    if case_ids:
        test_cases = [tc for tc in test_cases if tc.get("id") in case_ids]

    results = []
    for test_case in test_cases:
        case_id = test_case.get("id", "unknown")
        expected = expected_all.get(case_id, {})

        print(f"  [{case_id}] {test_case.get('description', '')[:40]}...", end=" ")

        result = evaluate_single_case(
            template=template,
            test_case=test_case,
            expected=expected,
            mode=mode,
            eval_config=eval_config,
        )

        status = "✓" if result["evaluation"]["passed"] else "✗"
        score = result["evaluation"]["overall_score"]
        score_str = f"{score:.2f}" if score is not None else "-"
        print(f"{status} ({score_str}) [{result['duration_ms']}ms]")

        results.append(result)

    # 요약 계산
    total = len(results)
    passed = sum(1 for r in results if r["evaluation"]["passed"])
    scores = [
        r["evaluation"]["overall_score"]
        for r in results
        if r["evaluation"]["overall_score"] is not None
    ]

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else None,
    }

    return {
        "prompt_name": prompt_name,
        "mode": mode,
        "model": execution_llm.model_name,
        "timestamp": datetime.now().isoformat(),
        "cases": results,
        "summary": summary,
    }


# ============================================================
# LangSmith Experiment 모드
# ============================================================


def run_langsmith_experiment(
    prompt_name: str,
    mode: RunMode = "standard",
    experiment_prefix: str | None = None,
    prompt_version: str | None = None,
) -> str:
    """LangSmith Experiment로 평가 실행.

    Dataset에 대해 evaluate()를 실행하고 결과를 LangSmith에 기록.
    버전 비교, 회귀 테스트에 활용.

    Args:
        prompt_name: 평가 세트 이름
        mode: 실행 모드 (quick/standard/full)
        experiment_prefix: 실험 이름 접두사
        prompt_version: LangSmith 프롬프트 버전 태그 (None이면 로컬 파일 사용)

    Returns:
        실험 URL
    """
    # 1. 데이터셋 업로드 (없으면 생성)
    ds_result = upload_dataset(prompt_name, backend="langsmith")
    dataset_name = ds_result.get("langsmith_name", f"prompt-eval-{prompt_name}")

    # 2. 프롬프트 템플릿 로드
    data = load_evaluation_set(prompt_name)
    expected_all = data["expected"]
    eval_config = data["eval_config"]

    # 프롬프트 소스 결정: LangSmith 버전 or 로컬 파일
    if prompt_version:
        print(f"  LangSmith 프롬프트 버전: {prompt_version}")
        template = get_prompt(
            prompt_name, backend="langsmith", version_tag=prompt_version
        )
    else:
        template = data["template"]

    # 3. Target 함수 정의 (LLM 호출)
    def target(inputs: dict) -> dict:
        """LangSmith evaluate()에서 호출할 타겟 함수."""
        output = execute_prompt(template, inputs)
        return {"output": output}

    # 4. 평가자 함수들 정의
    def keyword_evaluator(run, example) -> EvaluationResult:
        """키워드 포함 평가."""
        output = run.outputs.get("output", "")
        # case_id는 metadata에 저장됨
        case_id = example.metadata.get("case_id", "") if example.metadata else ""
        expected = expected_all.get(case_id, {})
        keywords = expected.get("keywords", [])

        if not keywords:
            return EvaluationResult(key="keyword_inclusion", score=1.0)

        found = sum(1 for k in keywords if k.lower() in output.lower())
        score = found / len(keywords)

        return EvaluationResult(
            key="keyword_inclusion",
            score=score,
            comment=f"Found {found}/{len(keywords)} keywords",
        )

    def forbidden_evaluator(run, example) -> EvaluationResult:
        """금지어 검사."""
        output = run.outputs.get("output", "")
        # case_id는 metadata에 저장됨
        case_id = example.metadata.get("case_id", "") if example.metadata else ""
        expected = expected_all.get(case_id, {})
        forbidden = expected.get("forbidden", [])

        if not forbidden:
            return EvaluationResult(key="forbidden_word_check", score=1.0)

        violations = [w for w in forbidden if w.lower() in output.lower()]
        score = 1.0 if not violations else 0.0

        return EvaluationResult(
            key="forbidden_word_check",
            score=score,
            comment=f"Violations: {violations}" if violations else "No violations",
        )

    # 5. 모드에 따른 평가자 선택
    # Note: rule-based 평가자는 sanity check용으로만 사용 (LangSmith에서는 점수로 기록되지만
    # 실제 pass/fail 판정은 llm_judge 기준으로 함)
    evaluators = [keyword_evaluator, forbidden_evaluator]

    # 6. LLM Judge 평가자 추가 (full 모드 또는 eval_config에 설정된 경우)
    llm_judge_config = None
    for evaluator in eval_config.get("evaluators", []):
        if evaluator.get("type") == "llm_judge":
            llm_judge_config = evaluator
            break

    if llm_judge_config and llm_judge_config.get("enabled", True):
        criteria = llm_judge_config.get("criteria", [])
        if mode == "full" or criteria:
            print(f"  LLM Judge 평가자 추가: {criteria}")
            for criterion in criteria:
                evaluators.append(create_langsmith_evaluator(criterion, template))

    # 7. 실험 이름 설정
    if experiment_prefix is None:
        experiment_prefix = f"{prompt_name}-{mode}"

    # 8. evaluate() 실행
    print(f"\nLangSmith Experiment 시작: {experiment_prefix}")
    print(f"  Dataset: {dataset_name}")
    print(f"  Mode: {mode}")
    print(f"  Model: {execution_llm.model_name}")
    print()

    results = evaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
    )

    # 9. 결과 URL 반환
    experiment_url = "https://smith.langchain.com/datasets"
    print("\n✅ Experiment 완료!")
    print(f"  결과 확인: {experiment_url}")

    return experiment_url


# ============================================================
# Langfuse Experiment 모드
# ============================================================


def _run_langfuse_experiment(
    prompt_name: str,
    mode: RunMode = "full",
    experiment_prefix: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    """Langfuse 기반 실험 실행.

    Langfuse SDK의 내장 run_experiment 사용.
    데이터셋 순회 → LLM 호출 → 평가 실행 (자동 트레이싱)

    Args:
        prompt_name: 평가 세트 이름
        mode: 실행 모드 (quick/full)
        experiment_prefix: 실험 이름 접두사
        prompt_version: Langfuse 프롬프트 버전 (None이면 로컬 파일 사용)

    Returns:
        실험 결과 딕셔너리
    """
    if not LANGFUSE_AVAILABLE:
        raise ImportError(
            "Langfuse SDK가 설치되지 않았습니다. 'poetry add langfuse'로 설치하세요."
        )

    langfuse = get_langfuse_client()

    # 1. 프롬프트 템플릿 로드
    data = load_evaluation_set(prompt_name)
    expected_all = data["expected"]
    eval_config = data["eval_config"]

    # 프롬프트 소스 결정: Langfuse 버전 or 로컬 파일
    if prompt_version:
        print(f"  Langfuse 프롬프트 버전: {prompt_version}")
        prompt_obj = get_prompt(
            prompt_name,
            backend="langfuse",
            version=int(prompt_version.lstrip("v").split(".")[0]),
        )
        template = prompt_obj.compile()
    else:
        template = data["template"]

    # 2. 데이터셋 로드
    try:
        dataset = get_dataset(prompt_name)
    except Exception as e:
        print(f"데이터셋 로드 실패: {e}")
        print("Langfuse에 데이터셋이 없습니다. 먼저 업로드하세요.")
        raise

    # 3. 실험 이름 설정
    if experiment_prefix is None:
        experiment_prefix = f"{prompt_name}-{mode}"
    experiment_name = f"{experiment_prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"\nLangfuse Experiment 시작: {experiment_name}")
    print(f"  Dataset: {prompt_name}")
    print(f"  Mode: {mode}")
    print(f"  Model: {execution_llm.model_name}")
    print(f"  Items: {len(dataset.items)}")
    print()

    # 4. LLM Judge 설정 확인
    llm_judge_config = None
    for evaluator in eval_config.get("evaluators", []):
        if evaluator.get("type") == "llm_judge":
            llm_judge_config = evaluator
            break

    use_llm_judge = (
        mode == "full" and llm_judge_config and llm_judge_config.get("enabled", True)
    )
    criteria = llm_judge_config.get("criteria", []) if llm_judge_config else []

    if use_llm_judge:
        print(f"  LLM Judge 평가자: {criteria}")

    # 5. Task 함수 정의 (LLM 호출 + Langfuse 트레이싱)
    def task(item):
        """Langfuse 실험의 타겟 함수 - 각 데이터셋 아이템에 대해 실행됨."""
        handler = get_langfuse_handler()
        output = execute_prompt(template, item.input, callbacks=[handler])
        return {"output": output}

    # 6. Evaluator 함수들 정의
    def keyword_evaluator(*, output, expected_output, input, metadata, **kwargs):
        """키워드 포함 평가."""
        text = output.get("output", "") if isinstance(output, dict) else str(output)
        case_id = metadata.get("case_id", "") if metadata else ""
        expected = expected_all.get(case_id, {})
        keywords = expected.get("keywords", [])

        if not keywords:
            return Evaluation(
                name="keyword_inclusion",
                value=1.0,
                comment="No keywords to check",
            )

        found = sum(1 for k in keywords if k.lower() in text.lower())
        score = found / len(keywords)
        return Evaluation(
            name="keyword_inclusion",
            value=score,
            comment=f"Found {found}/{len(keywords)} keywords",
        )

    def forbidden_evaluator(*, output, expected_output, input, metadata, **kwargs):
        """금지어 검사."""
        text = output.get("output", "") if isinstance(output, dict) else str(output)
        case_id = metadata.get("case_id", "") if metadata else ""
        expected = expected_all.get(case_id, {})
        forbidden = expected.get("forbidden", [])

        if not forbidden:
            return Evaluation(
                name="forbidden_word_check",
                value=1.0,
                comment="No forbidden words to check",
            )

        violations = [w for w in forbidden if w.lower() in text.lower()]
        score = 1.0 if not violations else 0.0
        return Evaluation(
            name="forbidden_word_check",
            value=score,
            comment=f"Violations: {violations}" if violations else "No violations",
        )

    # 7. 평가자 목록 구성
    evaluators = [keyword_evaluator, forbidden_evaluator]

    # LLM Judge 평가자 추가 (full 모드)
    if use_llm_judge:
        for criterion in criteria:
            evaluators.append(create_langfuse_evaluator(criterion))

    # 8. Langfuse 내장 run_experiment 실행
    print("  실험 실행 중...")
    experiment_result = langfuse.run_experiment(
        name=experiment_name,
        data=dataset.items,
        task=task,
        evaluators=evaluators,
        metadata={"mode": mode, "model": execution_llm.model_name},
    )

    # 9. 결과 변환
    results = []
    for item_result in experiment_result.item_results:
        # dataset item에서 case_id 추출
        item = item_result.item
        case_id = ""
        if hasattr(item, "metadata") and item.metadata:
            case_id = item.metadata.get("case_id", "")

        # 점수 추출 (evaluations 리스트에서)
        scores = {}
        for evaluation in item_result.evaluations:
            # evaluation이 dict일 수도 있고 Evaluation 객체일 수도 있음
            if isinstance(evaluation, dict):
                name = evaluation.get("name", "unknown")
                value = evaluation.get("value", 0.0)
            else:
                name = evaluation.name
                value = evaluation.value
            scores[name] = value

        # LLM Judge 점수만 추출하여 overall 계산
        llm_judge_scores = {
            k: v for k, v in scores.items() if k.startswith("llm_judge_")
        }
        overall_score = (
            sum(llm_judge_scores.values()) / len(llm_judge_scores)
            if llm_judge_scores
            else None
        )

        # sanity check
        keyword_score = scores.get("keyword_inclusion", 1.0)
        forbidden_score = scores.get("forbidden_word_check", 1.0)
        sanity_passed = keyword_score >= 0.5 and forbidden_score == 1.0

        passed = sanity_passed and (overall_score is None or overall_score >= 0.5)

        status = "✓" if passed else "✗"
        score_str = f"{overall_score:.2f}" if overall_score else "-"
        print(f"  [{case_id}] {status} ({score_str})")

        output_text = ""
        if item_result.output:
            if isinstance(item_result.output, dict):
                output_text = item_result.output.get("output", "")
            else:
                output_text = str(item_result.output)

        results.append(
            {
                "case_id": case_id,
                "output": output_text,
                "scores": scores,
                "overall_score": overall_score,
                "passed": passed,
                "trace_id": item_result.trace_id,
            }
        )

    # 10. 요약
    total = len(results)
    passed_count = sum(1 for r in results if r.get("passed", False))
    all_scores = [
        r["overall_score"] for r in results if r.get("overall_score") is not None
    ]

    summary = {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": passed_count / total if total > 0 else 0.0,
        "avg_score": sum(all_scores) / len(all_scores) if all_scores else None,
    }

    print("\n✅ Langfuse Experiment 완료!")
    print(f"  결과: {passed_count}/{total} 통과 ({summary['pass_rate']:.1%})")
    if summary["avg_score"]:
        print(f"  평균 점수: {summary['avg_score']:.3f}")
    print("  확인: http://localhost:3000")

    return {
        "experiment_name": experiment_name,
        "prompt_name": prompt_name,
        "mode": mode,
        "model": execution_llm.model_name,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": summary,
    }


# ============================================================
# 통합 Experiment 함수
# ============================================================


def run_experiment(
    prompt_name: str,
    mode: RunMode = "full",
    experiment_prefix: str | None = None,
    prompt_version: str | None = None,
    backend: Backend = "langfuse",
) -> str | dict[str, Any]:
    """평가 실험 실행 (통합 인터페이스).

    backend 파라미터로 LangSmith 또는 Langfuse 선택 가능.

    Args:
        prompt_name: 평가 세트 이름
        mode: 실행 모드 (quick/full)
        experiment_prefix: 실험 이름 접두사
        prompt_version: 프롬프트 버전 태그
        backend: 실험 백엔드 ("langsmith" | "langfuse")

    Returns:
        LangSmith: 실험 URL (str)
        Langfuse: 실험 결과 딕셔너리 (dict)
    """
    if backend == "langsmith":
        return run_langsmith_experiment(
            prompt_name=prompt_name,
            mode=mode,
            experiment_prefix=experiment_prefix,
            prompt_version=prompt_version,
        )
    elif backend == "langfuse":
        return _run_langfuse_experiment(
            prompt_name=prompt_name,
            mode=mode,
            experiment_prefix=experiment_prefix,
            prompt_version=prompt_version,
        )
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'langsmith' or 'langfuse'.")
