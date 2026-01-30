"""LLM-as-a-Judge 평가자.

eval_prompts/{domain}/{criterion}.txt에서 평가 프롬프트를 로드하여 실행.
"""

import json
from pathlib import Path
from typing import Any, Callable

from langsmith.evaluation import EvaluationResult

from utils.models import judge_llm

# 프롬프트 디렉토리
PROMPTS_DIR = Path(__file__).parent.parent.parent / "eval_prompts"


def load_eval_prompt(criterion: str, domain: str | None = None) -> str | None:
    """평가 프롬프트 파일 로드.

    Args:
        criterion: 평가 기준 이름
            - 단순: "instruction_following" → domain에서 검색
            - 경로 포함: "oneonone/coaching_quality" → 해당 경로 직접 사용
        domain: 우선 검색할 도메인 (예: "meeting_prep"). None이면 general 우선.

    Returns:
        프롬프트 텍스트 또는 None
    """
    if not PROMPTS_DIR.exists():
        return None

    # 0. criterion에 경로가 포함된 경우 (예: "oneonone/coaching_quality")
    if "/" in criterion:
        explicit_path = PROMPTS_DIR / f"{criterion}.txt"
        if explicit_path.exists():
            return explicit_path.read_text(encoding="utf-8")
        # 경로가 명시되었는데 없으면 None 반환 (다른 곳에서 찾지 않음)
        return None

    # 1. 지정된 도메인에서 먼저 검색
    if domain:
        domain_path = PROMPTS_DIR / domain / f"{criterion}.txt"
        if domain_path.exists():
            return domain_path.read_text(encoding="utf-8")

    # 2. general에서 검색
    general_path = PROMPTS_DIR / "general" / f"{criterion}.txt"
    if general_path.exists():
        return general_path.read_text(encoding="utf-8")

    # 3. 다른 모든 도메인에서 검색
    for domain_dir in sorted(PROMPTS_DIR.iterdir(), key=lambda d: d.name):
        if domain_dir.is_dir() and domain_dir.name not in ["general", domain]:
            path = domain_dir / f"{criterion}.txt"
            if path.exists():
                return path.read_text(encoding="utf-8")

    return None


def list_available_criteria() -> dict[str, str]:
    """사용 가능한 평가 기준 목록 반환."""
    criteria = {}

    # 모든 도메인 폴더 스캔
    if PROMPTS_DIR.exists():
        for domain_dir in PROMPTS_DIR.iterdir():
            if domain_dir.is_dir():
                for prompt_file in domain_dir.glob("*.txt"):
                    name = prompt_file.stem
                    domain = domain_dir.name
                    criteria[name] = f"{domain}/{name}"

    return criteria


def _build_failure_comment(result: dict, failed_items: list[str]) -> str:
    """0점 항목에 대한 상세 코멘트 생성.

    Args:
        result: LLM 평가 결과 전체
        failed_items: 0점 받은 체크리스트 항목 키 목록

    Returns:
        사람이 읽기 쉬운 실패 이유 문자열
    """
    if not failed_items:
        return result.get("reasoning", "") or result.get("feedback", "") or "All checks passed"

    parts = []

    # 1. 0점 항목 목록
    parts.append(f"Failed: {', '.join(failed_items)}")

    # 2. bad_examples가 있으면 추가
    bad_examples = result.get("bad_examples", [])
    if bad_examples:
        parts.append("Issues: " + "; ".join(bad_examples[:3]))  # 최대 3개

    # 3. reasoning/feedback이 있으면 추가
    reasoning = result.get("reasoning", "") or result.get("feedback", "")
    if reasoning:
        parts.append(f"Reason: {reasoning}")

    return " | ".join(parts)


