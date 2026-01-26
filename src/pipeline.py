"""평가 파이프라인

데이터 로드 → LLM 호출 → 평가 실행 → 결과 집계

두 가지 모드:
1. 로컬 모드: run_pipeline() - 빠른 개발/테스트
2. LangSmith 모드: run_langsmith_experiment() - 정식 평가, 버전 비교
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langsmith import Client, traceable
from langsmith.evaluation import EvaluationResult, evaluate

from configs.config import (
    DEFAULT_MIN_SCORE,
    DEFAULT_STRING_SIMILARITY_THRESHOLD,
)
from src.evaluators.rule_based import run_rule_evaluators
from src.evaluators.llm_judge import run_checklist_evaluation, create_checklist_evaluator
from src.evaluators.similarity import _levenshtein_similarity
from src.data_loader import load_evaluation_set, upload_to_langsmith
from utils.models import execution_llm

load_dotenv()

RunMode = Literal["quick", "full"]


@traceable(name="prompt_execution")
def execute_prompt(
    template: str,
    inputs: dict,
) -> str:
    """프롬프트를 LLM에 실행하고 응답 반환.

    Args:
        template: 프롬프트 템플릿 (플레이스홀더 포함)
        inputs: 템플릿에 채울 입력 데이터

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

    prompt = template.format(**format_args)

    response = execution_llm.invoke(prompt)

    return response.content


@traceable(name="run_evaluation")
def run_evaluation(
    output: str,
    expected: dict,
    inputs: dict,
    mode: RunMode = "quick",
    eval_config: dict | None = None
) -> dict[str, Any]:
    """출력에 대한 평가 실행.

    Args:
        output: LLM 출력
        expected: 기대 결과 (keywords, forbidden, reference)
        inputs: 원본 입력 (LLM Judge용)
        mode: 실행 모드 (quick/standard/full)
        eval_config: 평가 설정

    Returns:
        {
            "rule_based": {...},
            "embedding": {...},  # standard 이상
            "llm_judge": {...},  # full만
            "overall_score": float,
            "passed": bool
        }
    """
    # ============================================================
    # 1. Sanity Checks (pass/fail만, 점수에 미반영)
    # ============================================================
    rule_checks = ["keyword_inclusion", "forbidden_word_check", "format_validity"]
    rule_results = run_rule_evaluators(output, expected, rule_checks, eval_config)

    sanity_all_passed = all(r["passed"] for r in rule_results.values())
    sanity_checks = {
        "checks": rule_results,
        "all_passed": sanity_all_passed,
    }

    # ============================================================
    # 2. Scoring (점수에 반영되는 평가들) - full 모드에서만 실행
    # ============================================================
    scoring_results = {}
    score_breakdown = []  # (name, score, weight) 튜플 리스트

    if mode == "full":
        # 2-1. 문자열 유사도 (reference가 있는 경우만)
        try:
            reference = expected.get("reference", {})
            if reference:
                ref_str = json.dumps(reference, ensure_ascii=False)
                similarity = _levenshtein_similarity(output, ref_str)
                scoring_results["string_similarity"] = {
                    "score": similarity,
                    "passed": similarity >= DEFAULT_STRING_SIMILARITY_THRESHOLD,
                    "details": f"Levenshtein similarity: {similarity:.3f}",
                    "weight": 1.0,
                }
                score_breakdown.append(("string_similarity", similarity, 1.0))
        except Exception as e:
            scoring_results["string_similarity"] = {
                "score": 0.0,
                "passed": False,
                "details": f"Error: {str(e)}",
                "weight": 1.0,
            }

        # 2-2. LLM Judge
        try:
            domain = eval_config.get("eval_prompts_domain") if eval_config else None

            # config에서 criteria 가져오기
            criteria = ["helpfulness", "relevance"]  # 기본값
            if eval_config:
                for evaluator in eval_config.get("evaluators", []):
                    if evaluator.get("type") == "llm_judge":
                        criteria = evaluator.get("criteria", criteria)
                        break

            llm_results = run_checklist_evaluation(
                output=output,
                inputs=inputs,
                criteria=criteria,
                domain=domain,
            )
            scoring_results["llm_judge"] = {
                "criteria": llm_results,
                "weight": 1.0,
            }

            # LLM Judge 점수 추가
            for criterion, result in llm_results.items():
                if criterion != "overall":
                    score_breakdown.append((f"llm_judge.{criterion}", result["score"], 1.0))
        except Exception as e:
            scoring_results["llm_judge"] = {
                "error": str(e),
                "criteria": {},
                "weight": 1.0,
            }

    # ============================================================
    # 3. 최종 점수 계산
    # ============================================================
    if score_breakdown:
        total_weight = sum(w for _, _, w in score_breakdown)
        weighted_sum = sum(s * w for _, s, w in score_breakdown)
        overall_score = weighted_sum / total_weight
    else:
        overall_score = None  # quick 모드: 점수 없음

    min_score = eval_config.get("thresholds", {}).get("min_score", DEFAULT_MIN_SCORE) if eval_config else DEFAULT_MIN_SCORE

    # passed 판정
    # - quick: sanity check만 통과하면 pass
    # - full: sanity check + 점수 기준 통과
    if mode == "quick":
        passed = sanity_all_passed
        fail_reason = None if sanity_all_passed else "sanity_check_failed"
    else:
        passed = sanity_all_passed and (overall_score or 0) >= min_score
        fail_reason = _get_fail_reason(sanity_all_passed, overall_score or 0, min_score)

    # 결과 조합
    return {
        "sanity_checks": sanity_checks,
        "scoring": scoring_results,
        "score_breakdown": [
            {"name": name, "score": score, "weight": weight}
            for name, score, weight in score_breakdown
        ],
        "overall_score": overall_score,
        "min_score": min_score if mode == "full" else None,
        "passed": passed,
        "fail_reason": fail_reason,
    }


