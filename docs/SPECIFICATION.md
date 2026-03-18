# Prompt Evaluator 기능 명세서

> **버전**: 1.1.0
> **최종 수정일**: 2026-01-26

---

## 1. 개요

LLM 프롬프트의 성능을 정량적으로 측정하고 지속적으로 개선하기 위한 평가 시스템입니다.
LangSmith를 활용하여 데이터 기반 의사결정을 가능하게 합니다.

### 1.1. 핵심 목표

- **정량적 지표 확보**: 프롬프트 성능을 점수화하여 객관적 판단
- **버전 관리 및 비교**: 프롬프트 수정 전후 성능 변화 비교
- **테스트 자동화**: 반복적인 테스트 과정 자동화
- **회귀 방지**: 프롬프트 변경 시 기존 성능 저하 자동 감지

### 1.2. 설계 원칙

1. **LangSmith 기능 최대 활용**: 별도 인프라 없이 내장 기능 우선 사용
2. **모듈화된 파이프라인**: 데이터만 교체하면 동일 파이프라인 재사용
3. **점진적 복잡도**: Rule-based → LLM-Judge 순서로 확장

---

## 2. 시스템 구성

### 2.1. 데이터 흐름

```
[1. 평가 대상 프롬프트]              [2. 평가 데이터셋]
targets/{name}/prompt.*             datasets/{name}/
        │                                   │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌─────────────────────┐
        │   평가 파이프라인      │
        │   (pipeline.py)      │
        └──────────┬──────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  [Rule-based]          [LLM Judge]
        │                     │
        └──────────┬──────────┘
                   ▼
            [LangSmith 기록]
```

---

## 3. 핵심 기능

### 3.1. 평가자 (Evaluators)

| 유형 | 설명 | 비용 | 용도 |
|------|------|:----:|------|
| **Rule-based** | 키워드, 금지어, 포맷 검증 | 무료 | 필수 조건 체크 |
| **String Distance** | 문자열 편집 거리 | 무료 | 정답 유사도 |
| **Embedding Distance** | 벡터 유사도 | 저렴 | 의미적 유사도 |
| **LLM-as-Judge** | LLM 기반 평가 | 고비용 | 품질 판단 |

#### Rule-based 평가 항목

| 지표 | 설명 | 점수 |
|------|------|:----:|
| `keyword_inclusion` | 필수 키워드 포함 비율 | 0.0~1.0 |
| `forbidden_word_check` | 금지어 포함 여부 | 0 or 1 |

#### LLM Judge 평가 기준

**일반:**
- `instruction_following`: 지시사항 준수도
- `output_quality`: 전반적 출력 품질

**1on1 Meeting 특화:**
- `tone_appropriateness`: 톤/어조 적절성
- `sensitive_topic_handling`: 민감 주제 처리
- `header_format`: 헤더 형식 준수
- `section_count`: 섹션 개수 범위
- 외 다수

### 3.2. 실행 모드

| 모드 | 평가자 | 용도 |
|------|--------|------|
| `quick` | Rule-based만 | 개발 중 빠른 검증 |
| `full` | Rule + LLM Judge | 정식 평가 |

### 3.3. LangSmith 연동

- **Dataset**: 테스트 케이스를 LangSmith에 업로드
- **Experiment**: 평가 실행 및 결과 기록
- **Prompt Hub**: 프롬프트 버전 관리
- **Tracing**: LLM 호출 추적/디버깅

---

## 4. 파일 형식

### 4.1. 프롬프트 파일 (targets/{name}/prompt.*)

**지원 형식:**

| 형식 | 파일명 | 설명 |
|------|--------|------|
| `.txt` | `prompt.txt` | 단일 템플릿 텍스트 |
| `.md` | `prompt.md` | 마크다운 형식 |
| `.py` | `prompt.py` | Python 변수 (`*_PROMPT`) |
| `.xml` | `prompt.xml` | XML 구조 |

**예시 (.txt):**
```
당신은 {role}입니다.

사용자 질문: {query}
컨텍스트: {context}

위 정보를 바탕으로 답변해주세요.
```

### 4.2. 테스트 케이스 (datasets/{name}/test_cases.json)

```json
[
  {
    "id": "case_001",
    "description": "기본 흐름 테스트",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "환불 절차가 어떻게 되나요?",
      "context": "7일 이내 환불 가능"
    }
  }
]
```

### 4.3. 기대 결과 (datasets/{name}/expected.json)

