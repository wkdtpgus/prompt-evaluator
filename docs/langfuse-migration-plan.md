# Langfuse 마이그레이션 계획

## 개요

현재 LangSmith 기반의 프롬프트 평가 시스템을 Langfuse로 마이그레이션하여 셀프호스팅 환경에서 운영하기 위한 계획 문서입니다.

---

## 1. Langfuse 소개

Langfuse는 LLM 애플리케이션을 위한 오픈소스 observability 플랫폼입니다.

### 주요 기능

| 기능 | 설명 |
|------|------|
| **트레이싱** | LLM 호출, 체인 실행, 도구 사용 등 전체 실행 흐름 추적 |
| **프롬프트 관리** | 버전 관리, 레이블(production 등), SDK 연동 |
| **데이터셋** | 테스트 케이스 관리, CSV 업로드, 버전 관리 |
| **평가 (Evaluation)** | LLM-as-Judge, 커스텀 평가자, 점수(Score) 기록 |
| **실험 (Experiments)** | 데이터셋 기반 평가 실행 및 결과 비교 |
| **Playground** | 프롬프트 테스트 및 반복 개선 |

### 셀프호스팅 아키텍처

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

---

## 2. LangSmith vs Langfuse 비교

### 기능 비교

| 항목 | LangSmith (현재) | Langfuse |
|------|-----------------|----------|
| **호스팅** | 클라우드 only | 셀프호스팅 가능 (오픈소스) |
| **비용** | 유료 (trace 기반 과금) | 셀프호스팅 시 무료 |
| **프롬프트 관리** | LangChain Hub | 자체 버전 관리 시스템 |
| **데이터셋** | `langsmith.evaluate()` | `langfuse.create_dataset()` |
| **평가 실행** | `evaluate()` 함수 | 데이터셋 실험 + `create_score()` |
| **LangChain 연동** | 네이티브 통합 | CallbackHandler 방식 |
| **트레이싱** | 자동 (환경변수) | CallbackHandler 또는 @observe |

### 현재 프로젝트 LangSmith 사용 현황

```
utils/
├── langsmith_datasets.py    # 데이터셋 업로드
└── langsmith_prompts.py     # 프롬프트 저장소 연동

src/
└── pipeline.py              # run_langsmith_experiment()
```

---

## 3. 마이그레이션 범위

### 마이그레이션 대상 기능

| 현재 (LangSmith) | 마이그레이션 (Langfuse) |
|-----------------|----------------------|
| `langsmith.evaluate()` | Langfuse 데이터셋 + 실험 |
| 데이터셋 업로드 | `langfuse.create_dataset()` |
| 프롬프트 버전 관리 | `langfuse.create_prompt()` |
| 트레이싱 | `CallbackHandler` |

### 마이그레이션 대상 파일

```
수정 필요:
├── src/pipeline.py                    # 핵심 평가 파이프라인
├── utils/langsmith_datasets.py        # → utils/langfuse_datasets.py
├── utils/langsmith_prompts.py         # → utils/langfuse_prompts.py
└── .env                               # 환경변수 추가

신규 생성:
├── utils/langfuse_client.py           # Langfuse 클라이언트 설정
└── utils/langfuse_experiments.py      # 실험 실행 유틸리티
```

---

## 4. 단계별 마이그레이션 계획

### Phase 1: 로컬 서버 구축

**목표**: Docker로 Langfuse 서버 실행 및 UI 확인

```bash
# 1. Langfuse 저장소 클론
git clone https://github.com/langfuse/langfuse.git ~/langfuse
cd ~/langfuse

# 2. Docker Compose 실행
docker compose up -d

# 3. 접속 확인
# http://localhost:3000
```

**환경변수 설정** (.env 파일에 추가):

```bash
# Langfuse (로컬)
LANGFUSE_SECRET_KEY="sk-lf-..."    # Langfuse UI에서 생성
LANGFUSE_PUBLIC_KEY="pk-lf-..."    # Langfuse UI에서 생성
LANGFUSE_HOST="http://localhost:3000"
```

### Phase 2: SDK 설치 및 기본 연동

**목표**: Python SDK 설치 및 기본 트레이싱 테스트