def _get_fail_reason(sanity_passed: bool, score: float, min_score: float) -> str | None:
    """실패 사유 반환 (full 모드용)."""
    if not sanity_passed:
        return "sanity_check_failed"
    if score < min_score:
        return f"score_below_threshold ({score:.3f} < {min_score})"
    return None


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
        "duration_ms": duration_ms
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
    scores = [r["evaluation"]["overall_score"] for r in results if r["evaluation"]["overall_score"] is not None]

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else None
    }

    return {
        "prompt_name": prompt_name,
        "mode": mode,
        "model": execution_llm.model_name,
        "timestamp": datetime.now().isoformat(),
        "cases": results,
        "summary": summary
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
    from src.data_loader import pull_prompt

    # 1. 데이터셋 업로드 (없으면 생성)
    dataset_name = upload_to_langsmith(prompt_name)

    # 2. 프롬프트 템플릿 로드
    data = load_evaluation_set(prompt_name)
    expected_all = data["expected"]
    eval_config = data["eval_config"]

    # 프롬프트 소스 결정: LangSmith 버전 or 로컬 파일
    if prompt_version:
        print(f"  LangSmith 프롬프트 버전: {prompt_version}")
        template = pull_prompt(prompt_name, version_tag=prompt_version)
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
            comment=f"Found {found}/{len(keywords)} keywords"
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
            comment=f"Violations: {violations}" if violations else "No violations"
        )

    def format_evaluator(run, example) -> EvaluationResult:
        """JSON 포맷 검증."""
        output = run.outputs.get("output", "")

        try:
            parsed = json.loads(output)
            if "question_context" in parsed:
                return EvaluationResult(
                    key="format_validity",
                    score=1.0,
                    comment="Valid JSON with question_context"
                )
            return EvaluationResult(
                key="format_validity",
                score=0.5,
                comment="Valid JSON but missing question_context"
            )
        except json.JSONDecodeError as e:
            return EvaluationResult(
                key="format_validity",
                score=0.0,
                comment=f"Invalid JSON: {str(e)}"
            )

    # 5. 모드에 따른 평가자 선택
    # Note: rule-based 평가자는 sanity check용으로만 사용 (LangSmith에서는 점수로 기록되지만
    # 실제 pass/fail 판정은 llm_judge 기준으로 함)
    evaluators = [keyword_evaluator, forbidden_evaluator, format_evaluator]

    # 6. LLM Judge 평가자 추가 (full 모드 또는 eval_config에 설정된 경우)
    llm_judge_config = None
    for evaluator in eval_config.get("evaluators", []):
        if evaluator.get("type") == "llm_judge":
            llm_judge_config = evaluator
            break

    if llm_judge_config and llm_judge_config.get("enabled", True):
        criteria = llm_judge_config.get("criteria", [])
        domain = eval_config.get("eval_prompts_domain")
        if mode == "full" or criteria:
            print(f"  LLM Judge 평가자 추가: {criteria}")
            if domain:
                print(f"  eval_prompts 도메인: {domain}")
            for criterion in criteria:
                evaluators.append(
                    create_checklist_evaluator(criterion, template, domain)
                )

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
    experiment_url = f"https://smith.langchain.com/datasets"
    print(f"\n✅ Experiment 완료!")
    print(f"  결과 확인: {experiment_url}")

    return experiment_url
