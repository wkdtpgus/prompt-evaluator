---
name: eval-criteria
description: 프롬프트의 LLM-as-Judge 평가기준을 생성합니다. "평가기준 만들어줘", "evaluator 생성", "체크리스트 만들어줘" 요청 시 사용하세요.
argument-hint: "[프롬프트명]"
---

# LLM Judge 평가기준 생성기

프롬프트를 분석하여 LLM-as-Judge 평가기준(Evaluator)을 자동으로 생성합니다.

## Overview

이 스킬은 LLM 프롬프트에서 품질 기준을 추출하고, 평가 프롬프트 파일을 **직접 생성**합니다.

**핵심 기능:**
- 프롬프트 패턴 분석 (AVOID, MUST, Format 등)
- 평가 차원 자동 분류
- `eval_prompts/{도메인}/` 폴더에 평가 프롬프트 파일 직접 생성
- `targets/{프롬프트명}/config.yaml` 설정 파일 직접 생성

**중요: 이 스킬은 파일을 직접 생성해야 합니다. 코드 블록만 보여주지 마세요.**

## When to Use

- 새로운 프롬프트의 평가기준을 빠르게 설정할 때
- LLM Judge criteria를 추가하고 싶을 때
- 프롬프트 품질 평가 체크리스트가 필요할 때

## Core Concepts

### 프롬프트 패턴 → 평가기준 매핑

| 프롬프트 패턴 | 추출되는 평가기준 |
|-------------|-----------------|
| AVOID / DO NOT / Never | "Does it avoid..." 체크리스트 |
| MUST / Always / Required | "Does it include..." 체크리스트 |
| Format / JSON / Structure | "Is the format correct..." 체크리스트 |
| Role / Persona 정의 | "Does it match the expected role..." 체크리스트 |
| Good/Bad Examples | 예시 기반 체크리스트 |

### 평가 차원 분류

1. **Content Quality**: 내용의 정확성, 관련성, 완전성
2. **Tone & Style**: 톤, 어조, 문체 적절성
3. **Format Compliance**: 출력 형식 준수
4. **Safety & Guidelines**: 금지사항 준수
5. **Task Alignment**: 태스크 목적 부합도
6. **Personalization**: 맥락/사용자 맞춤화

## Instructions

### Step 0: 도메인 컨텍스트 및 기존 평가 기준 파악 (중요!)

**반드시 다음 파일들을 먼저 읽어야 합니다.**

```
targets/{프롬프트명}/prompt.*   # .txt, .py, .xml, .md 지원
targets/{프롬프트명}/config.yaml  # 기존 설정이 있다면 참조
eval_prompts/{도메인명}/*.txt   # ⭐ 기존 도메인 평가 기준 (재사용 검토!)
```

**프롬프트에서 파악할 것:**
- **도메인**: 무엇을 위한 프롬프트인가? (1on1 미팅, 고객 응대, 코드 리뷰 등)
- **목적**: 이 프롬프트가 달성하려는 핵심 목표
- **"무엇이 아닌지"**: 프롬프트가 명시적으로 피하라고 하는 것
- **도메인 특화 용어**: 해당 분야에서만 쓰이는 개념

**⭐ 기존 평가 기준 재사용 원칙 (필수!):**

1. **먼저 기존 도메인 폴더 확인**
   ```bash
   ls eval_prompts/  # 어떤 도메인이 있는지 확인
   ls eval_prompts/{관련도메인}/  # 기존 평가 기준 확인
   ```

2. **재사용 vs 신규 생성 판단:**
   - **재사용**: 도메인 전체에 적용되는 범용 기준 (톤, 민감 주제 처리, 기본 품질 등)
   - **신규 생성**: 해당 프롬프트에만 특화된 기준 (특정 출력 포맷, 특수 로직 등)

3. **도메인 폴더 구조 이해:**
   ```
   eval_prompts/
   ├── oneonone/              # 1on1 도메인 범용 기준
   │   ├── tone_appropriateness.txt    # 재사용 가능
   │   ├── sensitive_topic_handling.txt # 재사용 가능
   │   └── coaching_quality.txt        # 재사용 가능
   └── meeting_prep/          # 특정 프롬프트 특화 기준
       ├── analyze_quality_classification.txt  # prep_output_analyze 전용
       └── questions_structure.txt             # prep_output_questions 전용
   ```

**예시**: 1on1 미팅 프롬프트라면
- 먼저 `eval_prompts/oneonone/` 폴더 확인
- `tone_appropriateness`, `sensitive_topic_handling` 등은 재사용
- 프롬프트 고유 출력 형식 검증만 신규 생성
- 목적: 구성원 지원, 관계 구축
- "무엇이 아닌지": 업무 현황 보고 회의가 아님

### Step 1: 프롬프트 분석

프롬프트에서 다음을 식별합니다:
1. 명시적 규칙 (AVOID, MUST)
2. 출력 형식 요구사항
3. Role/Persona 정의
4. 예시 (Good/Bad)
5. 암묵적 품질 기준
6. **도메인 특화 요구사항** (Step 0에서 파악한 컨텍스트 활용)