def run_checklist_evaluation(
    output: str,
    inputs: dict,
    prompt_template: str = "",
    criteria: list[str] | None = None,
    domain: str | None = None,
    callbacks: list | None = None,
) -> dict[str, Any]:
    """체크리스트 기반 LLM 평가 실행.

    Args:
        output: LLM 출력
        inputs: 입력 데이터
        prompt_template: 원본 프롬프트 (instruction_following용)
        criteria: 평가 기준 목록 (None이면 기본 3개)
        domain: eval_prompts 도메인 (예: "oneonone")
        callbacks: LangChain 콜백 핸들러 목록 (Langfuse 트레이싱 등)

    Returns:
        각 기준별 점수 및 상세 결과
    """
    criteria = criteria or ["instruction_following", "factual_accuracy", "output_quality"]

    input_text = json.dumps(inputs, ensure_ascii=False, indent=2)
    results = {}

    # JSON 응답 강제
    llm_with_json = judge_llm.bind(response_format={"type": "json_object"})

    invoke_kwargs = {}
    if callbacks:
        invoke_kwargs["config"] = {"callbacks": callbacks}

    for criterion in criteria:
        template = load_eval_prompt(criterion, domain)
        if not template:
            results[criterion] = {
                "score": 0.0,
                "checklist": {},
                "passed": False,
                "details": f"평가 프롬프트 없음: eval_prompts/*/{criterion}.txt"
            }
            continue

        # 프롬프트 생성
        eval_prompt = template.format(
            prompt=prompt_template[:2000] if prompt_template else "(프롬프트 없음)",
            input=input_text[:3000],
            output=output[:3000]
        )

        try:
            messages = [
                ("system", "You are a precise evaluator. Score each checklist item as 0 (fail) or 1 (pass). Be strict but fair. Always respond with valid JSON."),
                ("user", eval_prompt)
            ]
            response = llm_with_json.invoke(messages, **invoke_kwargs)

            result = json.loads(response.content)

            # 체크리스트 점수 계산
            checklist = result.get("checklist", {})
            if checklist:
                score = sum(checklist.values()) / len(checklist)
            else:
                score = result.get("score", 0)

            # 0점 항목 추출 및 이유 생성
            failed_items = [k for k, v in checklist.items() if v == 0]
            details = _build_failure_comment(result, failed_items)

            results[criterion] = {
                "score": float(score),
                "checklist": checklist,
                "passed": float(score) >= 0.6,
                "details": details,
                "failed_items": failed_items,
            }

        except Exception as e:
            results[criterion] = {
                "score": 0.0,
                "checklist": {},
                "passed": False,
                "details": f"Error: {str(e)}"
            }

    # 전체 점수 계산
    if results:
        overall = sum(r["score"] for r in results.values()) / len(results)
        results["overall"] = {
            "score": overall,
            "passed": overall >= 0.6
        }

    return results


def create_checklist_evaluator(
    criterion: str,
    prompt_template: str = "",
    domain: str | None = None,
) -> Callable:
    """LangSmith용 체크리스트 평가자 생성.

    Args:
        criterion: 평가 기준
        prompt_template: 원본 프롬프트
        domain: eval_prompts 도메인 (예: "oneonone")

    Returns:
        LangSmith evaluate()에서 사용할 평가자 함수
    """
    def evaluator(run, example) -> EvaluationResult:
        output = run.outputs.get("output", "")
        inputs = example.inputs

        result = run_checklist_evaluation(
            output=output,
            inputs=inputs,
            prompt_template=prompt_template,
            criteria=[criterion],
            domain=domain,
        )

        criterion_result = result.get(criterion, {})

        # comment에 0점 항목과 이유를 포함
        details = criterion_result.get("details", "")
        failed_items = criterion_result.get("failed_items", [])

        # 0점인 경우에만 상세 정보 표시
        if failed_items:
            comment = details
        else:
            comment = "All checks passed" if criterion_result.get("score", 0) == 1.0 else details

        return EvaluationResult(
            key=criterion,
            score=criterion_result.get("score", 0.0),
            comment=str(comment)[:1000]  # 1000자로 확장
        )

    return evaluator


