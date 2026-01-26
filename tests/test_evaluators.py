"""Unit tests for evaluators."""

import json
import pytest
from src.evaluators.rule_based import (
    keyword_inclusion,
    forbidden_word_check,
    length_compliance,
    exact_match,
    run_rule_evaluators,
)


class TestKeywordInclusion:
    """keyword_inclusion 평가자 테스트."""

    def test_all_keywords_found(self):
        """모든 키워드가 포함된 경우."""
        output = "야근으로 인한 피로감과 휴가가 필요합니다. 컨디션 관리를 위해 지원이 필요합니다."
        keywords = ["야근", "피로", "휴가", "컨디션", "지원"]

        result = keyword_inclusion(output, keywords)

        assert result["score"] == 1.0
        assert result["passed"] is True
        assert len(result["found"]) == 5
        assert len(result["missing"]) == 0

    def test_partial_keywords_found(self):
        """일부 키워드만 포함된 경우."""
        output = "야근으로 피로합니다."
        keywords = ["야근", "피로", "휴가", "컨디션", "지원"]

        result = keyword_inclusion(output, keywords)

        assert result["score"] == 0.4  # 2/5
        assert result["passed"] is False
        assert set(result["found"]) == {"야근", "피로"}
        assert set(result["missing"]) == {"휴가", "컨디션", "지원"}

    def test_no_keywords(self):
        """키워드 목록이 비어있는 경우."""
        result = keyword_inclusion("아무 내용", [])

        assert result["score"] == 1.0
        assert result["passed"] is True

    def test_case_insensitive(self):
        """대소문자 무시 테스트."""
        output = "Leadership development is important"
        keywords = ["LEADERSHIP", "Development"]

        result = keyword_inclusion(output, keywords, case_sensitive=False)

        assert result["score"] == 1.0
        assert len(result["found"]) == 2


class TestForbiddenWordCheck:
    """forbidden_word_check 평가자 테스트."""

    def test_no_violations(self):
        """금지어가 없는 경우."""
        output = "업무 지원과 성장 기회에 대해 논의합니다."
        forbidden = ["퇴사", "이직", "연봉"]

        result = forbidden_word_check(output, forbidden)

        assert result["score"] == 1.0
        assert result["passed"] is True
        assert len(result["violations"]) == 0

    def test_has_violations(self):
        """금지어가 포함된 경우."""
        output = "이직을 고민 중이고 연봉에 불만이 있습니다."
        forbidden = ["퇴사", "이직", "연봉"]

        result = forbidden_word_check(output, forbidden)

        assert result["score"] == 0.0
        assert result["passed"] is False
        assert set(result["violations"]) == {"이직", "연봉"}

    def test_empty_forbidden_list(self):
        """금지어 목록이 비어있는 경우."""
        result = forbidden_word_check("아무 내용", [])

        assert result["score"] == 1.0
        assert result["passed"] is True


class TestLengthCompliance:
    """length_compliance 평가자 테스트."""

    def test_within_range(self):
        """길이가 범위 내인 경우."""
        output = "적절한 길이의 텍스트입니다."

        result = length_compliance(output, min_length=5, max_length=100)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_too_short(self):
        """길이가 너무 짧은 경우."""
        output = "짧음"

        result = length_compliance(output, min_length=10)

        assert result["passed"] is False
        assert "too short" in result["details"]

    def test_too_long(self):
        """길이가 너무 긴 경우."""
        output = "매우 긴 텍스트" * 100

        result = length_compliance(output, max_length=50)

        assert result["passed"] is False
        assert "too long" in result["details"]

    def test_word_count(self):
        """단어 수 기준 테스트."""
        output = "one two three four five"

        result = length_compliance(output, min_length=3, max_length=10, unit="words")

        assert result["passed"] is True
        assert result["actual_length"] == 5


class TestExactMatch:
    """exact_match 평가자 테스트."""

    def test_exact_match(self):
        """정확히 일치하는 경우."""
        result = exact_match("hello world", "hello world")

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_no_match(self):
        """일치하지 않는 경우."""
        result = exact_match("hello", "world")

        assert result["passed"] is False
        assert result["score"] == 0.0

    def test_normalized_match(self):
        """공백 정규화 후 일치."""
        result = exact_match("hello   world\n", "hello world")

        assert result["passed"] is True


class TestRunRuleEvaluators:
    """run_rule_evaluators 통합 테스트."""

    def test_full_evaluation(self):
        """전체 평가 실행."""
        output = json.dumps({
            "question_context": [
                {
                    "question_theme": "Work",
                    "response_quality": "detailed",
                    "coaching_hint": "야근으로 인한 피로감에 대해 지원 방안 논의"
                }
            ]
        }, ensure_ascii=False)

        expected = {
            "keywords": ["야근", "피로", "지원"],
            "forbidden": ["퇴사", "이직"],
            "reference": {"question_context": []}
        }

        results = run_rule_evaluators(output, expected)

        assert "keyword_inclusion" in results
        assert "forbidden_word_check" in results

        # 키워드 검사 통과
        assert results["keyword_inclusion"]["passed"] is True

        # 금지어 검사 통과
        assert results["forbidden_word_check"]["passed"] is True

    def test_selective_checks(self):
        """선택적 평가자 실행."""
        output = "테스트 출력"
        expected = {"keywords": ["테스트"]}

        results = run_rule_evaluators(
            output,
            expected,
            checks=["keyword_inclusion"]
        )

        assert "keyword_inclusion" in results
        assert "forbidden_word_check" not in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