```bash
# SDK 설치
poetry add langfuse
```

**기본 연동 코드** (utils/langfuse_client.py):

```python
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

def get_langfuse_client() -> Langfuse:
    """Langfuse 클라이언트 인스턴스 반환"""
    return get_client()

def get_langfuse_handler() -> CallbackHandler:
    """LangChain용 Langfuse 콜백 핸들러 반환"""
    return CallbackHandler()
```

### Phase 3: 프롬프트 관리 마이그레이션

**목표**: 기존 프롬프트를 Langfuse로 업로드 및 조회

**기존 구조**:
```
targets/
├── prep_generate/
│   ├── prompt.txt
│   └── .metadata.yaml
```

**Langfuse 연동 코드** (utils/langfuse_prompts.py):

```python
from langfuse import get_client

def upload_prompt(name: str, content: str, labels: list = None):
    """프롬프트를 Langfuse에 업로드"""
    langfuse = get_client()
    langfuse.create_prompt(
        name=name,
        type="text",
        prompt=content,
        labels=labels or ["staging"]
    )

def get_prompt(name: str, label: str = "production"):
    """Langfuse에서 프롬프트 조회"""
    langfuse = get_client()
    return langfuse.get_prompt(name, label=label)

def promote_to_production(name: str, version: int):
    """특정 버전을 production으로 승격"""
    langfuse = get_client()
    # Langfuse UI 또는 API를 통해 레이블 변경
    pass
```

### Phase 4: 데이터셋 마이그레이션

**목표**: 기존 테스트 케이스를 Langfuse 데이터셋으로 변환

**기존 구조**:
```
datasets/
├── prep_generate/
│   ├── test_cases.json
│   └── expected.json
```

**Langfuse 연동 코드** (utils/langfuse_datasets.py):

```python
import json
from langfuse import get_client

def upload_dataset(name: str, test_cases_path: str, expected_path: str):
    """테스트 케이스를 Langfuse 데이터셋으로 업로드"""
    langfuse = get_client()

    # 데이터셋 생성
    langfuse.create_dataset(name=name)

    # 테스트 케이스 로드
    with open(test_cases_path) as f:
        test_cases = json.load(f)
    with open(expected_path) as f:
        expected = json.load(f)

    # 아이템 추가
    for case in test_cases:
        case_id = case["id"]
        langfuse.create_dataset_item(
            dataset_name=name,
            input=case["inputs"],
            expected_output=expected.get(case_id, {}),
            metadata={"description": case.get("description", "")}
        )

def get_dataset(name: str):
    """Langfuse에서 데이터셋 조회"""
    langfuse = get_client()
    return langfuse.get_dataset(name)
```

### Phase 5: 실험 기능 마이그레이션

**목표**: `run_langsmith_experiment()` → Langfuse 실험

**Langfuse 실험 코드** (utils/langfuse_experiments.py):

```python
from langfuse import get_client
from langfuse.langchain import CallbackHandler

def run_experiment(
    dataset_name: str,
    prompt_name: str,
    experiment_name: str,
    target_fn,
    evaluators: list
):
    """Langfuse 기반 실험 실행"""
    langfuse = get_client()
    dataset = langfuse.get_dataset(dataset_name)

    results = []
    for item in dataset.items:
        # 트레이스 생성
        trace = langfuse.trace(name=experiment_name)

        # 타겟 함수 실행
        handler = CallbackHandler(trace_id=trace.id)
        output = target_fn(item.input, callbacks=[handler])

        # 평가 실행 및 점수 기록
        for evaluator in evaluators:
            score = evaluator(item.input, output, item.expected_output)
            langfuse.create_score(
                trace_id=trace.id,
                name=evaluator.__name__,
                value=score["score"],
                comment=score.get("reasoning", "")
            )

        results.append({
            "trace_id": trace.id,
            "input": item.input,
            "output": output,
            "expected": item.expected_output
        })

    langfuse.flush()
    return results
```

### Phase 6: 기존 코드 트레이싱 추가

**목표**: 모든 LLM 호출에 Langfuse 트레이싱 적용

**src/pipeline.py 수정**:

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

