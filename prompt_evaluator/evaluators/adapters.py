"""평가 결과를 LangSmith/Langfuse 플랫폼 형식으로 변환하는 어댑터.

rule_based.py, llm_judge.py의 평가 로직을 호출하고
결과를 각 플랫폼이 요구하는 형식으로 변환한다.

Note: keyword/forbidden 어댑터는 LangSmith/Langfuse 간 핵심 로직이 동일하지만,
플랫폼별 함수 시그니처가 다르기 때문에 별도로 정의한다.
- LangSmith: (run, example) → EvaluationResult
- Langfuse: (*, output, metadata, ...) → Evaluation
"""

from typing import Callable

from prompt_evaluator.evaluators.llm_judge import run_checklist_evaluation
from prompt_evaluator.evaluators.rule_based import (
    keyword_inclusion,
    forbidden_word_check,
)
from prompt_evaluator.models import get_judge_llm


# =============================================================================
# LangSmith 어댑터
# =============================================================================


def create_langsmith_keyword_evaluator(expected_all: dict) -> Callable:
    """LangSmith용 키워드 포함 평가자."""

    def evaluator(run, example):
        from langsmith.evaluation import EvaluationResult

        output = run.outputs.get("output", "")
        case_id = example.metadata.get("case_id", "") if example.metadata else ""
        expected = expected_all.get(case_id, {})

        result = keyword_inclusion(output, expected.get("keywords", []))

        return EvaluationResult(
            key="keyword_inclusion",
            score=result["score"],
            comment=result["details"],
        )

    return evaluator


def create_langsmith_forbidden_evaluator(expected_all: dict) -> Callable:
    """LangSmith용 금지어 검사 평가자."""

    def evaluator(run, example):
        from langsmith.evaluation import EvaluationResult

        output = run.outputs.get("output", "")
        case_id = example.metadata.get("case_id", "") if example.metadata else ""
        expected = expected_all.get(case_id, {})

        result = forbidden_word_check(output, expected.get("forbidden", []))

        return EvaluationResult(
            key="forbidden_word_check",
            score=result["score"],
            comment=result["details"],
        )

    return evaluator


def create_langsmith_evaluator(
    criterion: str,
    prompt_template: str = "",
) -> Callable:
    """LangSmith용 LLM Judge 평가자."""

    def evaluator(run, example):
        from langsmith.evaluation import EvaluationResult

        output = run.outputs.get("output", "")
        inputs = example.inputs

        result = run_checklist_evaluation(
            output=output,
            inputs=inputs,
            prompt_template=prompt_template,
            criteria=[criterion],
        )

        criterion_result = result.get(criterion, {})

        return EvaluationResult(
            key=criterion,
            score=criterion_result.get("score", 0.0),
        )

    return evaluator


# =============================================================================
# Langfuse 어댑터
# =============================================================================


def create_langfuse_keyword_evaluator(expected_all: dict) -> Callable:
    """Langfuse용 키워드 포함 평가자."""

    def evaluator(*, output, expected_output, input, metadata, **kwargs):
        from langfuse import Evaluation

        text = output.get("output", "") if isinstance(output, dict) else str(output)
        case_id = metadata.get("case_id", "") if metadata else ""
        expected = expected_all.get(case_id, {})

        result = keyword_inclusion(text, expected.get("keywords", []))

        return Evaluation(
            name="keyword_inclusion",
            value=result["score"],
            comment=result["details"],
        )

    return evaluator


def create_langfuse_forbidden_evaluator(expected_all: dict) -> Callable:
    """Langfuse용 금지어 검사 평가자."""

    def evaluator(*, output, expected_output, input, metadata, **kwargs):
        from langfuse import Evaluation

        text = output.get("output", "") if isinstance(output, dict) else str(output)
        case_id = metadata.get("case_id", "") if metadata else ""
        expected = expected_all.get(case_id, {})

        result = forbidden_word_check(text, expected.get("forbidden", []))

        return Evaluation(
            name="forbidden_word_check",
            value=result["score"],
            comment=result["details"],
        )

    return evaluator


def create_langfuse_evaluator(
    criterion: str,
    prompt_template: str = "",
) -> Callable:
    """Langfuse용 LLM Judge 평가자."""

    def evaluator(*, output, expected_output, input, metadata, **kwargs):
        from langfuse import Evaluation
        from prompt_evaluator.utils.langfuse_client import get_langfuse_handler

        name = f"llm_judge_{criterion}"
        text = output.get("output", "") if isinstance(output, dict) else str(output)
        if not text:
            return Evaluation(name=name, value=0.0, comment="Empty output")

        judge_handler = get_langfuse_handler()
        bound_judge = get_judge_llm().with_config({"callbacks": [judge_handler]})
        try:
            results = run_checklist_evaluation(
                output=text,
                inputs=input,
                prompt_template=prompt_template,
                criteria=[criterion],
                llm=bound_judge,
            )
            if criterion in results:
                return Evaluation(name=name, value=results[criterion]["score"])
        except Exception as e:
            return Evaluation(name=name, value=0.0, comment=f"Error: {e}")

        return Evaluation(name=name, value=0.0, comment="Evaluation failed")

    evaluator.__name__ = f"llm_judge_{criterion}"
    return evaluator
