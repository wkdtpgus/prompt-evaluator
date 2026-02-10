# Prompt Evaluator 기능 명세서

> **버전**: 1.3.0
> **최종 수정일**: 2026-02-05

---

## 1. 개요

LLM 프롬프트의 성능을 정량적으로 측정하고 지속적으로 개선하기 위한 평가 시스템입니다.
**LangSmith** 또는 **Langfuse**를 활용하여 데이터 기반 의사결정을 가능하게 합니다.

> **Note**: 기본값 `--backend both`로 두 플랫폼에서 동시에 실험 실행 및 모니터링 가능

### 1.1. 핵심 목표

- **정량적 지표 확보**: 프롬프트 성능을 점수화하여 객관적 판단
- **버전 관리 및 비교**: 프롬프트 수정 전후 성능 변화 비교
- **테스트 자동화**: 반복적인 테스트 과정 자동화
- **회귀 방지**: 프롬프트 변경 시 기존 성능 저하 자동 감지

### 1.2. 설계 원칙

1. **듀얼 백엔드 지원**: LangSmith + Langfuse 동시 운영, `backend` 파라미터로 선택
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
        │   backend= 파라미터   │
        └──────────┬──────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  [Rule-based]          [LLM Judge]
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  [Langfuse 기록]       [LangSmith 기록]
  (셀프호스팅)           (클라우드)
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

criteria는 항상 `도메인/기준명` 전체 경로로 지정합니다 (예: `general/instruction_following`).

**일반 (`general/`):**
- `general/instruction_following`: 지시사항 준수도
- `general/output_quality`: 전반적 출력 품질

**1on1 Meeting 특화 (`oneonone/`):**
- `oneonone/professional_tone`: 톤/어조 적절성
- `oneonone/sensitive_topic_handling`: 민감 주제 처리
- `oneonone/header_format`: 헤더 형식 준수
- `oneonone/section_count`: 섹션 개수 범위
- 외 다수

### 3.2. 실행 모드

| 모드 | 평가자 | 용도 |
|------|--------|------|
| `quick` | Rule-based만 | 개발 중 빠른 검증 |
| `full` | Rule + LLM Judge | 정식 평가 |

### 3.3. 평가 플랫폼 연동

#### LangSmith

LangSmith는 LangChain 팀에서 제공하는 클라우드 기반 LLM observability 플랫폼입니다.

- **Dataset**: 테스트 케이스를 LangSmith에 업로드
- **Experiment**: 평가 실행 및 결과 기록
- **Prompt Hub**: 프롬프트 버전 관리
- **Tracing**: LLM 호출 추적/디버깅 (환경변수만으로 자동 활성화)

#### Langfuse

Langfuse는 LLM 애플리케이션을 위한 오픈소스 observability 플랫폼입니다.

| 기능 | 설명 |
|------|------|
| **트레이싱** | LLM 호출, 체인 실행, 도구 사용 등 전체 실행 흐름 추적 |
| **프롬프트 관리** | 버전 관리, 레이블(production 등), SDK 연동 |
| **데이터셋** | 테스트 케이스 관리, CSV 업로드, 버전 관리 |
| **평가 (Evaluation)** | LLM-as-Judge, 커스텀 평가자, 점수(Score) 기록 |
| **실험 (Experiments)** | 데이터셋 기반 평가 실행 및 결과 비교 |
| **Playground** | 프롬프트 테스트 및 반복 개선 |

#### LangSmith vs Langfuse 비교

| 항목 | LangSmith | Langfuse |
|------|-----------------|----------|
| **호스팅** | 클라우드 only | 셀프호스팅 가능 (오픈소스) |
| **비용** | 유료 (trace 기반 과금) | 셀프호스팅 시 무료 |
| **프롬프트 관리** | LangChain Hub | 자체 버전 관리 시스템 |
| **데이터셋** | `langsmith.evaluate()` | `langfuse.create_dataset()` |
| **평가 실행** | `evaluate()` 함수 | 데이터셋 실험 + `create_score()` |
| **LangChain 연동** | 네이티브 통합 | CallbackHandler 방식 |
| **트레이싱** | 자동 (환경변수) | CallbackHandler 또는 @observe |

#### 백엔드 선택

