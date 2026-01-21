"""LLM-as-a-Judge evaluators.

체크리스트 기반 품질 평가:
1. instruction_following: 프롬프트 지시사항 준수
2. factual_accuracy: 사실 정확성 / 할루시네이션 검사
3. output_quality: 전반적 출력 품질

1on1 Meeting 특화 평가:
4. purpose_alignment: 1on1 미팅 목적 부합도
5. coaching_quality: 코칭 힌트 품질
6. tone_appropriateness: 톤/어조 적절성

비용이 발생하므로 full 모드에서만 사용.
"""

import json
from typing import Any, Callable
from langsmith.evaluation import EvaluationResult
from openai import OpenAI


# ============================================================
# 체크리스트 기반 평가 프롬프트
# ============================================================

# ============================================================
# 1on1 Meeting 특화 평가 프롬프트
# ============================================================

ONEONONE_PROMPTS = {
    "purpose_alignment": """You are an expert evaluator for 1on1 meeting coaching quality.

## Evaluation Criteria
1on1 meetings are NOT work status report meetings. Leaders already know basic work status.

The PURPOSE of 1on1 is:
- **Member support**: Understand member's challenges, blockers, and needs
- **Relationship building**: Show genuine care about the member's well-being
- **Growth facilitation**: Help member reflect and grow
- **Trust building**: Create safe space for open communication

## Input:
{input}

## AI's Output (coaching hints):
{output}

## Checklist - Score each item (0 or 1):

1. **Focus on Member**: Does the hint focus on member's feelings, struggles, or well-being?
2. **Support Oriented**: Does it suggest how leader can support/help (not request information)?
3. **Avoids Status Questions**: Does it avoid asking about basic work status/progress?
4. **Explores Growth**: Does it touch on growth, learning, or career aspects?
5. **Relationship Building**: Does it help build trust and open communication?

## Response Format (JSON):
{{
    "checklist": {{
        "focus_on_member": 0 or 1,
        "support_oriented": 0 or 1,
        "avoids_status_questions": 0 or 1,
        "explores_growth": 0 or 1,
        "relationship_building": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "good_examples": ["list of hints that serve 1on1 purpose well"],
    "bad_examples": ["list of hints that feel like status reports"]
}}""",

    "coaching_quality": """You are evaluating coaching hint quality for 1on1 meetings.

## Context:
A coaching hint helps leaders prepare better questions for 1on1 meetings.

## Input (member's response data):
{input}

## AI's Coaching Hints:
{output}

## Checklist - Score each item (0 or 1):

1. **Actionable**: Can the leader act on this hint immediately?
2. **Specific**: Is it specific to this member's situation (not generic)?
3. **Empathetic**: Does it show understanding of member's perspective?
4. **Safe**: Does it respect boundaries and sensitive topics?
5. **Contextual**: Does it connect to what the member actually said/expressed?

## Response Format (JSON):
{{
    "checklist": {{
        "actionable": 0 or 1,
        "specific": 0 or 1,
        "empathetic": 0 or 1,
        "safe": 0 or 1,
        "contextual": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "feedback": "brief constructive feedback on how to improve"
}}""",

    "tone_appropriateness": """You are evaluating the tone and language appropriateness of coaching hints.

## Task Context:
Coaching hints for leaders in 1on1 meeting preparation.

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **Professional**: Is the language professional but warm?
2. **Non-judgmental**: Does it avoid judging the member's responses?
3. **Constructive**: Is the framing positive and constructive?
4. **Appropriate Length**: Is each hint concise (1-2 sentences)?
5. **Language Match**: Is it in the requested language (Korean/English)?

## Response Format (JSON):
{{
    "checklist": {{
        "professional": 0 or 1,
        "non_judgmental": 0 or 1,
        "constructive": 0 or 1,
        "appropriate_length": 0 or 1,
        "language_match": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "issues": ["list of tone/style issues, if any"]
}}""",

    "sensitive_topic_handling": """You are evaluating how well the AI handles sensitive topics.

## Sensitive Topics in 1on1:
- Burnout signals
- Team conflicts
- Career concerns
- Personal struggles
- Avoided responses (member deflecting questions)

## Input:
{input}

## AI's Coaching Hints:
{output}

## Checklist - Score each item (0 or 1):

1. **Recognizes Signals**: Does it identify sensitive signals in member's response?
2. **Respects Boundaries**: Does it suggest respecting member's boundaries?
3. **Safe Approach**: Does it recommend gentle, non-intrusive follow-up?
4. **Alternative Topics**: Does it suggest alternative safer topics when needed?
5. **No Pressure**: Does it avoid pushing members to share more than comfortable?

## Response Format (JSON):
{{
    "checklist": {{
        "recognizes_signals": 0 or 1,
        "respects_boundaries": 0 or 1,
        "safe_approach": 0 or 1,
        "alternative_topics": 0 or 1,
        "no_pressure": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "sensitive_areas": ["list of sensitive topics detected"],
    "handling_quality": "brief assessment of how well sensitive areas were handled"
}}""",
}