---

## 5. 환경변수 설정

### 기존 (.env)

```bash
# LangSmith
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=prompt_eval
```

### 추가 (.env)

```bash
# Langfuse (로컬 서버)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000

# 마이그레이션 중 양쪽 유지 가능
# LANGSMITH_TRACING=false  # 마이그레이션 완료 후 비활성화
```

---

## 6. 예상 일정

| Phase | 작업 내용 | 우선순위 |
|-------|----------|---------|
| Phase 1 | Docker 서버 구축 | 높음 |
| Phase 2 | SDK 설치 및 기본 연동 | 높음 |
| Phase 3 | 프롬프트 관리 마이그레이션 | 중간 |
| Phase 4 | 데이터셋 마이그레이션 | 중간 |
| Phase 5 | 실험 기능 마이그레이션 | 높음 |
| Phase 6 | 트레이싱 추가 | 낮음 |

---

## 7. 주의사항

### Docker 리소스 요구사항

- PostgreSQL, ClickHouse, Redis 동시 실행
- 최소 8GB RAM 권장
- 디스크 공간: 10GB 이상

### 병행 운영 가능

마이그레이션 기간 동안 LangSmith와 Langfuse를 동시에 사용할 수 있습니다:

```python
# 환경변수로 선택
USE_LANGFUSE = os.getenv("USE_LANGFUSE", "false") == "true"

if USE_LANGFUSE:
    from utils.langfuse_experiments import run_experiment
else:
    from utils.langsmith_experiments import run_langsmith_experiment as run_experiment
```

### 기능 제한사항

| 기능 | LangSmith | Langfuse |
|------|-----------|----------|
| 자동 트레이싱 | 환경변수만으로 활성화 | CallbackHandler 필요 |
| 프롬프트 Hub | 있음 | 없음 (자체 관리) |
| 실험 비교 UI | 내장 | 기본 제공 |

---

## 8. 참고 자료

