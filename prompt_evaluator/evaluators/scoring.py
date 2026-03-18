"""pass/fail 판정 공통 로직.

pipeline.py, baseline.py 등에서 공유하는 점수 계산 및 통과 판정 함수.
"""

from prompt_evaluator.config import DEFAULT_KEYWORD_THRESHOLD, DEFAULT_PASS_THRESHOLD


def compute_pass_result(
    scores: dict,
    keyword_threshold: float = DEFAULT_KEYWORD_THRESHOLD,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> dict:
    """점수 딕셔너리에서 overall_score, sanity_passed, passed를 계산.

    Args:
        scores: 평가 점수 딕셔너리 (keyword_inclusion, forbidden_word_check, llm_judge_* 등)
        keyword_threshold: 키워드 점수 통과 기준 (기본값: config.DEFAULT_KEYWORD_THRESHOLD)
        pass_threshold: 전체 점수 통과 기준 (기본값: config.DEFAULT_PASS_THRESHOLD)

    Returns:
        {"overall_score": float|None, "sanity_passed": bool, "passed": bool}
    """
    llm_judge_scores = {k: v for k, v in scores.items() if k.startswith("llm_judge_")}
    overall_score = (
        sum(llm_judge_scores.values()) / len(llm_judge_scores)
        if llm_judge_scores
        else None
    )

    keyword_score = scores.get("keyword_inclusion", 1.0)
    forbidden_score = scores.get("forbidden_word_check", 1.0)
    sanity_passed = keyword_score >= keyword_threshold and forbidden_score == 1.0

    passed = sanity_passed and (
        overall_score is None or overall_score >= pass_threshold
    )

    return {
        "overall_score": overall_score,
        "sanity_passed": sanity_passed,
        "passed": passed,
    }