```json
{
  "case_001": {
    "keywords": ["환불", "7일"],
    "forbidden": ["불가능", "안됩니다"],
    "reference": {}
  }
}
```

### 4.4. 평가 설정 (targets/{name}/config.yaml)

```yaml
name: prep_generate
description: 1on1 Prep Report 생성 프롬프트
output_format: text  # text | json
eval_prompts_domain: oneonone

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check

  - type: llm_judge
    enabled: true
    criteria:
      - instruction_following
      - output_quality
      - tone_appropriateness

thresholds:
  pass_rate: 0.85
  min_score: 0.70

run_mode: quick  # quick | full
```

---

## 5. CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `experiment --name {name}` | 평가 실행 (자동 버전 관리 포함) |
| `regression --name {name} --experiment {exp}` | 회귀 테스트 실행 |
| `validate --name {name}` | config 검증 |
| `list` | 평가 세트 목록 |
| `criteria` | 사용 가능한 평가 기준 |
| `upload --name {name}` | 데이터셋 LangSmith 업로드 |
| `prompt info/init/push/pull/versions` | 프롬프트 버전 관리 |
| `baseline list/set/delete` | 기준선 관리 |

> 상세 사용법은 [CLI 레퍼런스](./features/cli-reference.md) 참조

---

## 6. 평가 워크플로우

```
[1. 데이터셋 구축]
       │
       ▼
[2. 프롬프트 작성/수정] ◄─────────────────────┐
       │                                      │
       ▼                                      │
[3. 평가 실행] ─────► [4. 결과 분석] ─────► [5. 개선]
       │                    │
       ▼                    ▼
  LangSmith 기록      실패 케이스 분석
```

### 6.1. 회귀 테스트 기준

| 지표 | 허용 변동폭 | 조치 |
|------|:----------:|------|
| 평균 점수 | -0.2 이내 | 초과 시 머지 차단 |
| Pass Rate | -5% 이내 | 초과 시 경고 |
| 특정 케이스 실패 | Pass → Fail | 반드시 리뷰 필요 |

---

## 7. 비용 추정 (100개 테스트 기준)

| 구성요소 | 단가 | 100회 비용 |
|----------|:----:|:----------:|
| 타겟 LLM 호출 (GPT-4o) | ~$0.01/call | ~$1.00 |
| LLM-Judge (GPT-4o) | ~$0.01/call | ~$1.00 |
| Embedding (ada-002) | ~$0.0001/call | ~$0.01 |
| **총합** | | **~$2.00** |

---

## 8. 향후 계획

### 구현 완료

| 항목 | 상태 | 문서 |
|------|:----:|------|
| 프롬프트 버전 관리 (Phase 1) | ✅ | [versioning.md](./features/versioning.md) |
| 회귀 테스트 체계 (Phase 2) | ✅ | [regression.md](./features/regression.md) |
| CLI 모듈화 | ✅ | [cli-reference.md](./features/cli-reference.md) |

### 미구현 항목

| 항목 | 우선순위 | 상태 |
|------|:--------:|:----:|
| GitHub Actions CI/CD | P1 | 대기 |
| 실패 분석 리포트 (Phase 3) | P1 | 대기 |
| LLM 응답 캐싱 | P2 | 대기 |
| Human spot-check (Phase 4) | P2 | 대기 |
| Slack 알림 연동 | P3 | 대기 |

### 평가 체계 성숙도 로드맵

```
[현재] Stage 1: Bootstrap
├── 자동생성으로 빠른 시작
├── 기본 평가 기준으로 MVP 검증
└── 피드백 루프 구축

[다음] Stage 2: Curate
├── 실전 좋은/나쁜 출력 수집
├── Golden Dataset 점진적 구축
└── 자동생성 평가기준 검증 & 수정

[향후] Stage 3: Refine
├── 실전 데이터 기반 평가기준 재정의
├── Edge case 중심 테스트 강화
└── 도메인 전문가 리뷰 반영
```

---

## 9. 참고 문서

### 기능별 상세
- [버전 관리](./features/versioning.md) - 프롬프트 버전 추적
- [회귀 테스트](./features/regression.md) - 기준선 비교 및 성능 저하 감지
- [CLI 레퍼런스](./features/cli-reference.md) - 전체 CLI 명령어

### 가이드
- [사용 가이드](./GUIDE.md) - 평가 체계 활용 방법
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md) - LangSmith 연동 상세
- [PromptOps 기획서](./PROMPTOPS_PLAN.md) - 전체 로드맵
