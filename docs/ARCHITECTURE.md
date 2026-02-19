# Prompt Evaluator 아키텍처

> **버전**: 1.5.0
> **최종 수정일**: 2026-02-19

---

## 1. 개요

LLM 프롬프트의 성능을 정량적으로 측정하고 지속적으로 개선하기 위한 평가 시스템입니다.
`pip install` 가능한 Python 패키지로, **LangSmith** 또는 **Langfuse**를 활용하여 데이터 기반 의사결정을 가능하게 합니다.

> **Note**: 기본값 `--backend both`로 두 플랫폼에서 동시에 실험 실행 및 모니터링 가능

### 1.1. 핵심 목표

- **정량적 지표 확보**: 프롬프트 성능을 점수화하여 객관적 판단
- **버전 관리 및 비교**: 프롬프트 수정 전후 성능 변화 비교
- **테스트 자동화**: 반복적인 테스트 과정 자동화
- **회귀 방지**: 프롬프트 변경 시 기존 성능 저하 자동 감지

### 1.2. 설계 원칙

1. **듀얼 백엔드 지원**: LangSmith + Langfuse 동시 운영, `backend` 파라미터로 선택
2. **패키지 = 평가 엔진만 제공**: 데이터(targets, datasets, eval_prompts)는 사용자 프로젝트에서 관리
3. **모듈화된 파이프라인**: 데이터만 교체하면 동일 파이프라인 재사용
4. **점진적 복잡도**: Rule-based → LLM-Judge 순서로 확장

### 1.3. 역할 분리

```
prompt-evaluator (pip install)        프로덕션 프로젝트 (.claude/skills/)
┌──────────────────────────┐          ┌─────────────────────────────┐
│ run_experiment()         │          │ 테스트케이스 생성 스킬      │
│ load_evaluation_set()    │          │ LLM Judge 기준 생성 스킬    │
│ run_checklist_eval()     │          │ A/B 비교 스킬              │
│ keyword_inclusion()      │          │                             │
│ forbidden_word_check()   │          │ → targets/, datasets/,      │
│                          │          │   eval_prompts/ 생성        │
└────────────┬─────────────┘          └──────────────┬──────────────┘
             │ 평가 실행                              │ 데이터 생성
             └─────────────────┬──────────────────────┘
                               ▼
                     프로덕션 프로젝트/
                     ├── targets/my_prompt/
                     ├── datasets/my_prompt/
                     ├── eval_prompts/my_domain/
                     └── results/
```

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

### 2.2. 프로젝트 구조