| 백엔드 | 설명 | 자동 버전관리 |
|--------|------|:-------------:|
| `both` (기본값) | Langfuse → LangSmith 순서로 동시 실행 | ✅ (양쪽) |
| `langfuse` | Langfuse만 실행 | - |
| `langsmith` | LangSmith만 실행 | ✅ |

#### 기능 제한사항

| 기능 | LangSmith | Langfuse |
|------|-----------|----------|
| 자동 트레이싱 | 환경변수만으로 활성화 | CallbackHandler 필요 |
| 프롬프트 Hub | 있음 | 없음 (자체 관리) |
| 실험 비교 UI | 내장 | 기본 제공 |

#### 통합 유틸리티 구조

모든 백엔드 연동은 `utils/` 하위 2개 모듈로 통합 관리됩니다:

```
utils/
├── prompt_sync.py          # 프롬프트 업로드/조회 (LangSmith + Langfuse 통합)
├── dataset_sync.py         # 데이터셋 업로드/조회 (LangSmith + Langfuse 통합)
├── eval_adapters.py        # LLM Judge 어댑터 (LangSmith/Langfuse 형식 변환)
└── langfuse_client.py      # Langfuse 싱글톤 클라이언트

src/
└── pipelines/pipeline.py   # run_experiment(backend=...)
```

**통합 API 사용 예시:**

```python
from utils.prompt_sync import push_prompt, get_prompt, list_prompt_versions

# 프롬프트 업로드 (backend 선택 가능)
result = push_prompt("my_prompt", backend="langfuse")       # Langfuse만
result = push_prompt("my_prompt", backend="both")           # 양쪽 동시

# 프롬프트 조회
template = get_prompt("my_prompt", backend="langfuse")

# 버전 목록 (LangSmith)
versions = list_prompt_versions("my_prompt")
```

```python
from utils.dataset_sync import upload_dataset, get_dataset

# 데이터셋 업로드 (backend 선택 가능)
result = upload_dataset("my_prompt", backend="langfuse")    # Langfuse만
result = upload_dataset("my_prompt", backend="both")        # 양쪽 동시

# 데이터셋 조회 (Langfuse)
dataset = get_dataset("my_prompt")
```

```python
from src.pipelines.pipeline import run_experiment

# 통합 실험 실행 (backend 파라미터로 선택)
run_experiment(
    prompt_name="my_prompt",
    mode="full",
    backend="langfuse",        # "langfuse" | "langsmith" | "both"
)
```

#### Langfuse 셀프호스팅 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                    Langfuse                         │
├─────────────────────────────────────────────────────┤
│  Web UI (port 3000)                                 │
├─────────────────────────────────────────────────────┤
│  PostgreSQL     │  ClickHouse     │  Redis          │
│  (트랜잭션)      │  (트레이스 저장) │  (큐/캐시)       │
└─────────────────────────────────────────────────────┘
```

#### GCP 클라우드 배포 아키텍처

로컬 Docker 환경의 Langfuse를 GCP에 배포하여 팀 공유 환경을 구축했습니다.

**채택: GCE 단일 VM + Docker Compose + Nginx 리버스 프록시**

```
                    http://34.64.193.193
                           │
