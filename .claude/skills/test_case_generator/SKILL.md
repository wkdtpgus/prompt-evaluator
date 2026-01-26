---
name: gen-testcases
description: 프롬프트 평가용 테스트 케이스를 생성합니다. "테스트케이스 만들어줘", "데이터셋 생성", "평가 데이터 만들어줘" 요청 시 사용하세요.
argument-hint: "[프롬프트명]"
---

# 테스트케이스 생성기

프롬프트 평가를 위한 테스트 케이스와 기대 결과 JSON 데이터를 생성합니다.

## Overview

API 엔드포인트 테스트에 바로 사용할 수 있는 JSON 형태의 테스트 케이스와 평가 기준을 **직접 생성**합니다.

**핵심 목표:**
- `test_cases.json`: 테스트 입력 데이터
- `expected.json`: 평가 기준 (keywords, forbidden, reference)
- Write 도구로 `datasets/{name}/`에 직접 저장

**중요: 이 스킬은 파일을 직접 생성해야 합니다. JSON만 보여주지 마세요.**

## When to Use

- 새 프롬프트의 테스트 데이터가 필요할 때
- API 테스트용 샘플 JSON이 필요할 때
- 엣지 케이스 데이터 추가가 필요할 때

## Instructions

### Step 1: 관련 파일 읽기 (심층 분석)

**필수 파일 (우선순위 순):**
```
targets/{프롬프트명}/prompt.*      # 1순위: 프롬프트 템플릿 - 플레이스홀더 변수명 확인!
targets/{프롬프트명}/schemas.py    # 2순위: 타겟 폴더 내 스키마 (있으면 우선 참조)
targets/{프롬프트명}/config.yaml   # 평가 설정
```

**⚠️ 핵심: 입력 필드명 결정 방법**

테스트 케이스의 `inputs` 키는 **프롬프트 템플릿의 플레이스홀더 변수명**과 일치해야 합니다.
파이프라인에서 `template.format(**inputs)`로 실행되기 때문입니다.

**확인 순서:**
1. **prompt.py/prompt.txt의 `{변수명}` 패턴 확인** (최우선)
   ```python
   # 예: prompt.py
   USER_PROMPT = """
   **Q&A Pairs**: {qa_pairs}        # ← inputs에 "qa_pairs" 사용
   **Survey Answers**: {survey_answers}
   **Member Name**: {member_name}
   """
   ```

2. **타겟 폴더 내 schemas.py 확인** (데이터 구조/타입 참조)
   - 프롬프트 변수명과 스키마 필드명이 다를 수 있음!
   - 스키마는 데이터 구조와 타입 이해용으로 참조

**주의: 스키마 필드명 ≠ 프롬프트 변수명일 수 있음**
```python
# schemas.py                    # prompt.py
class Input(BaseModel):         USER_PROMPT = """
    chat_history: List[Dict]    {qa_pairs}      # 다른 이름!
```
→ 이 경우 `inputs`에는 `qa_pairs` 사용 (프롬프트 변수명 우선)

**기존 데이터 참조 (필수):**
```
datasets/*/                       # 같은 프로젝트의 다른 테스트 데이터
```
- 기존 데이터의 스타일, 용어, 시나리오 패턴을 파악
- 일관된 케이스 ID 형식 및 description 스타일 유지
- 동일 도메인의 다른 프롬프트 데이터가 있다면 반드시 참조

**프롬프트에서 파악할 것 (핵심!):**
- **플레이스홀더 변수명**: `{변수명}` 패턴 → inputs 키로 사용
- **금지 사항**: "~하지 마라", "~를 피하라" 등의 지시 → forbidden 설정에 반영
- **조건부 로직**: "~인 경우에만", "~가 있으면" 등 → 해당 조건별 테스트 케이스 생성
- **출력 요구사항**: 필수 포함 정보, 톤앤매너, 포맷 규칙
- **민감 주제 처리**: 어떤 주제를 어떻게 다뤄야 하는지

**타겟 폴더 내 schemas.py에서 파악할 것:**
- Input 모델: 입력 필드 구조, 타입, 필수/선택, enum 값
- Output 모델: 출력 필드, 타입, 필수/선택
- Field description으로 각 필드의 의미 파악
- **단, 필드명은 프롬프트 플레이스홀더와 다를 수 있으므로 주의**

**targets/{name}/config.yaml에서 파악할 것:**
- `evaluators`: 어떤 평가자가 사용되는지 (keywords, forbidden 필요 여부)
- `eval_prompts_domain`: LLM Judge 도메인

### Step 2: 시나리오 기반 케이스 설계 (우선)

**도메인 특화 시나리오를 먼저 정의하세요.**

일반적인 Normal/Edge/Stress 분류보다 **비즈니스 시나리오 기반**으로 설계:

예시 - 1on1 미팅 도메인:
| 시나리오 | 설명 | 우선순위 |
|---------|------|:--------:|
| 이탈 위험 감지 | 퇴사/이직 암시하는 대화 | 높음 |
| 보상 불만 | 평가/연봉 관련 불만 표현 | 높음 |
| 팀 갈등 | 동료/리더와의 갈등 상황 | 높음 |
| 성장 욕구 | 커리어 발전 관련 대화 | 중간 |
| 컨디션 저하 | 번아웃, 피로 신호 | 중간 |
| 긍정적 상황 | 좋은 성과, 만족 표현 | 낮음 |
| 최소 정보 | 대화 없이 서베이만 | 낮음 |

**각 시나리오별로 1-2개씩 케이스 생성**

### Step 3: test_cases.json 생성

**⚠️ 중요: inputs의 키는 반드시 프롬프트 플레이스홀더 변수명과 일치해야 함!**

먼저 프롬프트에서 플레이스홀더를 확인:
```python
# prompt.py 예시
USER_PROMPT = """
**Q&A Pairs**: {qa_pairs}           # ← "qa_pairs" 사용
**Survey Answers**: {survey_answers}
**Member Name**: {member_name}
**Language**: {language}
"""
```

**프롬프트 플레이스홀더 + 스키마 구조 + 시나리오를 결합하여 생성:**

```json
[
  {
    "id": "case_001",
    "description": "이탈 위험 - 퇴사 고민 암시",
    "inputs": {
      "qa_pairs": [
        {"bot_question": "요즘 어떠세요?", "member_response": "솔직히 요즘 다른 데 알아보고 있어요..."}
      ],
      "survey_answers": {"condition": "BAD", "topic": "CAREER"},
      "language": "ko-KR",
      "member_name": "김이직"
    }
  },
  {
    "id": "case_002",
    "description": "보상 불만 - 평가 결과 불만족",
    "inputs": {
      "qa_pairs": [
        {"bot_question": "최근 상황은 어떠세요?", "member_response": "작년에 열심히 했는데 평가가 너무 낮았어요."}
      ],
      "survey_answers": {"condition": "TIRED"},
      "language": "ko-KR",
      "member_name": "김보상"
    }
  }
]
```

**설계 원칙:**
- **inputs 키 = 프롬프트 플레이스홀더 변수명** (가장 중요!)
- 데이터 구조는 스키마 참조 (타입, 필수/선택, enum 값)
- 필수 플레이스홀더는 항상 포함
- Optional 필드는 시나리오에 맞게 있는/없는 경우 혼합
- **프롬프트의 조건부 로직을 트리거하는 입력 포함**

### Step 4: expected.json 생성

**기본 구조 (대부분의 케이스):**

```json
{
  "case_001": {
    "keywords": [],
    "forbidden": [],
    "reference": {}
  },
  "case_002": {
    "keywords": [],
    "forbidden": [],
    "reference": {}
  }
}
```

**분류 검증이 필요한 경우:**

```json
{
  "case_turnover_risk": {
    "keywords": ["Career"],
    "forbidden": [],
    "reference": {
      "expected_theme": "Career",
      "expected_response_quality": "detailed"
    }
  },
  "case_critical_expression": {
    "keywords": [],
    "forbidden": ["퇴사해", "그만둬"],
    "reference": {}
  }
}
```

**필드 설명:**
| 필드 | 설명 | 필수 | 기본값 |
|-----|------|:----:|:------:|
| `keywords` | 분류/태그 검증용 (프롬프트에 명시된 규칙이 있을 때만) | O | `[]` (빈 배열 권장) |
| `forbidden` | 출력에 포함되면 안 되는 **치명적** 단어만 | O | `[]` (빈 배열 권장) |
| `reference` | 정답 참조 (분류 정확성 검증용) | X | `{}` |

### Step 5: keywords / forbidden 작성 가이드

#### 기본 원칙: 대부분의 케이스는 빈 배열

**일반적인 케이스 (권장):**
```json
{
  "case_001": {
    "keywords": [],
    "forbidden": [],
    "reference": {}
  }
}
```

품질 평가는 **LLM Judge가 담당**하므로, 룰 기반 체크는 최소화합니다.

---

#### keywords를 사용하는 경우: 분류/태그 검증

**프롬프트에 정해진 분류 규칙이 있을 때만** keywords 사용:

```json
// 예: 프롬프트가 "theme은 Work/Career/Team Culture/Condition 중 하나" 명시
{
  "case_turnover_risk": {
    "keywords": ["Career"],  // 분류가 올바른지 검증
    "forbidden": [],
    "reference": {
      "expected_theme": "Career"
    }
  }
}
```

**keywords 사용 조건:**
| 조건 | 예시 | keywords |
|------|------|----------|
| 분류/태그 명시 | theme: Work/Career/... | `["Career"]` |
| 필수 패턴 | "반드시 ~를 포함" | 해당 패턴 |
| enum 값 검증 | response_quality: detailed/brief | `["detailed"]` |
| **그 외 일반** | 품질, 톤, 내용 적절성 | `[]` (빈 배열) |

**잘못된 예시:**
```json
// ❌ 프롬프트에 명시된 규칙 없이 콘텐츠 키워드 추가
"keywords": ["커리어", "성장", "지원", "피드백"]
// → LLM Judge가 평가할 영역
```

---

#### forbidden를 사용하는 경우: 치명적 표현만