### Step 2: 평가기준 설계 (기존 기준 재사용 우선!)

**⭐ 재사용 체크리스트:**
1. 기존 도메인 평가 기준 중 재사용 가능한 것 목록화
2. 새로 만들어야 하는 것만 설계

**기존 기준 재사용 예시:**
```yaml
# config.yaml에서 여러 도메인의 기준 혼합 사용 가능
evaluators:
  - type: llm_judge
    criteria:
      # 기존 도메인(oneonone)에서 재사용
      - oneonone/tone_appropriateness
      - oneonone/sensitive_topic_handling
      # 새로 생성한 특화 기준
      - meeting_prep/analyze_quality_classification
```

**신규 생성 시 각 평가기준에 대해:**
- **evaluator_name**: snake_case 이름
- **한글 설명**: 무엇을 평가하는지
- **5개 체크리스트**: Yes/No로 판단 가능한 구체적 질문
- **저장 위치**: 범용 → 도메인 폴더, 특화 → 프롬프트별 폴더

### Step 3: 파일 직접 생성 (필수!)

**⚠️ 중요: Write 도구를 사용하여 파일을 직접 생성해야 합니다. 코드 블록만 보여주고 끝내지 마세요.**

**1. 평가 프롬프트 파일 생성**

Write 도구로 `eval_prompts/{도메인명}/{evaluator_name}.txt` 파일을 생성합니다.

- 도메인 폴더가 없으면 새로 생성됩니다
- 파일 내용은 아래 템플릿을 따릅니다

**⚠️ JSON 중괄호 이스케이프 필수!**

평가 프롬프트는 Python의 `template.format(input=..., output=...)`으로 실행됩니다.
따라서 **JSON 예시의 `{`, `}`는 반드시 `{{`, `}}`로 이스케이프**해야 합니다!

- `{input}`, `{output}` → 플레이스홀더이므로 그대로 유지
- JSON의 `{`, `}` → `{{`, `}}`로 이스케이프

```
You are evaluating: {평가 목적 영문 설명}

## Input:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **{Check1}**: {구체적 질문}?
2. **{Check2}**: {구체적 질문}?
3. **{Check3}**: {구체적 질문}?
4. **{Check4}**: {구체적 질문}?
5. **{Check5}**: {구체적 질문}?

## Response Format (JSON):
{{
    "checklist": {{
        "{check1_key}": 0 or 1,
        "{check2_key}": 0 or 1,
        "{check3_key}": 0 or 1,
        "{check4_key}": 0 or 1,
        "{check5_key}": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "reasoning": "brief explanation"
}}
```

**이스케이프 예시:**
```
# 잘못된 예 (KeyError 발생!)
{
    "checklist": {
        "item1": 0 or 1
    }
}

# 올바른 예
{{
    "checklist": {{
        "item1": 0 or 1
    }}
}}
```

**2. 설정 파일 생성 (또는 업데이트)**

Write 도구로 `targets/{프롬프트명}/config.yaml` 파일을 생성하거나 기존 파일에 criteria를 추가합니다.

**⭐ 여러 도메인의 평가 기준 혼합 사용:**
```yaml
# {프롬프트명} 평가 설정

name: {프롬프트명}
output_format: text  # text | json
eval_prompts_domain: {주_도메인명}  # 신규 생성 시 저장될 위치

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check

  - type: llm_judge
    enabled: true
    criteria:
      # 기존 도메인에서 재사용 (도메인/기준명 형식)
      - oneonone/tone_appropriateness
      - oneonone/sensitive_topic_handling
      # 주 도메인의 특화 기준 (기준명만)
      - {evaluator_name_1}
      - {evaluator_name_2}

thresholds:
  pass_rate: 0.85
  min_score: 0.70

run_mode: full
```

**criteria 경로 규칙:**
- `기준명` → `eval_prompts/{eval_prompts_domain}/기준명.txt`
- `도메인/기준명` → `eval_prompts/도메인/기준명.txt` (다른 도메인 재사용 시)

**체크리스트:**
- [ ] `eval_prompts/{도메인명}/` 폴더에 평가 프롬프트 파일 생성됨
- [ ] `targets/{프롬프트명}/config.yaml` 설정 파일 생성/업데이트됨
- [ ] 생성된 파일 경로를 사용자에게 알려줌

## What to Avoid

- 코드 블록만 보여주고 파일을 생성하지 않는 것 (반드시 Write 도구 사용!)
- **JSON 중괄호 이스케이프 누락** (`{` → `{{`, `}` → `}}` 필수!)
  - Python의 `.format()` 메서드가 `{...}`를 플레이스홀더로 인식하여 KeyError 발생
  - 예: `KeyError: '\n    "checklist"'` → JSON의 `{`가 이스케이프되지 않음
