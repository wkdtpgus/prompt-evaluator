---
name: gen-testcases
description: 프롬프트 평가용 테스트 케이스를 생성합니다. "테스트케이스 만들어줘", "데이터셋 생성", "평가 데이터 만들어줘" 요청 시 사용하세요.
argument-hint: "[프롬프트명]"
---

# 테스트케이스 생성기

프롬프트 평가를 위한 테스트 케이스 JSON 데이터를 생성합니다.

## Overview

API 엔드포인트 테스트(Swagger UI 등)에 바로 사용할 수 있는 JSON 형태의 테스트 케이스를 **직접 생성**합니다.

**핵심 목표:**
- Swagger UI에서 복붙해서 바로 테스트 가능한 JSON
- 다양한 시나리오 커버 (정상, 엣지, 스트레스)
- Write 도구로 `datasets/{name}_data/test_cases.json`에 직접 저장

**중요: 이 스킬은 파일을 직접 생성해야 합니다. JSON만 보여주지 마세요.**

## When to Use

- 새 프롬프트의 테스트 데이터가 필요할 때
- API 테스트용 샘플 JSON이 필요할 때
- 엣지 케이스 데이터 추가가 필요할 때

## Instructions

### Step 1: 평가 대상 프롬프트 파일 읽기

```
targets/{프롬프트명}_prompt.txt
```

파악할 것:
- 입력 필드와 타입
- 필수/선택 필드 구분
- 값의 범위나 제약

### Step 2: JSON 테스트 케이스 생성

**Swagger UI에서 바로 사용 가능한 형태로 생성:**

```json
[
  {
    "id": "case_001",
    "description": "정상 케이스 - 기본 입력",
    "inputs": {
      "field1": "value1",
      "field2": ["item1", "item2"],
      "field3": {"key": "value"}
    }
  },
  {
    "id": "case_002",
    "description": "엣지 케이스 - 빈 배열",
    "inputs": {
      "field1": "value1",
      "field2": [],
      "field3": {}
    }
  }
]
```

### Step 3: 케이스 유형 균형

| 유형 | 설명 | 개수 |
|-----|------|------|
| Normal | 일반적인 정상 입력 | 5-7개 |
| Edge | 빈 값, 경계값, 특수문자 | 3-5개 |
| Stress | 긴 입력, 많은 항목 | 2-3개 |

**총 10-15개 권장**

## Output Format

`inputs` 필드는 API request body로 바로 사용 가능해야 함:

```json
{
  "id": "case_001",
  "description": "한글 설명",
  "inputs": {
    // Swagger UI에 복붙 가능한 JSON
  }
}
```

## Step 4: 파일 직접 생성 (필수!)

**⚠️ 중요: Write 도구를 사용하여 파일을 직접 생성해야 합니다. JSON만 보여주고 끝내지 마세요.**

1. `datasets/{프롬프트명}_data/` 폴더가 없으면 생성됨
2. Write 도구로 `test_cases.json` 파일 생성
3. 생성된 파일 경로를 사용자에게 알려줌

**저장 위치:**
```
datasets/{프롬프트명}_data/test_cases.json
```

## What to Avoid

- JSON만 보여주고 파일을 생성하지 않는 것 (반드시 Write 도구 사용!)
- 너무 많은 케이스 (15개 초과)
- 중복 시나리오
- 실제로 발생하지 않을 비현실적 데이터
- JSON 문법 오류 (주석, trailing comma 등)

---

**Version**: 1.1.0
**Last Updated**: 2025-01-21
