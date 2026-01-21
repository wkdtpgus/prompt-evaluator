"""평가 파이프라인

데이터 로드 → LLM 호출 → 평가 실행 → 결과 집계

두 가지 모드:
1. 로컬 모드: run_pipeline() - 빠른 개발/테스트
2. LangSmith 모드: run_langsmith_experiment() - 정식 평가, 버전 비교
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langsmith import Client, traceable
from langsmith.evaluation import EvaluationResult, evaluate
from openai import OpenAI

from src.evaluators.rule_based import run_rule_evaluators
from src.evaluators.llm_judge import run_llm_judge_local, create_checklist_evaluator
from src.data import load_evaluation_set, upload_to_langsmith

load_dotenv()

RunMode = Literal["quick", "standard", "full"]


@traceable(name="prompt_execution")
def execute_prompt(
    template: str,
    inputs: dict,
    model: str = "gpt-4o-mini"
) -> str:
    """프롬프트를 LLM에 실행하고 응답 반환.

    Args:
        template: 프롬프트 템플릿 (플레이스홀더 포함)
        inputs: 템플릿에 채울 입력 데이터
        model: 사용할 OpenAI 모델

    Returns:
        LLM 응답 텍스트
    """
    client = OpenAI()

    # 템플릿에 입력 값 채우기
    prompt = template.format(
        qa_pairs=json.dumps(inputs.get("qa_pairs", []), ensure_ascii=False, indent=2),
        survey_answers=json.dumps(inputs.get("survey_answers", []), ensure_ascii=False),
        member_name=inputs.get("member_name", "Unknown"),
        language=inputs.get("language", "Korean")
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content


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
    results = {}
    scores = []

    # 1. Rule-based (항상 실행)
    rule_checks = ["keyword_inclusion", "forbidden_word_check", "format_validity"]
    results["rule_based"] = run_rule_evaluators(output, expected, rule_checks)

    # Rule-based 점수 계산
    rule_scores = [r["score"] for r in results["rule_based"].values()]
    if rule_scores:
        scores.append(sum(rule_scores) / len(rule_scores))

    # 2. Embedding distance (standard 이상)
    if mode in ["standard", "full"]:
        try:
            from src.evaluators.langsmith_builtin import _levenshtein_similarity
            reference = expected.get("reference", {})
            if reference:
                ref_str = json.dumps(reference, ensure_ascii=False)
                similarity = _levenshtein_similarity(output, ref_str)
                results["string_distance"] = {
                    "score": similarity,
                    "passed": similarity >= 0.3,  # 낮은 임계값 (구조가 다를 수 있음)
                    "details": f"Levenshtein similarity: {similarity:.3f}"
                }
                scores.append(similarity)
        except Exception as e:
            results["string_distance"] = {
                "score": 0.0,
                "passed": False,
                "details": f"Error: {str(e)}"
            }

    # 3. LLM Judge (full만)
    if mode == "full":
        try:
            reference = expected.get("reference", {})
            llm_results = run_llm_judge_local(
                output=output,
                inputs=inputs,
                reference=reference,
                criteria=["helpfulness", "relevance"]
            )
            results["llm_judge"] = llm_results

            # LLM Judge 점수 추가
            for criterion, result in llm_results.items():
                scores.append(result["score"])
        except Exception as e:
            results["llm_judge"] = {
                "error": str(e),
                "score": 0.0,
                "passed": False
            }

    # 전체 점수 계산
    overall_score = sum(scores) / len(scores) if scores else 0.0
    min_score = eval_config.get("thresholds", {}).get("min_score", 0.70) if eval_config else 0.70

    results["overall_score"] = overall_score
    results["passed"] = overall_score >= min_score

    return results


@traceable(name="evaluate_case")
def evaluate_single_case(
    template: str,
    test_case: dict,
    expected: dict,
    mode: RunMode = "quick",
    eval_config: dict | None = None,
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """단일 테스트 케이스 평가.

    Args:
        template: 프롬프트 템플릿
        test_case: 테스트 케이스 데이터
        expected: 기대 결과
        mode: 실행 모드
        eval_config: 평가 설정
        model: LLM 모델

    Returns:
        {
            "case_id": str,
            "output": str,
            "evaluation": dict,
            "duration_ms": int
        }
    """
    import time
    start = time.time()

    case_id = test_case.get("id", "unknown")
    inputs = test_case.get("inputs", {})

    # LLM 실행
    output = execute_prompt(template, inputs, model)

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
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """전체 평가 파이프라인 실행.

    Args:
        prompt_name: 평가 세트 이름 (예: "prep_analyzer")
        mode: 실행 모드 (quick/standard/full)
        case_ids: 특정 케이스만 실행 (None이면 전체)
        model: LLM 모델

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
            model=model
        )

        status = "✓" if result["evaluation"]["passed"] else "✗"
        score = result["evaluation"]["overall_score"]
        print(f"{status} ({score:.2f}) [{result['duration_ms']}ms]")

        results.append(result)

    # 요약 계산
    total = len(results)
    passed = sum(1 for r in results if r["evaluation"]["passed"])
    scores = [r["evaluation"]["overall_score"] for r in results]

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else 0.0
    }

    return {
        "prompt_name": prompt_name,
        "mode": mode,
        "model": model,
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
    model: str = "gpt-4o-mini",
    experiment_prefix: str | None = None,
) -> str:
    """LangSmith Experiment로 평가 실행.

    Dataset에 대해 evaluate()를 실행하고 결과를 LangSmith에 기록.
    버전 비교, 회귀 테스트에 활용.

    Args:
        prompt_name: 평가 세트 이름
        mode: 실행 모드 (quick/standard/full)
        model: LLM 모델
        experiment_prefix: 실험 이름 접두사

    Returns:
        실험 URL
    """
    # 1. 데이터셋 업로드 (없으면 생성)
    dataset_name = upload_to_langsmith(prompt_name)

    # 2. 프롬프트 템플릿 로드
    data = load_evaluation_set(prompt_name)
    template = data["template"]
    expected_all = data["expected"]
    eval_config = data["eval_config"]

    # 3. Target 함수 정의 (LLM 호출)
    def target(inputs: dict) -> dict:
        """LangSmith evaluate()에서 호출할 타겟 함수."""
        output = execute_prompt(template, inputs, model)
        return {"output": output}

    # 4. 평가자 함수들 정의
    def keyword_evaluator(run, example) -> EvaluationResult:
        """키워드 포함 평가."""
        output = run.outputs.get("output", "")
        case_id = example.inputs.get("case_id", "")
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
        case_id = example.inputs.get("case_id", "")
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
    evaluators = [keyword_evaluator, forbidden_evaluator, format_evaluator]

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
                evaluators.append(
                    create_checklist_evaluator(criterion, template, model)
                )

    # 7. 실험 이름 설정
    if experiment_prefix is None:
        experiment_prefix = f"{prompt_name}-{mode}"

    # 8. evaluate() 실행
    print(f"\nLangSmith Experiment 시작: {experiment_prefix}")
    print(f"  Dataset: {dataset_name}")
    print(f"  Mode: {mode}")
    print(f"  Model: {model}")
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