# ============================================================
# 일반 체크리스트 평가 프롬프트
# ============================================================

CHECKLIST_PROMPTS = {
    "instruction_following": """You are evaluating if the AI followed the prompt instructions.

## Original Prompt (Instructions):
{prompt}

## Input Data:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **Output Format**: Did the AI use the requested format? (JSON, specific fields, structure)
2. **Required Fields**: Are all required fields present in the output?
3. **Constraints**: Did the AI follow specified constraints? (length, tone, language, etc.)
4. **Task Completion**: Did the AI complete the requested task?
5. **No Extra Content**: Did the AI avoid adding unrequested content?

## Response Format (JSON):
{{
    "checklist": {{
        "output_format": 0 or 1,
        "required_fields": 0 or 1,
        "constraints": 0 or 1,
        "task_completion": 0 or 1,
        "no_extra_content": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "issues": ["list of specific issues found, if any"]
}}""",

    "factual_accuracy": """You are evaluating factual accuracy and hallucination.

## Input Data (Ground Truth):
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **No Fabrication**: Did the AI avoid making up information not in the input?
2. **No Distortion**: Did the AI avoid distorting/misrepresenting input data?
3. **Accurate Extraction**: Are extracted facts accurate to the source?
4. **Reasonable Inference**: Are any inferences logically sound?
5. **No Hallucinated Details**: Are there no hallucinated names, numbers, or specifics?

## Response Format (JSON):
{{
    "checklist": {{
        "no_fabrication": 0 or 1,
        "no_distortion": 0 or 1,
        "accurate_extraction": 0 or 1,
        "reasonable_inference": 0 or 1,
        "no_hallucinated_details": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "hallucinations": ["list of specific hallucinations found, if any"]
}}""",

    "output_quality": """You are evaluating overall output quality.

## Task Context:
{prompt}

## Input:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **Clarity**: Is the output clear and easy to understand?
2. **Completeness**: Does it address all aspects of the task?
3. **Usefulness**: Would this output be useful for the intended purpose?
4. **Consistency**: Is the output internally consistent?
5. **Professionalism**: Is the tone/style appropriate?

## Response Format (JSON):
{{
    "checklist": {{
        "clarity": 0 or 1,
        "completeness": 0 or 1,
        "usefulness": 0 or 1,
        "consistency": 0 or 1,
        "professionalism": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "feedback": "brief constructive feedback"
}}""",
}


