"""LLM-as-a-Judge evaluators.

평가 프롬프트를 파일에서 로드하여 실행합니다.

eval_prompts/
├── general/           # 범용 평가 기준
│   ├── instruction_following.txt
│   ├── factual_accuracy.txt
│   └── output_quality.txt
└── oneonone/          # 1on1 특화 평가 기준
    ├── purpose_alignment.txt
    ├── coaching_quality.txt
    ├── tone_appropriateness.txt
    └── sensitive_topic_handling.txt
"""

import json
from pathlib import Path
from typing import Any, Callable
from langsmith.evaluation import EvaluationResult
from openai import OpenAI


# 프롬프트 디렉토리
PROMPTS_DIR = Path(__file__).parent.parent.parent / "eval_prompts"


def load_eval_prompt(criterion: str) -> str | None:
    """평가 프롬프트 파일 로드.

    Args:
        criterion: 평가 기준 이름 (예: "instruction_following", "purpose_alignment")

    Returns:
        프롬프트 텍스트 또는 None
    """
    # general 폴더에서 찾기
    general_path = PROMPTS_DIR / "general" / f"{criterion}.txt"
    if general_path.exists():
        return general_path.read_text(encoding="utf-8")

    # oneonone 폴더에서 찾기
    oneonone_path = PROMPTS_DIR / "oneonone" / f"{criterion}.txt"
    if oneonone_path.exists():
        return oneonone_path.read_text(encoding="utf-8")

    # 다른 도메인 폴더에서 찾기 (향후 확장)
    for domain_dir in PROMPTS_DIR.iterdir():
        if domain_dir.is_dir():
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


def run_checklist_evaluation(
    output: str,
    inputs: dict,
    prompt_template: str = "",
    criteria: list[str] | None = None,
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """체크리스트 기반 LLM 평가 실행.

    Args:
        output: LLM 출력
        inputs: 입력 데이터
        prompt_template: 원본 프롬프트 (instruction_following용)
        criteria: 평가 기준 목록 (None이면 기본 3개)
        model: 평가용 LLM 모델

    Returns:
        각 기준별 점수 및 상세 결과
    """
    client = OpenAI()
    criteria = criteria or ["instruction_following", "factual_accuracy", "output_quality"]

    input_text = json.dumps(inputs, ensure_ascii=False, indent=2)
    results = {}

    for criterion in criteria:
        template = load_eval_prompt(criterion)
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
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise evaluator. Score each checklist item as 0 (fail) or 1 (pass). Be strict but fair. Always respond with valid JSON."
                    },
                    {"role": "user", "content": eval_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # 체크리스트 점수 계산
            checklist = result.get("checklist", {})
            if checklist:
                score = sum(checklist.values()) / len(checklist)
            else:
                score = result.get("score", 0)

            results[criterion] = {
                "score": float(score),
                "checklist": checklist,
                "passed": float(score) >= 0.6,
                "details": result.get("issues") or result.get("hallucinations") or result.get("feedback", "")
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
    model: str = "gpt-4o-mini"
) -> Callable:
    """LangSmith용 체크리스트 평가자 생성.

    Args:
        criterion: 평가 기준
        prompt_template: 원본 프롬프트
        model: 평가용 LLM 모델

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
            model=model
        )

        criterion_result = result.get(criterion, {})

        return EvaluationResult(
            key=criterion,
            score=criterion_result.get("score", 0.0),
            comment=str(criterion_result.get("details", ""))[:500]
        )

    return evaluator


# ============================================================
# 기존 호환성 유지
# ============================================================

def run_llm_judge_local(
    output: str,
    inputs: dict,
    reference: dict,
    criteria: list[str] | None = None,
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """로컬 모드에서 LLM Judge 실행."""
    return run_checklist_evaluation(
        output=output,
        inputs=inputs,
        prompt_template="",
        criteria=criteria or ["instruction_following", "factual_accuracy", "output_quality"],
        model=model
    )


def get_llm_judge_evaluators(
    criteria_list: list[str],
    model: str = "gpt-4o-mini"
) -> list[Callable]:
    """여러 기준에 대한 LLM Judge 평가자 목록 생성."""
    return [create_checklist_evaluator(c, model=model) for c in criteria_list]
