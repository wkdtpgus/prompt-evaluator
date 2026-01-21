"""Rule-based evaluators for prompt evaluation.

Rule-based 평가자: 빠르고 결정적인 평가를 위한 함수들
- LLM 호출 없이 로컬에서 즉시 실행
- quick 모드에서 기본 사용
"""

import json
import re
from typing import Any


def keyword_inclusion(
    output: str,
    expected_keywords: list[str],
    case_sensitive: bool = False
) -> dict[str, Any]:
    """출력에 기대 키워드가 포함되어 있는지 검사.

    Args:
        output: LLM 출력 텍스트
        expected_keywords: 포함되어야 할 키워드 목록
        case_sensitive: 대소문자 구분 여부

    Returns:
        {
            "score": float (0.0 ~ 1.0),
            "passed": bool,
            "found": list[str],
            "missing": list[str],
            "details": str
        }
    """
    if not expected_keywords:
        return {
            "score": 1.0,
            "passed": True,
            "found": [],
            "missing": [],
            "details": "No keywords to check"
        }

    check_output = output if case_sensitive else output.lower()
    found = []
    missing = []

    for keyword in expected_keywords:
        check_keyword = keyword if case_sensitive else keyword.lower()
        if check_keyword in check_output:
            found.append(keyword)
        else:
            missing.append(keyword)

    score = len(found) / len(expected_keywords) if expected_keywords else 1.0

    return {
        "score": score,
        "passed": score >= 0.5,  # 절반 이상 포함 시 통과
        "found": found,
        "missing": missing,
        "details": f"Found {len(found)}/{len(expected_keywords)} keywords"
    }


def forbidden_word_check(
    output: str,
    forbidden_words: list[str],
    case_sensitive: bool = False
) -> dict[str, Any]:
    """출력에 금지 단어가 포함되어 있는지 검사.

    Args:
        output: LLM 출력 텍스트
        forbidden_words: 포함되면 안 되는 단어 목록
        case_sensitive: 대소문자 구분 여부

    Returns:
        {
            "score": float (0.0 or 1.0),
            "passed": bool,
            "violations": list[str],
            "details": str
        }
    """
    if not forbidden_words:
        return {
            "score": 1.0,
            "passed": True,
            "violations": [],
            "details": "No forbidden words to check"
        }

    check_output = output if case_sensitive else output.lower()
    violations = []

    for word in forbidden_words:
        check_word = word if case_sensitive else word.lower()
        if check_word in check_output:
            violations.append(word)

    passed = len(violations) == 0

    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "violations": violations,
        "details": f"Found {len(violations)} forbidden words" if violations else "No violations"
    }


def length_compliance(
    output: str,
    min_length: int | None = None,
    max_length: int | None = None,
    unit: str = "chars"  # "chars" or "words"
) -> dict[str, Any]:
    """출력 길이가 허용 범위 내인지 검사.

    Args:
        output: LLM 출력 텍스트
        min_length: 최소 길이 (None이면 체크 안 함)
        max_length: 최대 길이 (None이면 체크 안 함)
        unit: "chars" (문자 수) 또는 "words" (단어 수)

    Returns:
        {
            "score": float (0.0 or 1.0),
            "passed": bool,
            "actual_length": int,
            "details": str
        }
    """
    if unit == "words":
        actual_length = len(output.split())
    else:
        actual_length = len(output)

    passed = True
    issues = []

    if min_length is not None and actual_length < min_length:
        passed = False
        issues.append(f"too short (min: {min_length})")

    if max_length is not None and actual_length > max_length:
        passed = False
        issues.append(f"too long (max: {max_length})")

    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "actual_length": actual_length,
        "details": f"Length: {actual_length} {unit}" + (f" - {', '.join(issues)}" if issues else "")
    }


def format_validity(
    output: str,
    expected_format: str = "json",
    schema: dict | None = None
) -> dict[str, Any]:
    """출력이 기대 포맷(JSON 등)을 따르는지 검사.

    Args:
        output: LLM 출력 텍스트
        expected_format: "json" 또는 "yaml"
        schema: JSON 스키마 (선택, 기본 검증만)

    Returns:
        {
            "score": float (0.0 or 1.0),
            "passed": bool,
            "parsed": Any (파싱된 데이터, 실패 시 None),
            "details": str
        }
    """
    if expected_format == "json":
        try:
            # JSON 블록 추출 시도 (```json ... ``` 형식)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', output)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = output.strip()

            parsed = json.loads(json_str)

            # 스키마 검증 (간단한 필드 존재 여부만)
            if schema and "required_fields" in schema:
                missing_fields = []
                for field in schema["required_fields"]:
                    if field not in parsed:
                        missing_fields.append(field)

                if missing_fields:
                    return {
                        "score": 0.5,
                        "passed": False,
                        "parsed": parsed,
                        "details": f"Missing required fields: {missing_fields}"
                    }

            return {
                "score": 1.0,
                "passed": True,
                "parsed": parsed,
                "details": "Valid JSON format"
            }

        except json.JSONDecodeError as e:
            return {
                "score": 0.0,
                "passed": False,
                "parsed": None,
                "details": f"Invalid JSON: {str(e)}"
            }

    return {
        "score": 0.0,
        "passed": False,
        "parsed": None,
        "details": f"Unsupported format: {expected_format}"
    }


def exact_match(
    output: str,
    reference: str,
    normalize: bool = True
) -> dict[str, Any]:
    """출력이 참조 값과 정확히 일치하는지 검사.

    Args:
        output: LLM 출력 텍스트
        reference: 기대되는 정확한 값
        normalize: 공백/줄바꿈 정규화 여부

    Returns:
        {
            "score": float (0.0 or 1.0),
            "passed": bool,
            "details": str
        }
    """
    if normalize:
        # 공백 정규화: 연속 공백 → 단일 공백, 앞뒤 공백 제거
        norm_output = " ".join(output.split())
        norm_reference = " ".join(reference.split())
    else:
        norm_output = output
        norm_reference = reference

    passed = norm_output == norm_reference

    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "details": "Exact match" if passed else "Not an exact match"
    }


def run_rule_evaluators(
    output: str,
    expected: dict[str, Any],
    checks: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    """여러 rule-based 평가자를 한 번에 실행.

    Args:
        output: LLM 출력 텍스트
        expected: expected.json의 해당 케이스 데이터
            - keywords: list[str]
            - forbidden: list[str]
            - reference: dict (선택)
        checks: 실행할 평가자 목록 (None이면 모두 실행)

    Returns:
        {
            "keyword_inclusion": {...},
            "forbidden_word_check": {...},
            ...
        }
    """
    default_checks = ["keyword_inclusion", "forbidden_word_check", "format_validity"]
    checks = checks or default_checks

    results = {}

    if "keyword_inclusion" in checks:
        results["keyword_inclusion"] = keyword_inclusion(
            output=output,
            expected_keywords=expected.get("keywords", [])
        )

    if "forbidden_word_check" in checks:
        results["forbidden_word_check"] = forbidden_word_check(
            output=output,
            forbidden_words=expected.get("forbidden", [])
        )

    if "format_validity" in checks:
        results["format_validity"] = format_validity(
            output=output,
            expected_format="json",
            schema={"required_fields": ["question_context"]}
        )

    if "length_compliance" in checks:
        results["length_compliance"] = length_compliance(
            output=output,
            min_length=10,
            max_length=5000
        )

    if "exact_match" in checks and "reference" in expected:
        # reference가 있을 때만 exact_match 실행
        results["exact_match"] = exact_match(
            output=output,
            reference=json.dumps(expected["reference"], ensure_ascii=False)
        )

    return results
