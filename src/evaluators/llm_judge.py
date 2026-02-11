"""LLM-as-a-Judge 평가자.

eval_prompts/{criterion}.txt에서 평가 프롬프트를 로드하여 실행.
"""

import json
from pathlib import Path
from typing import Any


from utils.models import judge_llm

# 프롬프트 디렉토리
PROMPTS_DIR = Path(__file__).parent.parent.parent / "eval_prompts"


def run_checklist_evaluation(
    output: str,
    inputs: dict,
    prompt_template: str = "",
    criteria: list[str] | None = None,
    llm=None,
) -> dict[str, Any]:
    """체크리스트 기반 LLM 평가 실행.

    Args:
        output: LLM 출력
        inputs: 입력 데이터
        prompt_template: 원본 프롬프트 (instruction_following용)
        criteria: 평가 기준 목록 (None이면 기본 3개)
        llm: Judge LLM 인스턴스 (None이면 기본 judge_llm 사용)

    Returns:
        각 기준별 점수 및 상세 결과
    """
    criteria = criteria or [
        "instruction_following",
        "factual_accuracy",
        "output_quality",
    ]

    input_text = json.dumps(inputs, ensure_ascii=False, indent=2)
    results = {}

    # LLM 선택: 주입된 LLM or 기본 judge_llm
    evaluator_llm = llm if llm is not None else judge_llm

    # JSON 응답 강제: structured output으로 순수 JSON 반환
    json_judge = evaluator_llm.bind(response_mime_type="application/json")

    for criterion in criteria:
        prompt_path = PROMPTS_DIR / f"{criterion}.txt"
        if not prompt_path.exists():
            results[criterion] = {"score": 0.0}
            continue

        template = prompt_path.read_text(encoding="utf-8")
        eval_prompt = template.format(
            prompt=prompt_template if prompt_template else "(프롬프트 없음)",
            input=input_text,
            output=output,
        )

        try:
            messages = [
                (
                    "system",
                    "You are a precise evaluator. Score each checklist item as 0 (fail) or 1 (pass). Be strict but fair. Respond with valid JSON only.",
                ),
                ("user", eval_prompt),
            ]
            response = json_judge.invoke(messages)

            result = json.loads(response.content)

            checklist = result.get("checklist", {})
            if checklist:
                score = sum(checklist.values()) / len(checklist)
            else:
                score = result.get("score", 0)

            results[criterion] = {"score": float(score)}

        except Exception:
            results[criterion] = {"score": 0.0}

    # 전체 점수 계산
    if results:
        overall = sum(r["score"] for r in results.values()) / len(results)
        results["overall"] = {"score": overall}

    return results