```
prompt-evaluator/
├── prompt_evaluator/           # pip install 대상 패키지
│   ├── __init__.py             # 공개 API
│   ├── context.py              # EvalContext (프로젝트 경로 설정)
│   ├── config.py               # 모델, 임계값 기본값
│   ├── models.py               # LLM 인스턴스
│   ├── schema.yaml             # config 스키마
│   ├── cli/                    # CLI 명령어 모듈
│   │   ├── __init__.py         # Typer app 정의 (entry point)
│   │   ├── scaffold.py         # init 명령어
│   │   ├── experiment.py       # experiment, regression 명령어
│   │   ├── config.py           # validate 명령어
│   │   ├── dataset.py          # list, upload 명령어
│   │   ├── prompt.py           # prompt 서브커맨드
│   │   └── baseline.py         # baseline 서브커맨드
│   ├── loaders/                # 데이터 로더
│   │   ├── dataset_loader.py
│   │   └── prompt_loader.py
│   ├── evaluators/             # 평가자
│   │   ├── rule_based.py       # Rule-based 평가
│   │   ├── llm_judge.py        # LLM-as-a-Judge 평가
│   │   ├── scoring.py          # 스코어링
│   │   ├── adapters.py         # LLM Judge 어댑터 (LangSmith/Langfuse 형식 변환)
│   │   └── eval_prompts/       # 번들 평가 기준
│   │       └── general/        # 범용 (instruction_following, factual_accuracy, output_quality)
│   ├── pipelines/              # 평가 파이프라인
│   │   ├── pipeline.py         # run_experiment(), execute_prompt()
│   │   └── runner.py           # PipelineRunner (E2E 파이프라인 모드)
│   ├── regression/             # 회귀 테스트
│   │   ├── baseline.py         # 기준선 관리
│   │   └── comparator.py       # 회귀 비교
│   ├── versioning/             # 버전 관리
│   │   └── prompt_metadata.py  # 프롬프트 메타데이터
│   ├── utils/                  # 유틸리티
│   │   ├── config_validator.py
│   │   ├── git.py
│   │   ├── dataset_sync.py     # 데이터셋 관리 (LangSmith + Langfuse 통합)
│   │   ├── prompt_sync.py      # 프롬프트 관리 (LangSmith + Langfuse 통합)
│   │   └── langfuse_client.py  # Langfuse 싱글톤 클라이언트
│   └── skills/                 # 번들 스킬 (init 시 .claude/skills/로 복사)
│       ├── test_case_generator/
│       ├── llm_judge_generator/
│       └── prompt_ab_comparator/
│
├── main.py                     # 개발용 CLI 진입점
├── pyproject.toml              # 패키지 설정
├── targets/                    # 평가 대상 프롬프트 (개발용)
├── datasets/                   # 테스트 데이터 (개발용)
├── eval_prompts/               # LLM Judge 평가 프롬프트 (개발용)
└── results/                    # 평가 결과 (개발용)
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
- `general/factual_accuracy`: 사실 정확성

**1on1 Meeting 특화 (`oneonone/`):**
- `oneonone/professional_tone`: 톤/어조 적절성
- `oneonone/sensitive_topic_handling`: 민감 주제 처리
- `oneonone/header_format`: 헤더 형식 준수
- `oneonone/section_count`: 섹션 개수 범위
- 외 다수

#### 실행 모드

| 모드 | 평가자 | 용도 |
|------|--------|------|
| `quick` | Rule-based만 | 개발 중 빠른 검증 |
| `full` | Rule + LLM Judge | 정식 평가 |

### 3.2. 평가 플랫폼 연동

#### LangSmith vs Langfuse 비교

| 항목 | LangSmith | Langfuse |
|------|-----------|----------|
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
| `both` (기본값) | Langfuse → LangSmith 순서로 동시 실행 | O (양쪽) |
| `langfuse` | Langfuse만 실행 | - |
| `langsmith` | LangSmith만 실행 | O |

#### 기능 제한사항

| 기능 | LangSmith | Langfuse |
|------|-----------|----------|
| 자동 트레이싱 | 환경변수만으로 활성화 | CallbackHandler 필요 |
| 프롬프트 Hub | 있음 | 없음 (자체 관리) |
| 실험 비교 UI | 내장 | 기본 제공 |

#### 통합 유틸리티 구조

모든 백엔드 연동은 `prompt_evaluator/utils/` 하위 모듈로 통합 관리됩니다:

```
prompt_evaluator/
├── utils/
│   ├── prompt_sync.py          # 프롬프트 업로드/조회 (LangSmith + Langfuse 통합)
│   ├── dataset_sync.py         # 데이터셋 업로드/조회 (LangSmith + Langfuse 통합)
│   └── langfuse_client.py      # Langfuse 싱글톤 클라이언트
├── evaluators/adapters.py      # LLM Judge 어댑터 (LangSmith/Langfuse 형식 변환)
└── pipelines/pipeline.py       # run_experiment(backend=...)
```

**통합 API 사용 예시:**

```python
from prompt_evaluator.utils.prompt_sync import push_prompt, get_prompt, list_prompt_versions

# 프롬프트 업로드 (backend 선택 가능)
result = push_prompt("my_prompt", backend="langfuse")       # Langfuse만
result = push_prompt("my_prompt", backend="both")           # 양쪽 동시

# 프롬프트 조회
template = get_prompt("my_prompt", backend="langfuse")

# 버전 목록 (LangSmith)
versions = list_prompt_versions("my_prompt")
```

```python
from prompt_evaluator.utils.dataset_sync import upload_dataset, get_dataset

# 데이터셋 업로드 (backend 선택 가능)
result = upload_dataset("my_prompt", backend="langfuse")    # Langfuse만
result = upload_dataset("my_prompt", backend="both")        # 양쪽 동시

# 데이터셋 조회 (Langfuse)
dataset = get_dataset("my_prompt")
```

```python
from prompt_evaluator.pipelines.pipeline import run_experiment

# 통합 실험 실행 (backend 파라미터로 선택)
run_experiment(
    prompt_name="my_prompt",
    mode="full",
    backend="langfuse",        # "langfuse" | "langsmith" | "both"
)
```

#### 트레이싱

모든 LLM 호출에 Langfuse 트레이싱이 적용됩니다:

- `pipelines/pipeline.py`: `execute_prompt()`에 `callbacks` 파라미터 (execution LLM 트레이싱)
- `evaluators/adapters.py`: Langfuse 어댑터에서 `judge_llm.with_config()`으로 callbacks 바인딩
- Langfuse 실험 시 `get_langfuse_handler()` 자동 생성

LLM Judge는 `llm` 파라미터 주입 방식으로 트레이싱합니다:

```python
# execution LLM: callbacks 파라미터로 전달
handler = get_langfuse_handler()
output = execute_prompt(template, inputs, callbacks=[handler])