- [Langfuse 공식 문서](https://langfuse.com/docs)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)
- [Docker Compose 설정](https://langfuse.com/self-hosting/deployment/docker-compose)
- [Python SDK 레퍼런스](https://python.reference.langfuse.com/)
- [LangChain 연동 가이드](https://langfuse.com/docs/integrations/langchain/tracing)

---

## 9. Phase별 TODO 체크리스트

### Phase 1: 로컬 서버 구축

- [x] Docker Desktop 실행 확인
- [x] Langfuse 저장소 클론 (`git clone https://github.com/langfuse/langfuse.git ~/langfuse`)
- [x] Docker Compose 실행 (`docker compose up -d`)
- [x] 컨테이너 상태 확인 (`docker ps`)
- [x] http://localhost:3000 접속 확인
- [x] Langfuse 계정 생성 (로컬 UI에서)
- [x] 프로젝트 생성
- [x] API 키 발급 (Secret Key, Public Key)
- [x] .env 파일에 환경변수 추가

### Phase 2: SDK 설치 및 기본 연동

- [x] langfuse 패키지 설치 (`poetry add langfuse`)
- [x] utils/langfuse_client.py 파일 생성
- [x] get_langfuse_client() 함수 구현
- [x] get_langfuse_handler() 함수 구현
- [x] 연결 테스트 코드 작성 및 실행
- [x] Langfuse UI에서 트레이스 확인

### Phase 3: 프롬프트 관리 마이그레이션

- [x] utils/langfuse_prompts.py 파일 생성
- [x] upload_prompt() 함수 구현
- [x] get_prompt() 함수 구현
- [x] promote_to_production() 함수 구현
- [x] 기존 targets/ 프롬프트 업로드 스크립트 작성
- [x] prep_generate 프롬프트 업로드 테스트
- [x] prep_output_analyze 프롬프트 업로드 테스트
- [x] prep_output_questions 프롬프트 업로드 테스트
- [x] Langfuse UI에서 프롬프트 버전 확인

### Phase 4: 데이터셋 마이그레이션

- [x] utils/langfuse_datasets.py 파일 생성
- [x] upload_dataset() 함수 구현
- [x] get_dataset() 함수 구현
- [x] 기존 datasets/ 업로드 스크립트 작성
- [x] prep_generate 데이터셋 업로드 테스트
- [x] prep_output_analyze 데이터셋 업로드 테스트
- [x] prep_output_questions 데이터셋 업로드 테스트
- [x] Langfuse UI에서 데이터셋 확인

### Phase 5: 실험 기능 통합 (src/pipeline.py 수정) ✅

**목표**: 기존 `run_langsmith_experiment()` → 통합 `run_experiment(backend=...)` 함수로 변경

- [x] src/pipeline.py에 `run_experiment()` 통합 함수 추가
  - [x] `backend` 파라미터 추가 (`"langsmith"` | `"langfuse"`)
  - [x] Langfuse용 내부 함수 `_run_langfuse_experiment()` 구현
  - [x] 기존 LangSmith 로직은 그대로 유지 (호환성)
- [x] Langfuse 실험 로직 구현
  - [x] Langfuse SDK 내장 `run_experiment()` 메서드 활용
  - [x] 평가자(evaluator) 실행 + `LangfuseEvaluation` 객체 반환
  - [x] 실험 결과 반환
- [x] cli/experiment.py 수정
  - [x] `--backend` 옵션 추가 (기본값: both)
  - [x] `both` 옵션: Langfuse + LangSmith 동시 실행
- [x] 테스트
  - [x] quick 모드 전체 데이터셋 실험 테스트 (11/11 통과)
  - [x] Langfuse UI에서 결과 확인 (http://localhost:3000)

---

## 현재 의사결정 방향성

### 단기 (현재)
- **LangSmith + Langfuse 병행 운영**
  - `--backend both` 기본값으로 두 플랫폼 동시 실행
  - 프롬프트 테스트 시 양쪽 UI에서 모니터링
  - LangSmith의 직관적인 평가 UI + Langfuse의 셀프호스팅 장점 활용

### 장기 (점진적 마이그레이션 후)
- **Langfuse 단독 사용**
  - 트레이싱 기능까지 완전 이전 후 LangSmith 비활성화
  - 상세 스코어링 로그 → 커스텀 리포트 생성
  - comment에 JSON 구조화 → API로 추출 → 별도 리포트/대시보드

---

### Phase 6: 트레이싱 옵션 추가 (기존 로직에 통합)

**목표**: 기존 평가자/로더에 Langfuse 트레이싱 옵션 추가

- [ ] src/pipeline.py 수정
  - [ ] `execute_prompt()`에 `trace_to_langfuse` 옵션 추가
  - [ ] CallbackHandler 조건부 적용
- [ ] src/evaluators/llm_judge.py 수정
  - [ ] LLM Judge 호출 시 트레이싱 옵션 추가
- [ ] utils/models.py 수정
  - [ ] LLM 인스턴스에 기본 콜백 핸들러 옵션 추가
- [ ] 테스트
  - [ ] 전체 파이프라인 실행 테스트
  - [ ] Langfuse UI에서 트레이스 계층 구조 확인
  - [ ] 성능 지표 (latency, token usage) 확인

### Phase 7: 스코어링 리포트 고도화 (마이그레이션 완료 후)

**목표**: 실험 실행 시 상세 스코어 리포트 자동 생성

- [ ] comment 필드 JSON 구조화
  - [ ] `LangfuseEvaluation(comment=json.dumps({...}))` 형태로 저장
  - [ ] failed_items, passed_items, reasoning, suggestions 포함
- [ ] 실험 종료 시 자동 리포트 생성
  - [ ] `_run_langfuse_experiment()` 완료 후 리포트 출력
  - [ ] Langfuse API로 스코어 데이터 추출 → JSON 파싱
  - [ ] 실패 케이스 상세 분석 포함
  - [ ] 결과를 `results/{experiment_name}/report.md` 저장

### 마이그레이션 완료 후

- [ ] LangSmith 환경변수 비활성화 (`LANGSMITH_TRACING=false`)
- [ ] utils/langsmith_*.py 파일 정리 (백업 또는 삭제)
- [ ] README.md 업데이트 (Langfuse 사용법 추가)
- [ ] 팀 공유 및 문서화