**⚠️ 대부분 빈 배열 `[]` 사용!**

`forbidden`은 해당 단어가 있으면 **무조건 실패** 처리됩니다.

**forbidden 사용 조건:**
| 조건 | 예시 | forbidden |
|------|------|-----------|
| 프롬프트가 "절대 금지" 명시 | "퇴사 권유 절대 금지" | `["퇴사해", "그만둬"]` |
| 치명적 표현 | 욕설, 위협, 차별 | 해당 표현 |
| **그 외 모든 경우** | 톤, 뉘앙스, 간접 언급 | `[]` (빈 배열) |

**올바른 예시:**
```json
// 프롬프트: "멤버에게 퇴사를 권유하거나 위협하지 마세요"
"forbidden": ["퇴사해", "그만둬", "해고"]  // ✅ 직접적 권유만
```

**잘못된 예시:**
```json
// ❌ 너무 광범위 - 정상 출력도 실패
"forbidden": ["퇴사", "이직", "연봉", "급여"]
// → "이직 관련 고민이 있으시군요"도 실패 처리됨
```

---

#### 역할 분담 정리

| 검증 대상 | 방법 | 예시 |
|----------|------|------|
| 분류 정확성 | `keywords` + `reference` | theme, response_quality |
| 치명적 금지 표현 | `forbidden` | "퇴사해", "해고" |
| 톤/뉘앙스 | LLM Judge | 판단적 언어, 압박감 |
| 콘텐츠 품질 | LLM Judge | 맥락 적절성, 지원적 관점 |
| 민감 주제 처리 | LLM Judge | 간접 언급 허용 여부 |

### Step 6: 케이스 유형 균형

| 유형 | 설명 | 개수 |
|-----|------|------|
| 핵심 시나리오 | 도메인 특화 상황 (이탈, 불만, 갈등 등) | 6-8개 |
| 정상 흐름 | 일반적인 긍정/중립 상황 | 3-4개 |
| 엣지 케이스 | 빈 값, 최소 정보, 다국어 | 2-3개 |

**총 10-15개 권장**

### Step 7: 파일 직접 생성 (필수!)

**⚠️ 중요: Write 도구를 사용하여 두 파일을 모두 생성해야 합니다.**

1. `datasets/{프롬프트명}/` 폴더가 없으면 생성됨
2. Write 도구로 `test_cases.json` 파일 생성
3. Write 도구로 `expected.json` 파일 생성
4. 생성된 파일 경로를 사용자에게 알려줌

**저장 위치:**
```
datasets/{프롬프트명}/
├── test_cases.json   # 테스트 입력
└── expected.json     # 평가 기준
```

## Checklist (생성 전 확인)

- [ ] **프롬프트 플레이스홀더 `{변수명}`을 확인했는가?** (가장 중요!)
- [ ] **inputs 키가 프롬프트 플레이스홀더와 일치하는가?**
- [ ] 타겟 폴더 내 schemas.py로 데이터 구조를 확인했는가?
- [ ] 프롬프트의 금지 사항을 파악했는가?
- [ ] 프롬프트의 조건부 로직을 트리거하는 케이스가 있는가?
- [ ] 기존 데이터의 스타일을 참조했는가?
- [ ] **keywords가 빈 배열 `[]`인가?** (분류 검증 필요 시만 추가)
- [ ] **forbidden이 빈 배열 `[]`인가?** (치명적 표현만 예외적으로 추가)
- [ ] 핵심 시나리오(민감 주제, 갈등 등)가 포함되어 있는가?

## What to Avoid

- **프롬프트 플레이스홀더 확인 없이 스키마 필드명을 그대로 사용하는 것** (KeyError 발생!)
- **inputs 키와 프롬프트 `{변수명}` 불일치** (예: 스키마는 `chat_history`인데 프롬프트는 `{qa_pairs}` 사용)
- JSON만 보여주고 파일을 생성하지 않는 것 (반드시 Write 도구 사용!)
- `test_cases.json`만 만들고 `expected.json`을 빠뜨리는 것
- **keywords에 콘텐츠 키워드를 넣는 것** (분류/태그 검증 아니면 `[]` 사용)
  - ❌ `["커리어", "성장", "지원"]` - LLM Judge 영역
  - ✅ `[]` 또는 `["Career"]` - 분류 검증용만
- **forbidden에 너무 많은 단어를 넣는 것** (정상 출력도 실패 처리됨!)
  - ❌ `["퇴사", "이직", "연봉", "급여"]` - 너무 광범위
  - ✅ `[]` 또는 `["퇴사해", "그만둬"]` - 치명적 표현만
- 프롬프트 분석 없이 일반적인 테스트만 생성하는 것
- 기존 데이터 스타일을 무시하고 새 스타일로 작성하는 것
- 너무 많은 케이스 (15개 초과)
- 중복 시나리오
- 실제로 발생하지 않을 비현실적 데이터
- JSON 문법 오류 (주석, trailing comma 등)
- case_id 불일치 (test_cases와 expected의 id가 다른 경우)

---

**Version**: 2.4.0
**Last Updated**: 2026-01-26
