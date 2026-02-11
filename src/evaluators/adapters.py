"""LLM Judge 평가 결과를 LangSmith/Langfuse 플랫폼 형식으로 변환하는 어댑터."""

from typing import Callable

from langsmith.evaluation import EvaluationResult

from src.evaluators.llm_judge import run_checklist_evaluation
from utils.langfuse_client import get_langfuse_handler
from utils.models import judge_llm
from langfuse import Evaluation


def create_langsmith_evaluator(
    criterion: str,
    prompt_template: str = "",
) -> Callable:
    """LangSmith evaluate()용 평가자 함수 생성."""

    def evaluator(run, example) -> EvaluationResult:
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


def create_langfuse_evaluator(
    criterion: str,
) -> Callable:
    """Langfuse experiment용 평가자 함수 생성."""

    def evaluator(*, output, expected_output, input, metadata, **kwargs):
        name = f"llm_judge_{criterion}"
        text = output.get("output", "") if isinstance(output, dict) else str(output)
        if not text:
            return Evaluation(name=name, value=0.0, comment="Empty output")

        judge_handler = get_langfuse_handler()
        bound_judge = judge_llm.with_config({"callbacks": [judge_handler]})
        try:
            results = run_checklist_evaluation(
                output=text,
                inputs=input,
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