# judge LLM: callbacks가 바인딩된 LLM 인스턴스를 주입
bound_judge = judge_llm.with_config({"callbacks": [handler]})
results = run_checklist_evaluation(output=text, inputs=input, llm=bound_judge)
```

#### 의사결정 방향성

**단기 (현재)**:
- **LangSmith + Langfuse 병행 운영**
  - `--backend both` 기본값으로 두 플랫폼 동시 실행
  - LangSmith의 직관적인 평가 UI + Langfuse의 셀프호스팅 장점 활용

**장기 (점진적 마이그레이션 후)**:
- **Langfuse 단독 사용**
  - 트레이싱 기능까지 완전 이전 후 LangSmith 비활성화
  - 상세 스코어링 로그 → 커스텀 리포트 생성

### 3.3. 프롬프트 버전 관리 (Phase 1)

> 상세: [features/versioning.md](./features/versioning.md)

- SHA256 해시 기반 자동 변경 감지
- 자동 버전 증가 (v1.0 → v1.1)
- `.metadata.yaml` 로컬 메타데이터 관리
- LangSmith/Langfuse 자동 push 연동
- `ChatPromptTemplate` 지원 (SYSTEM_PROMPT/USER_PROMPT 구분)
- git config 연동 (owner/author 자동 감지)

핵심 모듈: `prompt_evaluator/versioning/prompt_metadata.py`

### 3.4. 회귀 테스트 (Phase 2)

> 상세: [features/regression.md](./features/regression.md)

- 기준선(Baseline) 저장/로드/삭제
- RegressionReport 기반 버전 비교
- 회귀 판정 (pass_rate 5% 이상 하락)
- 개별 케이스 추적 (new_failures, fixed_cases)
- CI/CD 연동용 `--fail` 옵션
- Langfuse 소스: `--source langfuse`로 로컬 파일 없이 직접 비교

핵심 모듈: `prompt_evaluator/regression/baseline.py`, `comparator.py`

#### 회귀 테스트 기준

| 지표 | 허용 변동폭 | 조치 |
|------|:----------:|------|
| 평균 점수 | -0.2 이내 | 초과 시 머지 차단 |
| Pass Rate | -5% 이내 | 초과 시 경고 |
| 특정 케이스 실패 | Pass → Fail | 반드시 리뷰 필요 |

### 3.5. 패키지화

- `pip install` 가능한 패키지 구조 (`prompt_evaluator/`)
- `prompt-eval` CLI 엔트리 포인트
- `EvalContext` 기반 프로젝트 경로 관리 (`context.py`)
- `prompt-eval init` 명령으로 프로덕션 환경 초기화
- 번들 스킬 및 범용 평가 기준 포함

#### EvalContext — 프로젝트 경로 관리

```python
from prompt_evaluator import EvalContext, set_context, run_experiment

# 방법 1: 전역 컨텍스트 설정 (한 번만)
set_context(EvalContext(root="/app/evaluation"))
run_experiment("my_prompt", backend="langfuse")

# 방법 2: 함수 호출 시 직접 경로 지정 (기존 방식도 여전히 동작)
from prompt_evaluator import load_evaluation_set
data = load_evaluation_set("my_prompt", targets_dir="/app/prompts", datasets_dir="/app/data")
```

#### 경로 해석 우선순위

```
1. 함수 인자로 직접 전달된 경로 (최우선)
2. set_context()로 설정된 EvalContext
3. config.yaml 자동 탐색 (.prompt-eval/config.yaml → config.yaml)
4. 환경변수 PROMPT_EVAL_ROOT
5. CWD 기준 기본 컨벤션 (targets/, datasets/, ...)
```

#### 프로덕션 사용 워크플로우

```bash
# 0. 패키지 설치
pip install prompt-evaluator

# 1. 평가 환경 초기화 (한 번만 — config.yaml 생성됨)
prompt-eval init --dir .prompt-eval --targets-dir src/prompts

# 2. Claude Code에서 스킬로 데이터 생성
#    /gen-testcases chat_prompt  →  .prompt-eval/datasets/chat_prompt/ 생성
#    /eval-criteria chat_prompt  →  .prompt-eval/eval_prompts/chat/ 생성

# 3. 평가 실행 (경로는 config.yaml에서 자동 로드)
prompt-eval experiment --name chat_prompt --backend langfuse

