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
- Write 도구로 `datasets/{name}_data/`에 직접 저장

**중요: 이 스킬은 파일을 직접 생성해야 합니다. JSON만 보여주지 마세요.**

## When to Use

- 새 프롬프트의 테스트 데이터가 필요할 때
- API 테스트용 샘플 JSON이 필요할 때
- 엣지 케이스 데이터 추가가 필요할 때

## Instructions

### Step 1: 관련 파일 읽기 (심층 분석)

**필수 파일:**
```
targets/{프롬프트명}_prompt.txt   # 프롬프트 템플릿
targets/schemas.py               # Pydantic 스키마 (입출력 타입 정의)
configs/{프롬프트명}.yaml         # 평가 설정
```

**기존 데이터 참조 (필수):**
```
datasets/*_data/                 # 같은 프로젝트의 다른 테스트 데이터
```
- 기존 데이터의 스타일, 용어, 시나리오 패턴을 파악
- 일관된 케이스 ID 형식 및 description 스타일 유지
- 동일 도메인의 다른 프롬프트 데이터가 있다면 반드시 참조

**프롬프트에서 파악할 것 (핵심!):**
- **금지 사항**: "~하지 마라", "~를 피하라" 등의 지시 → forbidden 설정에 반영
- **조건부 로직**: "~인 경우에만", "~가 있으면" 등 → 해당 조건별 테스트 케이스 생성
- **출력 요구사항**: 필수 포함 정보, 톤앤매너, 포맷 규칙
- **민감 주제 처리**: 어떤 주제를 어떻게 다뤄야 하는지

**schemas.py에서 파악할 것:**
- Input 모델: 입력 필드, 타입, 필수/선택, enum 값
- Output 모델: 출력 필드, 타입, 필수/선택
- Field description으로 각 필드의 의미 파악

**configs/{name}.yaml에서 파악할 것:**
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

**schemas.py의 Input 모델 + 시나리오를 결합하여 생성:**

```json
[
  {
    "id": "case_001",
    "description": "이탈 위험 - 퇴사 고민 암시",
    "inputs": {
      "chat_history": [
        {"role": "ai", "content": "요즘 어떠세요?"},
        {"role": "human", "content": "솔직히 요즘 다른 데 알아보고 있어요..."}
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
      "chat_history": [
        {"role": "ai", "content": "최근 상황은 어떠세요?"},
        {"role": "human", "content": "작년에 열심히 했는데 평가가 너무 낮았어요. 연봉도 거의 안 올랐고요."}
      ],
      "survey_answers": {"condition": "TIRED"},
      "language": "ko-KR",
      "member_name": "김보상"
    }
  }
]
```

**스키마 + 시나리오 기반 설계:**
- 필수 필드는 항상 포함
- Optional 필드는 시나리오에 맞게 있는/없는 경우 혼합
- Literal/Enum 값은 시나리오에 적합한 값 선택
- **프롬프트의 조건부 로직을 트리거하는 입력 포함**

### Step 4: expected.json 생성

**프롬프트 요구사항을 반영한 평가 기준:**

```json
{
  "case_001": {
    "keywords": ["이직", "커리어", "지원"],
    "forbidden": ["퇴사해라", "그만둬라", "다른 회사"],
    "reference": {}
  },
  "case_002": {
    "keywords": ["평가", "피드백", "성장"],
    "forbidden": ["연봉", "급여", "인상"],
    "reference": {}
  }
}
```

**필드 설명:**
| 필드 | 설명 | 필수 | 용도 |
|-----|------|:----:|------|
| `keywords` | 출력에 반드시 포함되어야 할 **콘텐츠** 키워드 | O | keyword_inclusion 평가 |
| `forbidden` | 출력에 포함되면 안 되는 단어 | O | forbidden_word_check 평가 |
| `reference` | 정답 참조 출력 (Output 스키마 구조 따름) | X | embedding/string 유사도 평가 |

### Step 5: keywords / forbidden 작성 가이드

#### keywords 선정 기준

**올바른 예시 (콘텐츠 키워드):**
```json
"keywords": ["커리어", "성장", "지원", "피드백"]
```

**잘못된 예시 (필드명):**
```json
"keywords": ["question_context", "coaching_hint", "response_quality"]
```

- 프롬프트가 해당 입력에 대해 출력해야 할 핵심 개념
- 도메인 특화 용어 (예: 1on1 → "코칭", "피드백", "성장")
- 입력에서 언급된 주제와 관련된 키워드
- **JSON 필드명이 아닌 실제 콘텐츠!**

#### forbidden 선정 기준

**프롬프트의 금지 규칙을 반영:**
```json
"forbidden": ["연봉", "급여", "퇴사해", "문제가 있다"]
```

- 프롬프트가 명시적으로 금지한 단어/표현
- 민감한 주제의 **직접적** 언급 (간접 언급은 허용될 수 있음)
- 부정적/판단적 표현

**프롬프트 분석 예시:**
```
프롬프트: "민감한 주제(연봉, 평가 등)는 직접 언급하지 말고
         우회적으로 다루세요"

→ forbidden: ["연봉", "급여", "평가 점수", "등급"]
```

### Step 6: 케이스 유형 균형

| 유형 | 설명 | 개수 |
|-----|------|------|
| 핵심 시나리오 | 도메인 특화 상황 (이탈, 불만, 갈등 등) | 6-8개 |
| 정상 흐름 | 일반적인 긍정/중립 상황 | 3-4개 |
| 엣지 케이스 | 빈 값, 최소 정보, 다국어 | 2-3개 |

**총 10-15개 권장**

### Step 7: 파일 직접 생성 (필수!)

**⚠️ 중요: Write 도구를 사용하여 두 파일을 모두 생성해야 합니다.**

1. `datasets/{프롬프트명}_data/` 폴더가 없으면 생성됨
2. Write 도구로 `test_cases.json` 파일 생성
3. Write 도구로 `expected.json` 파일 생성
4. 생성된 파일 경로를 사용자에게 알려줌

**저장 위치:**
```
datasets/{프롬프트명}_data/
├── test_cases.json   # 테스트 입력
└── expected.json     # 평가 기준
```

## Checklist (생성 전 확인)

- [ ] 프롬프트의 금지 사항을 파악했는가?
- [ ] 프롬프트의 조건부 로직을 트리거하는 케이스가 있는가?
- [ ] 기존 데이터의 스타일을 참조했는가?
- [ ] keywords가 필드명이 아닌 콘텐츠 키워드인가?
- [ ] forbidden이 프롬프트의 금지 규칙을 반영하는가?
- [ ] 핵심 시나리오(민감 주제, 갈등 등)가 포함되어 있는가?

## What to Avoid

- JSON만 보여주고 파일을 생성하지 않는 것 (반드시 Write 도구 사용!)
- `test_cases.json`만 만들고 `expected.json`을 빠뜨리는 것
- **keywords에 JSON 필드명을 넣는 것** (예: "question_context" ❌)
- 프롬프트 분석 없이 일반적인 테스트만 생성하는 것
- 기존 데이터 스타일을 무시하고 새 스타일로 작성하는 것
- 너무 많은 케이스 (15개 초과)
- 중복 시나리오
- 실제로 발생하지 않을 비현실적 데이터
- JSON 문법 오류 (주석, trailing comma 등)
- case_id 불일치 (test_cases와 expected의 id가 다른 경우)

---

**Version**: 2.1.0
**Last Updated**: 2026-01-22
