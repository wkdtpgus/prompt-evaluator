"""평가 파이프라인

프롬프트 실행 → 평가 → 실험 (LangSmith / Langfuse)
"""

import json
import re
from datetime import datetime
from typing import Any, Literal

from dotenv import load_dotenv, find_dotenv
from langsmith import traceable
from langsmith.evaluation import evaluate

# Langfuse imports (lazy import for optional dependency)
try:
    from prompt_evaluator.utils.langfuse_client import (
        get_langfuse_client,
        get_langfuse_handler,
    )

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

from prompt_evaluator.loaders import load_evaluation_set
from prompt_evaluator.utils.dataset_sync import upload_dataset, get_dataset
from prompt_evaluator.evaluators.adapters import (
    create_langfuse_evaluator,
    create_langfuse_forbidden_evaluator,
    create_langfuse_keyword_evaluator,
    create_langsmith_evaluator,
    create_langsmith_forbidden_evaluator,
    create_langsmith_keyword_evaluator,
)
from prompt_evaluator.evaluators.scoring import compute_pass_result
from prompt_evaluator.utils.prompt_sync import get_prompt

load_dotenv(find_dotenv(usecwd=True))

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
    # {{var}} → {var} 변환 (프롬프트 파일이 이중 중괄호 사용 시 .format() 호환)
    template = re.sub(r"\{\{(\w+)\}\}", r"{\1}", template)

    # 템플릿에 입력 값 채우기
    format_args = {}
    for key, value in inputs.items():
        if isinstance(value, (dict, list)):
            format_args[key] = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            format_args[key] = value

    prompt = template.format(**format_args)

    invoke_kwargs = {}
    if callbacks:
        invoke_kwargs["config"] = {"callbacks": callbacks}

    response = get_execution_llm().invoke(prompt, **invoke_kwargs)

    return response.content


# ============================================================
# LangSmith Experiment 모드
# ============================================================


def run_langsmith_experiment(
    prompt_name: str,
    mode: RunMode = "full",
    experiment_prefix: str | None = None,
    prompt_version: str | None = None,
) -> str:
    """LangSmith Experiment로 평가 실행.

    Dataset에 대해 evaluate()를 실행하고 결과를 LangSmith에 기록.
    버전 비교, 회귀 테스트에 활용.

    Args:
        prompt_name: 평가 세트 이름
        mode: 실행 모드 (quick/full)
        experiment_prefix: 실험 이름 접두사
        prompt_version: LangSmith 프롬프트 버전 태그 (None이면 로컬 파일 사용)

    Returns:
        실험 URL
    """
    from prompt_evaluator.context import get_context

    ctx = get_context()

    # 1. 데이터셋 업로드 (없으면 생성)
    ds_result = upload_dataset(
        prompt_name,
        backend="langsmith",
        targets_dir=str(ctx.targets_dir),
        datasets_dir=str(ctx.datasets_dir),
    )
    dataset_name = ds_result.get("langsmith_name", f"prompt-eval-{prompt_name}")

    # 2. 프롬프트 템플릿 로드
    data = load_evaluation_set(
        prompt_name,
        targets_dir=ctx.targets_dir,
        datasets_dir=ctx.datasets_dir,
    )
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

    # 4. 평가자 구성
    evaluators = [
        create_langsmith_keyword_evaluator(expected_all),
        create_langsmith_forbidden_evaluator(expected_all),
    ]

    # 5. LLM Judge 평가자 추가 (full 모드 또는 eval_config에 설정된 경우)
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
    print(f"  Model: {get_execution_llm().model_name}")
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


def run_langfuse_experiment(
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
    from prompt_evaluator.context import get_context

    ctx = get_context()
    data = load_evaluation_set(
        prompt_name,
        targets_dir=ctx.targets_dir,
        datasets_dir=ctx.datasets_dir,
    )
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
    print(f"  Model: {get_execution_llm().model_name}")
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

    # 6. 평가자 구성
    evaluators = [
        create_langfuse_keyword_evaluator(expected_all),
        create_langfuse_forbidden_evaluator(expected_all),
    ]

    # LLM Judge 평가자 추가 (full 모드)
    if use_llm_judge:
        for criterion in criteria:
            evaluators.append(create_langfuse_evaluator(criterion, template))

    # 8. Langfuse 내장 run_experiment 실행
    print("  실험 실행 중...")
    experiment_result = langfuse.run_experiment(
        name=experiment_name,
        data=dataset.items,
        task=task,
        evaluators=evaluators,
        metadata={"mode": mode, "model": get_execution_llm().model_name},
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

        # pass/fail 판정
        pass_result = compute_pass_result(scores)
        overall_score = pass_result["overall_score"]
        passed = pass_result["passed"]

        status = "✓" if passed else "✗"
        score_str = f"{overall_score:.2f}" if overall_score is not None else "-"
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
    if summary["avg_score"] is not None:
        print(f"  평균 점수: {summary['avg_score']:.3f}")
    print("  확인: http://localhost:3000")

    return {
        "experiment_name": experiment_name,
        "prompt_name": prompt_name,
        "mode": mode,
        "model": get_execution_llm().model_name,
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
        return run_langfuse_experiment(
            prompt_name=prompt_name,
            mode=mode,
            experiment_prefix=experiment_prefix,
            prompt_version=prompt_version,
        )
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'langsmith' or 'langfuse'.")