- **⭐ 기존 평가 기준 확인 없이 새로 생성하는 것**
  - 반드시 `eval_prompts/` 폴더의 기존 도메인 기준 먼저 확인
  - 재사용 가능한 범용 기준은 새로 만들지 않음
- 너무 많은 평가기준 생성 (신규 생성은 프롬프트당 2-4개 권장, 재사용 포함 시 더 많아도 OK)
- 모호한 체크리스트 항목 (Yes/No로 판단 불가능한 질문)
- 일반적인 평가기준 (프롬프트에 특화되지 않은 항목) → 기존 도메인 기준 재사용
- `{input}`, `{output}` placeholder 수정 (이것만 단일 중괄호 유지)

## Example

### 입력: 고객 응대 프롬프트

```
You are a friendly customer service agent.

MUST:
- Acknowledge the customer's feelings
- Offer a solution or next steps

AVOID:
- Blaming the customer
- Using technical jargon
- Being dismissive

Output in JSON format with "response" and "sentiment" fields.
```

### 출력: 생성된 평가기준

**1. 평가 프롬프트 파일: `eval_prompts/customer_service/customer_empathy.txt`**

```
You are evaluating customer service empathy quality.

## Input:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **Acknowledges Feeling**: Does it acknowledge the customer's emotion or frustration?
2. **No Blame**: Does it avoid blaming or criticizing the customer?
3. **Shows Understanding**: Does it demonstrate understanding of the customer's issue?
4. **Offers Solution**: Does it proactively offer a solution or next steps?
5. **Warm Tone**: Is the tone friendly and warm (not robotic)?

## Response Format (JSON):
{{
    "checklist": {{
        "acknowledges_feeling": 0 or 1,
        "no_blame": 0 or 1,
        "shows_understanding": 0 or 1,
        "offers_solution": 0 or 1,
        "warm_tone": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "reasoning": "brief explanation"
}}
```

**2. 평가 프롬프트 파일: `eval_prompts/customer_service/customer_clarity.txt`**

```
You are evaluating customer service response clarity.

## Input:
{input}

## AI's Output:
{output}

## Checklist - Score each item (0 or 1):

1. **No Jargon**: Does it avoid technical jargon or explain terms clearly?
2. **Clear Steps**: Are the next steps clearly stated?
3. **Concise**: Is the response concise without unnecessary information?
4. **Actionable**: Can the customer act on this response immediately?
5. **Format Correct**: Is the output in valid JSON with required fields?

## Response Format (JSON):
{{
    "checklist": {{
        "no_jargon": 0 or 1,
        "clear_steps": 0 or 1,
        "concise": 0 or 1,
        "actionable": 0 or 1,
        "format_correct": 0 or 1
    }},
    "score": <float 0-1, average of checklist>,
    "reasoning": "brief explanation"
}}
```

**3. 설정 파일: `targets/customer_service/config.yaml`**

```yaml
name: customer_service
output_format: text
eval_prompts_domain: customer_service

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check

  - type: llm_judge
    enabled: true
    criteria:
      - customer_empathy
      - customer_clarity

thresholds:
  pass_rate: 0.85
  min_score: 0.70

run_mode: full
```

## Integration

이 스킬로 생성된 파일들:

- **eval_prompts/{도메인명}/{evaluator_name}.txt**: 평가 프롬프트 파일 (새로 생성)
- **targets/{프롬프트명}/config.yaml**: 평가 설정 파일 (생성/업데이트)
- **LangSmith**: Experiment에서 평가 실행

**폴더 구조:**
```
eval_prompts/               # 평가 프롬프트 (LLM Judge용)
├── general/               # 범용 평가 기준
└── {도메인명}/            # 도메인 특화 평가 기준

targets/                   # 평가 대상 프롬프트
└── {프롬프트명}/
    ├── prompt.*           # 프롬프트 템플릿
    └── config.yaml        # 평가 설정
```

## Related Commands

```bash
# 사용 가능한 평가 기준 확인
poetry run python main.py criteria

# 설정 검증
poetry run python main.py validate --name {프롬프트명}

# 평가 실행
poetry run python main.py experiment --name {프롬프트명} --mode full
```

## Checklist (생성 전 확인)

- [ ] 타겟 프롬프트 파일을 먼저 읽었는가?
- [ ] **기존 도메인 평가 기준(`eval_prompts/`)을 확인했는가?** (필수!)
- [ ] 재사용 가능한 기존 기준을 파악했는가?
- [ ] 신규 생성이 필요한 기준만 설계했는가?
- [ ] **JSON 중괄호를 `{{`, `}}`로 이스케이프했는가?** (가장 중요!)
- [ ] `{input}`, `{output}` 플레이스홀더는 단일 중괄호로 유지했는가?
- [ ] Write 도구로 파일을 직접 생성했는가?
- [ ] config.yaml에 기존 기준 재사용 + 신규 기준을 추가했는가?

---

**Version**: 1.2.0
**Last Updated**: 2026-01-26