# 4. 회귀 테스트
prompt-eval regression --name chat_prompt --source langfuse
```

#### 프로덕션 프로젝트 구조 (init 후)

```
my-app/
├── src/prompts/chat_prompt/prompt.py   # 프로덕션 프롬프트 (기존 위치 그대로)
├── .prompt-eval/                       # 평가 전용 (prompt-eval init 생성)
│   ├── config.yaml                     # 경로 설정 (이후 자동 로드)
│   ├── datasets/
│   ├── eval_prompts/
│   │   └── general/                    # 범용 평가 기준 (번들)
│   └── results/                        # gitignore 대상
├── .claude/
│   └── skills/                         # Claude Code 스킬 (자동 설치)
└── .gitignore                          # .prompt-eval/results/ 자동 추가
```

### 3.6. 파이프라인 모드 (E2E 평가)

프로덕션 코드의 실제 파이프라인 클래스를 통째로 호출하여 E2E 결과를 평가합니다.
`config.yaml`에 `pipeline:` 블록이 있으면 자동으로 파이프라인 모드로 전환됩니다.

| | 프롬프트 모드 | 파이프라인 모드 |
|---|---|---|
| **실행 대상** | 프롬프트 템플릿 + LLM 1회 호출 | 사용자 파이프라인 클래스 전체 |
| **프롬프트 관리** | 패키지가 로드/관리 | 프로덕션 코드 내부에서 자체 관리 |
| **필요 파일** | `prompt.*` + `config.yaml` | `config.yaml`만 (프롬프트 파일 불필요) |
| **용도** | 단일 프롬프트 품질 평가 | 다단계 파이프라인 E2E 평가 |

**pipeline config 필드:**

| 필드 | 필수 | 설명 |
|------|:----:|------|
| `module` | O | 파이프라인 클래스가 위치한 모듈의 dotted import path |
| `class` | O | 인스턴스화할 클래스 이름 |
| `method` | - | 호출할 메서드명. 미지정 시 `__call__()` 사용 |
| `input_model` | - | 입력 dict를 변환할 Pydantic 모델의 dotted path |
| `output_key` | - | 반환값이 dict/Pydantic 모델일 때 특정 필드만 추출 |
| `init_args` | - | 클래스 생성자에 전달할 키워드 인자. `${ENV_VAR}` 문법 지원 |

핵심 모듈: `prompt_evaluator/pipelines/runner.py`

### 3.7. GCP Langfuse 배포

#### 배포 아키텍처

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

---

## 4. 파일 형식

### 4.1. 프롬프트 파일 (targets/{name}/prompt.*)

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
name: my_prompt
description: 프롬프트 설명
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

thresholds:
  pass_rate: 0.85
  min_score: 0.70

run_mode: quick  # quick | full
```

---

## 5. CLI 명령어

```bash
# 패키지 설치 후
prompt-eval <command> [options]

# 또는 개발 시
poetry run python main.py <command> [options]
```

| 명령어 | 설명 |
|--------|------|
| `init --dir {dir} --targets-dir {path}` | 평가 환경 초기화 |
| `experiment --name {name}` | 평가 실행 (기본: Langfuse + LangSmith 동시) |
| `experiment --name {name} --backend {backend}` | 백엔드 지정 (langsmith/langfuse/both) |
| `regression --name {name} --source {source}` | 회귀 테스트 실행 (local/langfuse/langsmith) |
| `validate --name {name}` | config 검증 |
| `list` | 평가 세트 목록 |
| `upload --name {name}` | 데이터셋 업로드 |
| `prompt info/init/push/pull/versions/keys` | 프롬프트 버전 관리 |
| `baseline list/set/set-local/set-langfuse/delete` | 기준선 관리 |

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
  LangSmith/            실패 케이스 분석
  Langfuse 기록
```

---

## 7. 비용 추정 (100개 테스트 기준)

| 구성요소 | 단가 | 100회 비용 |
|----------|:----:|:----------:|
| 타겟 LLM 호출 (GPT-4o) | ~$0.01/call | ~$1.00 |
| LLM-Judge (GPT-4o) | ~$0.01/call | ~$1.00 |
| Embedding (ada-002) | ~$0.0001/call | ~$0.01 |
| **총합** | | **~$2.00** |

---

## 8. 참고 문서

### 기능별 상세
- [버전 관리](./features/versioning.md) - 프롬프트 버전 추적
- [회귀 테스트](./features/regression.md) - 기준선 비교 및 성능 저하 감지
- [CLI 레퍼런스](./features/cli-reference.md) - 전체 CLI 명령어

### 가이드
- [사용 가이드](../prompt_evaluator/GUIDE.md) - 평가 체계 활용 방법

### 향후 계획
- [ROADMAP](./ROADMAP.md) - 미구현 항목 및 로드맵