┌──────────────────────────┼──────────────────────────┐
│  GCE VM: langfuse-vm (e2-standard-4, 서울)          │
│  Ubuntu 22.04 LTS / SSD 80GB                        │
│                          │                           │
│  Nginx (호스트, :80) ─── Basic Auth ──┐              │
│    /api/* → auth off                  │              │
│    /*     → auth required             │              │
│                          ↓            │              │
│  ┌─────────────────────────────────────────────┐    │
│  │  Docker Compose                              │    │
│  │  ┌────────────┐ ┌────────────┐               │    │
│  │  │ langfuse   │ │ langfuse   │               │    │
│  │  │  -web      │ │  -worker   │               │    │
│  │  │ (:3000)    │ │ (:3030)    │               │    │
│  │  └────────────┘ └────────────┘               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │    │
│  │  │PostgreSQL│ │ClickHouse│ │  Redis   │     │    │
│  │  │ (:5432)  │ │(:8123/   │ │ (:6379)  │     │    │
│  │  │          │ │  :9000)  │ │          │     │    │
│  │  └──────────┘ └──────────┘ └──────────┘     │    │
│  │  ┌──────────┐                                │    │
│  │  │  MinIO   │                                │    │
│  │  │(:9000/   │                                │    │
│  │  │  :9001)  │                                │    │
│  │  └──────────┘                                │    │
│  └─────────────────────────────────────────────┘    │
│  Volumes: postgres_data, clickhouse_data,            │
│           clickhouse_logs, minio_data                │
└──────────────────────────────────────────────────────┘
```

**인프라 구성:**

| 항목 | 설정 |
|------|------|
| GCP 프로젝트 | `thetimecollabo` |
| VM | `langfuse-vm` (e2-standard-4, 4 vCPU, 16GB RAM) |
| 리전 | `asia-northeast3` (서울) |
| OS | Ubuntu 22.04 LTS |
| 디스크 | SSD Persistent Disk 80GB |
| 고정 IP | `34.64.193.193` |
| 접근 제어 | Nginx Basic Auth (UI) + API Key (SDK) |

**Docker 리소스 요구사항:**

- PostgreSQL, ClickHouse, Redis 동시 실행
- 최소 8GB RAM 권장
- 디스크 공간: 10GB 이상

#### 트레이싱

모든 LLM 호출에 Langfuse 트레이싱이 적용됩니다:

- `src/pipelines/pipeline.py`: `execute_prompt()`에 `callbacks` 파라미터
- `src/evaluators/llm_judge.py`: `run_checklist_evaluation()`에 `callbacks` 파라미터
- `src/pipelines/e2e_chain.py`: `_run_e2e_chain()`에 `callbacks` 파라미터
- Langfuse 실험 시 `get_langfuse_handler()` 자동 생성 후 전달

```python
from langfuse.langchain import CallbackHandler

def execute_prompt(prompt_text: str, inputs: dict, trace_name: str = None):
    """프롬프트 실행 (Langfuse 트레이싱 포함)"""
    handler = CallbackHandler()

    result = execution_llm.invoke(
        prompt_text.format(**inputs),
        config={"callbacks": [handler]}
    )

    return result
```

#### 의사결정 방향성

**단기 (현재)**:
- **LangSmith + Langfuse 병행 운영**
  - `--backend both` 기본값으로 두 플랫폼 동시 실행
  - 프롬프트 테스트 시 양쪽 UI에서 모니터링
  - LangSmith의 직관적인 평가 UI + Langfuse의 셀프호스팅 장점 활용

**장기 (점진적 마이그레이션 후)**:
- **Langfuse 단독 사용**
  - 트레이싱 기능까지 완전 이전 후 LangSmith 비활성화
  - 상세 스코어링 로그 → 커스텀 리포트 생성
  - comment에 JSON 구조화 → API로 추출 → 별도 리포트/대시보드

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

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check

  - type: llm_judge
    enabled: true
    criteria:
      - general/instruction_following      # 항상 '도메인/기준명' 전체 경로
      - general/output_quality
      - oneonone/professional_tone

thresholds:
  pass_rate: 0.85
  min_score: 0.70

run_mode: quick  # quick | full
```

---

## 5. CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `experiment --name {name}` | 평가 실행 (기본: Langfuse + LangSmith 동시) |
| `experiment --name {name} --backend {backend}` | 백엔드 지정 (langsmith/langfuse/both) |
| `regression --name {name} --experiment {exp}` | 회귀 테스트 실행 |
| `validate --name {name}` | config 검증 |
| `list` | 평가 세트 목록 |
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
| Langfuse 통합 (Phase 2.5) | ✅ | 본 문서 Section 3.3 |
| CLI 모듈화 | ✅ | [cli-reference.md](./features/cli-reference.md) |
| 유틸리티 통합 (prompt_sync + dataset_sync) | ✅ | 본 문서 Section 3.3 |
| GCP 클라우드 배포 | 🔄 | 인프라/배포/보안 완료, 운영 남음 |

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
- [Langfuse 마이그레이션 계획](./langfuse-migration-plan.md) - Langfuse 통합 상세

### 가이드
- [사용 가이드](./GUIDE.md) - 평가 체계 활용 방법
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md) - LangSmith 연동 상세
- [PromptOps 기획서](./PROMPTOPS_PLAN.md) - 전체 로드맵
