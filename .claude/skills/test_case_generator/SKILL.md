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

### Step 1: 관련 파일 읽기

**필수 파일:**
```
targets/{프롬프트명}_prompt.txt   # 프롬프트 템플릿
targets/schemas.py               # Pydantic 스키마 (입출력 타입 정의)
configs/{프롬프트명}.yaml         # 평가 설정
```

**프롬프트에서 파악할 것:**
- 프롬프트가 요구하는 입출력 관계
- 특수 케이스 처리 방식

**schemas.py에서 파악할 것:**
- Input 모델: 입력 필드, 타입, 필수/선택, enum 값
- Output 모델: 출력 필드, 타입, 필수/선택
- Field description으로 각 필드의 의미 파악

**configs/{name}.yaml에서 파악할 것:**
- `evaluators`: 어떤 평가자가 사용되는지 (keywords, forbidden 필요 여부)
- `eval_prompts_domain`: LLM Judge 도메인

### Step 2: test_cases.json 생성

**schemas.py의 Input 모델을 참조하여 생성:**

예시) `PrepOutputInput` 스키마가 있다면:
```python
class PrepOutputInput(BaseModel):
    chat_history: List[Dict] = Field(default=[], description="챗봇 대화 기록")
    survey_answers: Optional[Dict] = Field(default=None, description="서베이 응답")
    language: Literal["ko-KR", "en-US", "vi-VN"] = Field(default="ko-KR")
    member_name: str = Field(default="멤버")
```

이를 기반으로 테스트 케이스 생성:
```json
[
  {
    "id": "case_001",
    "description": "정상 케이스 - 상세 대화 기록",
    "inputs": {
      "chat_history": [
        {"role": "ai", "content": "최근 업무는 어떠세요?"},
        {"role": "human", "content": "프로젝트가 많아서 바쁘지만 보람있어요"}
      ],
      "survey_answers": {"condition": "GOOD", "topic": "WORK"},
      "language": "ko-KR",
      "member_name": "김철수"
    }
  },
  {
    "id": "case_002",
    "description": "엣지 케이스 - 서베이만 있음",
    "inputs": {
      "chat_history": [],
      "survey_answers": {"condition": "BAD"},
      "language": "ko-KR",
      "member_name": "이영희"
    }
  }
]
```

**스키마 기반 케이스 설계:**
- 필수 필드는 항상 포함
- Optional 필드는 있는 경우 / 없는 경우 모두 테스트
- Literal/Enum 값은 각 옵션별 케이스 생성
- List 필드는 빈 배열 / 1개 / 여러 개 케이스 포함

### Step 3: expected.json 생성

**schemas.py의 Output 모델을 참조하여 기대값 정의:**

예시) `QuestionContext` 출력 스키마가 있다면:
```python
class QuestionContext(BaseModel):
    question_theme: str = Field(description="챗봇이 물어본 주제")
    response_quality: Literal["detailed", "brief", "avoided", "survey_only"]
    coaching_hint: str = Field(description="코칭/접근 힌트")
```

이를 기반으로 expected.json 생성:
```json
{
  "case_001": {
    "keywords": ["question_context", "coaching_hint", "detailed"],
    "forbidden": ["퇴사", "이직", "연봉"],
    "reference": {
      "question_context": [
        {
          "question_theme": "Work",
          "response_quality": "detailed",
          "coaching_hint": "업무 성과에 대해 구체적으로 인정하며 시작"
        }
      ]
    }
  },
  "case_002": {
    "keywords": ["survey_only"],
    "forbidden": ["퇴사"],
    "reference": {}
  }
}
```

**필드 설명:**
| 필드 | 설명 | 필수 | 용도 |
|-----|------|:----:|------|
| `keywords` | 출력에 반드시 포함되어야 할 키워드 | O | keyword_inclusion 평가 |
| `forbidden` | 출력에 포함되면 안 되는 단어 | O | forbidden_word_check 평가 |
| `reference` | 정답 참조 출력 (Output 스키마 구조 따름) | X | embedding/string 유사도 평가 |

**reference 필드 참고:**
- `reference`는 **선택 사항**입니다
- 빈 객체 `{}`로 두거나 생략하면 유사도 평가가 스킵됩니다
- LLM 출력이 다양할 수 있는 경우 `reference`를 비워두고, LLM Judge로만 평가하는 것을 권장합니다

### Step 4: 케이스 유형 균형

| 유형 | 설명 | 개수 |
|-----|------|------|
| Normal | 일반적인 정상 입력 | 5-7개 |
| Edge | 빈 값, 경계값, 특수문자 | 3-5개 |
| Stress | 긴 입력, 많은 항목 | 2-3개 |

**총 10-15개 권장**

### Step 5: 파일 직접 생성 (필수!)

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

## expected.json 작성 가이드

### keywords 선정 기준
- 프롬프트가 명시적으로 요구하는 출력 키워드
- 도메인 특화 용어 (예: 1on1 → "coaching", "feedback")
- 입력에서 반드시 반영되어야 할 핵심 단어

### forbidden 선정 기준
- 민감한 주제 직접 언급 (예: "퇴사", "연봉", "이직")
- 부정적/판단적 표현 (예: "문제가 있다", "잘못된")
- 프롬프트가 금지하는 표현

### reference 작성 기준
- 이상적인 출력의 핵심 부분만 포함
- 전체 출력이 아닌 평가에 필요한 부분만
- 빈 객체 `{}`도 허용 (유사도 평가 스킵)

## What to Avoid

- JSON만 보여주고 파일을 생성하지 않는 것 (반드시 Write 도구 사용!)
- `test_cases.json`만 만들고 `expected.json`을 빠뜨리는 것
- 너무 많은 케이스 (15개 초과)
- 중복 시나리오
- 실제로 발생하지 않을 비현실적 데이터
- JSON 문법 오류 (주석, trailing comma 등)
- case_id 불일치 (test_cases와 expected의 id가 다른 경우)

---

**Version**: 2.0.0
**Last Updated**: 2026-01-22