# 모든 프롬프트 통합 (일반 + 1on1 특화)
ALL_CHECKLIST_PROMPTS = {**CHECKLIST_PROMPTS, **ONEONONE_PROMPTS}


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
        criteria: 평가 기준 목록 (None이면 전체)
        model: 평가용 LLM 모델

    Returns:
        {
            "instruction_following": {
                "score": float,
                "checklist": dict,
                "issues": list
            },
            ...
        }
    """
    client = OpenAI()
    criteria = criteria or ["instruction_following", "factual_accuracy", "output_quality"]

    input_text = json.dumps(inputs, ensure_ascii=False, indent=2)
    results = {}

    for criterion in criteria:
        template = ALL_CHECKLIST_PROMPTS.get(criterion)
        if not template:
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
                "passed": float(score) >= 0.6,  # 60% 이상 통과
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
        criterion: 평가 기준 (instruction_following, factual_accuracy, output_quality)
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
# 기존 호환성 유지 (deprecated)
# ============================================================

CRITERIA_PROMPTS = {
    "helpfulness": CHECKLIST_PROMPTS["output_quality"],
    "relevance": CHECKLIST_PROMPTS["factual_accuracy"],
    "coherence": CHECKLIST_PROMPTS["instruction_following"],
}


def run_llm_judge_local(
    output: str,
    inputs: dict,
    reference: dict,
    criteria: list[str] | None = None,
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """로컬 모드에서 LLM Judge 실행 (체크리스트 기반).

    기존 인터페이스 유지하면서 내부는 체크리스트 방식으로 변경.
    """
    # 새로운 체크리스트 기반 평가 실행
    return run_checklist_evaluation(
        output=output,
        inputs=inputs,
        prompt_template="",
        criteria=["instruction_following", "factual_accuracy", "output_quality"],
        model=model
    )


def create_llm_judge_evaluator(
    criteria: str,
    model: str = "gpt-4o-mini"
) -> Callable:
    """LLM-as-Judge 평가자 생성 (기존 호환).

    내부적으로 체크리스트 평가자 사용.
    """
    # 기존 criteria를 새 criteria로 매핑
    mapping = {
        "helpfulness": "output_quality",
        "relevance": "factual_accuracy",
        "coherence": "instruction_following",
    }
    new_criterion = mapping.get(criteria, criteria)

    return create_checklist_evaluator(new_criterion, model=model)


def get_llm_judge_evaluators(
    criteria_list: list[str],
    model: str = "gpt-4o-mini"
) -> list[Callable]:
    """여러 기준에 대한 LLM Judge 평가자 목록 생성."""
    return [create_llm_judge_evaluator(c, model) for c in criteria_list]


# ============================================================
# 1on1 특화 평가 함수
# ============================================================

def run_oneonone_evaluation(
    output: str,
    inputs: dict,
    criteria: list[str] | None = None,
    model: str = "gpt-4o-mini"
) -> dict[str, Any]:
    """1on1 Meeting 특화 평가 실행.

    Args:
        output: LLM 출력 (coaching hints)
        inputs: 입력 데이터 (qa_pairs, survey_answers 등)
        criteria: 평가 기준 목록 (None이면 1on1 전체)
        model: 평가용 LLM 모델

    Returns:
        각 기준별 점수 및 상세 결과
    """
    criteria = criteria or [
        "purpose_alignment",
        "coaching_quality",
        "tone_appropriateness",
        "sensitive_topic_handling"
    ]

    return run_checklist_evaluation(
        output=output,
        inputs=inputs,
        prompt_template="",
        criteria=criteria,
        model=model
    )


def create_oneonone_evaluator(
    criterion: str,
    model: str = "gpt-4o-mini"
) -> Callable:
    """1on1 특화 LangSmith 평가자 생성.

    Args:
        criterion: 평가 기준 (purpose_alignment, coaching_quality, etc.)
        model: 평가용 LLM 모델

    Returns:
        LangSmith evaluate()에서 사용할 평가자 함수
    """
    return create_checklist_evaluator(criterion, model=model)


def get_oneonone_evaluators(
    model: str = "gpt-4o-mini"
) -> list[Callable]:
    """1on1 특화 평가자 전체 목록 생성."""
    criteria = [
        "purpose_alignment",
        "coaching_quality",
        "tone_appropriateness",
        "sensitive_topic_handling"
    ]
    return [create_oneonone_evaluator(c, model) for c in criteria]


# 사용 가능한 모든 평가 기준 목록
AVAILABLE_CRITERIA = {
    # 일반 평가 기준
    "instruction_following": "프롬프트 지시사항 준수도",
    "factual_accuracy": "사실 정확성 / 할루시네이션 검사",
    "output_quality": "전반적 출력 품질",
    # 1on1 특화 평가 기준
    "purpose_alignment": "1on1 미팅 목적 부합도",
    "coaching_quality": "코칭 힌트 품질",
    "tone_appropriateness": "톤/어조 적절성",
    "sensitive_topic_handling": "민감한 주제 처리",
}


def list_available_criteria() -> dict[str, str]:
    """사용 가능한 평가 기준 목록 반환."""
    return AVAILABLE_CRITERIA.copy()
