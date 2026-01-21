---
name: ab-compare
description: 두 프롬프트 버전을 A/B 비교 평가합니다. "프롬프트 비교", "A/B 테스트", "XML vs Markdown" 요청 시 사용하세요.
argument-hint: "[비교 대상]"
---

# 프롬프트 A/B 비교 평가기

두 프롬프트 버전(A vs B)을 비교 평가하기 위한 기준을 생성합니다.

## Overview

프롬프트 변형 실험 시 어떤 버전이 더 좋은지 판단하기 위한 평가 프레임워크를 제공합니다.

**사용 사례:**
- XML 태그 vs Markdown 포맷 비교
- Few-shot 예시 개수 비교 (3개 vs 5개)
- 지시문 스타일 비교 (상세 vs 간결)
- 프롬프트 구조 변경 전/후 비교

## When to Use

- 프롬프트 포맷을 변경하고 어떤 게 나은지 알고 싶을 때
- 프롬프트 최적화 실험을 진행할 때
- 동일한 태스크에 대해 두 가지 접근법을 비교할 때

## Core Concepts

### 비교 평가의 원칙

1. **동일 입력**: 두 버전에 같은 테스트 케이스 사용
2. **블라인드 평가**: 어떤 게 A인지 B인지 모르게
3. **다차원 평가**: 단일 점수가 아닌 여러 차원에서 비교
4. **통계적 유의성**: 충분한 케이스로 판단

### 비교 차원

| 차원 | 설명 | 측정 방법 |
|-----|------|----------|
| **Task Completion** | 태스크를 완수했는가 | Pass/Fail |
| **Output Quality** | 출력 품질이 더 좋은가 | A > B, A = B, A < B |
| **Format Adherence** | 지정 포맷을 잘 따르는가 | 0-1 점수 |
| **Consistency** | 여러 케이스에서 일관성 있는가 | 분산 측정 |
| **Edge Case Handling** | 예외 케이스를 잘 처리하는가 | Pass/Fail |

## Instructions

### Step 1: 비교 대상 파악

사용자가 비교하려는 두 프롬프트를 확인합니다:

```
프롬프트 A: {첫 번째 버전 - 예: XML 태그 방식}
프롬프트 B: {두 번째 버전 - 예: Markdown 방식}
```

**차이점 분석:**
- 구조적 차이 (포맷, 섹션 구성)
- 내용적 차이 (지시문 표현, 예시)
- 컨텍스트 제공 방식 차이

### Step 2: 비교 가설 설정

어떤 차원에서 차이가 날 것으로 예상되는지 가설을 세웁니다:

```
가설 1: XML 태그가 구조화된 출력에서 더 정확할 것이다
가설 2: Markdown이 자연어 응답에서 더 자연스러울 것이다
가설 3: XML이 중첩 구조 파싱에서 에러가 적을 것이다
```

### Step 3: 평가기준 생성

**비교 평가용 프롬프트 템플릿:**

```python
"{comparison_name}": """You are comparing two AI outputs for the same task.

## Task Description
{태스크 설명}

## Input (same for both):
{input}

## Output A:
{output_a}

## Output B:
{output_b}

## Comparison Checklist - For each item, choose: A_better, B_better, or Equal

1. **Task Completion**: Which output better completes the required task?
2. **Accuracy**: Which output is more accurate/correct?
3. **Format Compliance**: Which output better follows the required format?
4. **Clarity**: Which output is clearer and easier to understand?
5. **Completeness**: Which output is more complete without unnecessary content?

## Response Format (JSON):
{{
    "comparisons": {{
        "task_completion": "A_better" | "B_better" | "Equal",
        "accuracy": "A_better" | "B_better" | "Equal",
        "format_compliance": "A_better" | "B_better" | "Equal",
        "clarity": "A_better" | "B_better" | "Equal",
        "completeness": "A_better" | "B_better" | "Equal"
    }},
    "winner": "A" | "B" | "Tie",
    "confidence": "high" | "medium" | "low",
    "reasoning": "explanation of the comparison"
}}"""
```

### Step 4: 테스트 케이스 설계

비교를 위한 테스트 케이스 유형:

| 유형 | 설명 | 예시 |
|-----|------|-----|
| **Normal Case** | 일반적인 입력 | 표준 질문/데이터 |
| **Edge Case** | 경계 조건 | 빈 입력, 긴 입력 |
| **Stress Case** | 복잡한 입력 | 중첩 구조, 특수문자 |
| **Ambiguous Case** | 모호한 입력 | 해석이 여러 가지인 경우 |

## Example: XML vs Markdown 비교

### 비교 대상

**프롬프트 A (XML):**
```
<instruction>
다음 텍스트를 분석하세요.
</instruction>

<input>
{user_input}
</input>

<output_format>
JSON으로 응답
</output_format>
```

**프롬프트 B (Markdown):**
```
## Instruction
다음 텍스트를 분석하세요.

## Input
{user_input}

## Output Format
JSON으로 응답
```

### 생성된 비교 평가기준

```python
COMPARISON_PROMPTS = {
    "xml_vs_markdown_structure": """You are comparing XML-tagged vs Markdown-formatted prompt outputs.

## Task: Text analysis with JSON output

## Input (same for both):
{input}

## Output A (from XML prompt):
{output_a}

## Output B (from Markdown prompt):
{output_b}

## Comparison Checklist:

1. **JSON Validity**: Which output produces valid JSON more reliably?
2. **Field Completeness**: Which output includes all required fields?
3. **Boundary Handling**: Which better separates sections (no leakage)?
4. **Instruction Following**: Which follows the instructions more precisely?
5. **Robustness**: Which handles edge cases (empty input, special chars) better?

## Response Format (JSON):
{{
    "comparisons": {{
        "json_validity": "A_better" | "B_better" | "Equal",
        "field_completeness": "A_better" | "B_better" | "Equal",
        "boundary_handling": "A_better" | "B_better" | "Equal",
        "instruction_following": "A_better" | "B_better" | "Equal",
        "robustness": "A_better" | "B_better" | "Equal"
    }},
    "winner": "A" | "B" | "Tie",
    "win_count": {{"A": n, "B": m, "Equal": k}},
    "recommendation": "Use A/B when...",
    "reasoning": "detailed explanation"
}}"""
}
```

## Output: 비교 결과 해석

### 집계 방법

```python
# 여러 테스트 케이스 결과 집계
results = {
    "A_wins": 12,
    "B_wins": 8,
    "Ties": 5,
    "total": 25
}

# 차원별 승률
dimension_results = {
    "json_validity": {"A": 15, "B": 7, "Equal": 3},
    "instruction_following": {"A": 10, "B": 12, "Equal": 3},
    ...
}
```

### 결론 도출

```
결론:
- 전체 승률: A가 48%, B가 32%, 동점 20%
- JSON 출력 정확도: A(XML)가 우세
- 지시 따르기: B(Markdown)가 약간 우세
- 권장: 구조화된 출력이 중요하면 XML, 자연어 응답이면 Markdown
```

## What to Avoid

- 단일 케이스로 결론 내리기 (최소 10+ 케이스 필요)
- 주관적 "느낌"으로 판단
- 한 차원만 보고 전체 판단
- A/B 순서 편향 (랜덤화 필요)

## Integration

비교 평가 결과는 다음과 연동:
- **datasets/**: 테스트 케이스 저장
- **results/**: 비교 결과 저장
- **LangSmith**: Experiment로 A/B 실험 추적

---

**Version**: 1.0.0
**Last Updated**: 2025-01-21
