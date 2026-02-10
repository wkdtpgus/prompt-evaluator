# Prompt Evaluator 사용 가이드

> LLM 프롬프트 평가 체계 활용 방법

---

## 1. 시작하기

### 1.1. 환경 설정

```bash
# 의존성 설치
poetry install

# 환경변수 설정
cp .env.example .env
```

`.env` 파일에 필요한 환경변수를 설정합니다:

```bash
# OpenAI (필수)
OPENAI_API_KEY=sk-...

# LangSmith (클라우드)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=prompt_eval

# Langfuse (셀프호스팅)
LANGFUSE_SECRET_KEY=sk-lf-...     # Langfuse UI에서 생성
LANGFUSE_PUBLIC_KEY=pk-lf-...     # Langfuse UI에서 생성
LANGFUSE_HOST=http://localhost:3000  # 로컬 또는 클라우드 서버 URL
```

> 양쪽 플랫폼 환경변수를 모두 설정하면 `--backend both` (기본값)로 동시 실행됩니다.

### 1.2. Langfuse 로컬 서버 구축

Langfuse를 로컬에서 실행하려면 Docker가 필요합니다:

```bash
# 1. Langfuse 저장소 클론
git clone https://github.com/langfuse/langfuse.git ~/langfuse
cd ~/langfuse

# 2. Docker Compose 실행
docker compose up -d

# 3. 접속 확인
# http://localhost:3000
```

**서버 구축 후:**

1. http://localhost:3000 에서 Langfuse 계정 생성
2. 프로젝트 생성
3. API 키 발급 (Secret Key, Public Key)
4. `.env` 파일에 `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST` 추가

**Docker 리소스 요구사항:**

- PostgreSQL, ClickHouse, Redis 동시 실행
- 최소 8GB RAM 권장
- 디스크 공간: 10GB 이상

> 팀 공유용 GCP 클라우드 배포에 대한 상세 내용은 [기능 명세서 Section 3.3](./SPECIFICATION.md) 참조

### 1.3. Langfuse 프로젝트별 트레이싱 분리

프로덕션 환경에서는 서비스(타겟)별로 Langfuse 프로젝트를 분리하여 트레이스와 평가 결과를 관리하는 것을 권장합니다.

**프로젝트별 API 키 설정:**

```bash
# .env — 프로젝트별 API 키 (Langfuse UI에서 각 프로젝트마다 발급)
LANGFUSE_PREP_OUTPUT_PUBLIC_KEY=pk-lf-...
LANGFUSE_PREP_OUTPUT_SECRET_KEY=sk-lf-...

LANGFUSE_MEETING_GENERATOR_PUBLIC_KEY=pk-lf-...
LANGFUSE_MEETING_GENERATOR_SECRET_KEY=sk-lf-...

# 공통 호스트
LANGFUSE_HOST=http://34.64.193.193
```

**프로덕션 애플리케이션에서 프로젝트별 트레이싱:**

각 서비스에서 Langfuse 클라이언트 생성 시 해당 프로젝트의 API 키를 사용하면, 트레이스가 해당 프로젝트에만 기록됩니다:

```python
from langfuse import Langfuse

# prep_output 서비스 → PREP_OUTPUT 프로젝트에 트레이스 기록
client = Langfuse(
    public_key=os.environ["LANGFUSE_PREP_OUTPUT_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_PREP_OUTPUT_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
)
```

**LLM-as-a-Judge 평가 (Running Evaluator):**

프로젝트별로 분리된 트레이스에 대해 Langfuse UI에서 Running Evaluator를 설정할 수 있습니다:

1. Langfuse UI > 해당 프로젝트 선택
2. LLM-as-a-Judge > "+ Create Custom Evaluator"
3. eval 프롬프트 내용을 복사하여 등록
4. 변수 매핑: `{output}` → `{{output}}`, `{input}` → `{{input}}`

> **Note**: Running Evaluator 생성은 현재 UI에서만 가능합니다 (API 미지원, [langfuse#8241](https://github.com/langfuse/langfuse/issues/8241)).
> 이 프로젝트의 `experiment` 커맨드는 별도로 코드에서 LLM Judge를 실행하므로, Running Evaluator 설정 없이도 평가가 동작합니다.

### 1.4. 프로젝트 구조

```
prompt-evaluator/
├── main.py                     # CLI 엔트리포인트
├── cli/                        # CLI 명령어 모듈
│   ├── prompt.py               # prompt 서브커맨드
│   ├── baseline.py             # baseline 서브커맨드
│   ├── experiment.py           # experiment, regression 명령어
│   ├── config.py               # validate 명령어
│   └── dataset.py              # list, upload 명령어
│
├── src/                        # 핵심 소스 코드
│   ├── pipelines/
│   │   ├── pipeline.py         # 평가 파이프라인 (backend 파라미터)
│   │   └── e2e_chain.py        # E2E 체인 파이프라인
│   ├── evaluators/             # 평가자
│   ├── loaders/                # 로더
│   ├── versioning/             # 버전 관리
│   └── regression/             # 회귀 테스트
│
├── utils/                      # 유틸리티 모듈
│   ├── prompt_sync.py          # 프롬프트 업로드/조회 (LangSmith + Langfuse 통합)
│   ├── dataset_sync.py         # 데이터셋 업로드/조회 (LangSmith + Langfuse 통합)
│   ├── eval_adapters.py        # LLM Judge 어댑터 (LangSmith/Langfuse 형식 변환)
│   ├── langfuse_client.py      # Langfuse 싱글톤 클라이언트
│   ├── models.py               # LLM 인스턴스
│   └── git.py                  # git 관련 유틸
│
├── targets/                    # 평가 대상 프롬프트
│   └── {name}/
│       ├── prompt.*            # 프롬프트 템플릿 (.txt, .py, .xml, .md)
│       ├── config.yaml         # 평가 설정
│       └── .metadata.yaml      # 프롬프트 버전 메타데이터
│
├── datasets/                   # 테스트 데이터
│   └── {name}/
│       ├── test_cases.json     # 입력 데이터
│       └── expected.json       # 기대 결과 (키워드, 금지어 등)
│
├── eval_prompts/               # LLM Judge 평가 프롬프트
│   ├── general/                # 범용 평가 기준
│   └── {domain}/               # 도메인별 평가 기준
│
├── results/                    # 평가 결과
│   └── baselines/{name}/       # 기준선 저장
│
└── configs/                    # 전역 설정
    ├── config.py               # 모델, 임계값 기본값
    └── schema.yaml             # config 스키마 참고
```

---

## 2. 새 프롬프트 평가 추가

### 2.1. 폴더 생성

```bash
mkdir -p targets/my_prompt
mkdir -p datasets/my_prompt
```

### 2.2. 프롬프트 파일 작성

`targets/my_prompt/prompt.txt`:
```
당신은 {role}입니다.

사용자 질문: {query}
컨텍스트: {context}

위 정보를 바탕으로 답변해주세요.
```

**지원 형식:**
| 확장자 | 설명 |
|--------|------|
| `.txt` | 단일 템플릿 |
| `.md` | 마크다운 형식 |
| `.py` | Python 변수 (`SYSTEM_PROMPT`, `USER_PROMPT` 등) |
| `.xml` | XML 구조 (`<system>`, `<user>` 태그) |

### 2.3. 평가 설정 작성

`targets/my_prompt/config.yaml`:
```yaml
name: my_prompt
description: 프롬프트 설명
output_format: text  # text | json

evaluators:
  # Rule-based 평가 (무료)
  - type: rule_based
    checks:
      - keyword_inclusion      # 필수 키워드 포함
      - forbidden_word_check   # 금지어 미포함

  # LLM Judge 평가 (유료)
  - type: llm_judge
    enabled: true
    criteria:
      - general/instruction_following    # 항상 '도메인/기준명' 전체 경로
      - general/output_quality

thresholds:
  pass_rate: 0.85    # 전체 케이스 중 85% 통과
  min_score: 0.70    # 개별 케이스 최소 점수

run_mode: quick  # quick: Rule만 | full: Rule + LLM Judge
```

### 2.4. 테스트 데이터 작성

`datasets/my_prompt/test_cases.json`:
```json
[
  {
    "id": "case_001",
    "description": "기본 테스트",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "환불 절차가 어떻게 되나요?",
      "context": "7일 이내 환불 가능"
    }
  },
  {
    "id": "case_002",
    "description": "복잡한 상황 테스트",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "배송이 늦어지고 있는데 환불도 가능한가요?",
      "context": "배송 지연 시 전액 환불 가능, 7일 이내"
    }
  }
]
```

`datasets/my_prompt/expected.json`:
```json
{
  "case_001": {
    "keywords": ["환불", "7일"],
    "forbidden": ["불가능", "안됩니다"]
  },
  "case_002": {
    "keywords": ["환불", "배송", "지연"],
    "forbidden": ["불가능"]
  }
}
```

### 2.5. 검증 및 실행

```bash
# 설정 검증
poetry run python main.py validate --name my_prompt

# 평가 실행 (Langfuse + LangSmith 동시 - 기본값)
poetry run python main.py experiment --name my_prompt

# Langfuse만 실행
poetry run python main.py experiment --name my_prompt --backend langfuse

# LangSmith만 실행 (자동 버전 관리)
poetry run python main.py experiment --name my_prompt --backend langsmith

# 정식 평가 (full 모드 - Rule + LLM Judge)
poetry run python main.py experiment --name my_prompt --mode full
```

---

## 3. CLI 명령어

### 3.1. 평가 실행

```bash
# 기본 실행 (Langfuse + LangSmith 동시)
poetry run python main.py experiment --name {name}

# 백엔드 지정
poetry run python main.py experiment --name {name} --backend langfuse  # Langfuse만
poetry run python main.py experiment --name {name} --backend langsmith # LangSmith만

# 모드 지정
poetry run python main.py experiment --name {name} --mode full

# 특정 프롬프트 버전으로 평가
poetry run python main.py experiment --name {name} --version v1.0

# 실험 이름 접두사 지정
poetry run python main.py experiment --name {name} --prefix "feature-branch"
```

### 3.2. 설정 검증

```bash
# 단일 config 검증
poetry run python main.py validate --name {name}

# 모든 config 검증
poetry run python main.py validate --all
```

### 3.3. 타겟 프롬프트 버전 관리

```bash
# 프롬프트 업로드 (LangSmith + Langfuse 동시 - 기본값)
poetry run python main.py prompt push --name {name} --tag v1.0

# 특정 백엔드만 업로드
poetry run python main.py prompt push --name {name} --tag v1.0 --backend langfuse

# 프롬프트 가져오기 (LangSmith 기본)
poetry run python main.py prompt pull --name {name} --tag v1.0

# Langfuse에서 가져오기
poetry run python main.py prompt pull --name {name} --backend langfuse

# 버전 목록 조회
poetry run python main.py prompt versions --name {name}

# .py/.xml 파일의 프롬프트 키 확인
poetry run python main.py prompt keys --name {name}
```

### 3.4. 유틸리티

```bash
# 평가 가능한 세트 목록
poetry run python main.py list

# 데이터셋 업로드 (LangSmith + Langfuse 동시 - 기본값)
poetry run python main.py upload --name {name}

# 특정 백엔드만 업로드
poetry run python main.py upload --name {name} --backend langfuse
```

### 3.5. 코드에서 통합 API 사용

프롬프트와 데이터셋 관리는 `backend` 파라미터로 LangSmith/Langfuse를 선택합니다:

```python
from utils.prompt_sync import push_prompt, get_prompt, list_prompt_versions

# 프롬프트 업로드
result = push_prompt("my_prompt", backend="both", version_tag="v1.0")    # 양쪽 동시
result = push_prompt("my_prompt", backend="langfuse")                     # Langfuse만
result = push_prompt("my_prompt", backend="langsmith", version_tag="v1.0") # LangSmith만

# 프롬프트 조회
template = get_prompt("my_prompt", backend="langfuse")
template = get_prompt("my_prompt", backend="langsmith", version_tag="v1.0")

# 버전 목록 (LangSmith)
versions = list_prompt_versions("my_prompt")
```

```python
from utils.dataset_sync import upload_dataset, get_dataset

# 데이터셋 업로드
result = upload_dataset("my_prompt", backend="both")        # 양쪽 동시
result = upload_dataset("my_prompt", backend="langfuse")    # Langfuse만

# 데이터셋 조회 (Langfuse)
dataset = get_dataset("my_prompt")
```

---

## 4. 평가 기준 설정

### 4.1. Rule-based 평가 (무료)

| 항목 | 설명 |
|------|------|
| `keyword_inclusion` | `expected.json`의 `keywords` 포함 비율 |
| `forbidden_word_check` | `expected.json`의 `forbidden` 미포함 여부 |

### 4.2. LLM Judge 평가 (유료)

평가 기준 프롬프트는 `eval_prompts/{domain}/` 폴더에 `.txt` 파일로 작성합니다.

**일반 기준 (`eval_prompts/general/`):**
- `instruction_following.txt` - 지시사항 준수도
- `output_quality.txt` - 전반적 출력 품질
- `factual_accuracy.txt` - 사실 정확성

**도메인별 기준 예시 (`eval_prompts/oneonone/`):**
- `tone_appropriateness.txt` - 톤/어조 적절성
- `coaching_quality.txt` - 코칭 품질
- `sensitive_topic_handling.txt` - 민감 주제 처리

### 4.3. 새 평가 기준 추가

1. `eval_prompts/{domain}/{criterion}.txt` 파일 생성
2. 평가 프롬프트 작성 (점수 1-5 또는 0-1 기준)
3. `config.yaml`의 `llm_judge.criteria`에 `{domain}/{criterion}` 전체 경로로 추가

---

## 5. 실행 모드

| 모드 | 평가자 | 용도 | 비용 |
|------|--------|------|:----:|
| `quick` | Rule-based만 | 개발 중 빠른 검증 | 무료 |
| `full` | Rule + LLM Judge | 정식 평가, 버전 비교 | 유료 |

```yaml
# config.yaml에서 기본 모드 설정
run_mode: quick
```

```bash
# CLI에서 오버라이드
poetry run python main.py experiment --name {name} --mode full
```

---

## 6. 결과 확인

### 6.1. 평가 대시보드

평가 결과는 **LangSmith** 또는 **Langfuse** 대시보드에서 확인합니다:
- 각 테스트 케이스별 점수
- 평가 기준별 상세 결과
- 실패 케이스 분석
- 버전 간 비교

| 플랫폼 | 접속 URL | 비고 |
|--------|----------|------|
| LangSmith | https://smith.langchain.com | 클라우드 (유료) |
| Langfuse (로컬) | http://localhost:3000 | Docker 실행 필요 |
| Langfuse (GCP) | http://34.64.193.193 | 팀 공유 서버 (Basic Auth) |

> **Note**: 기본값 `--backend both`로 실행 시 두 플랫폼에서 동시에 결과 확인 가능

### 6.2. 회귀 테스트

프롬프트 수정 시 이전 버전과 비교하여 성능 저하를 감지합니다.

#### 데이터 소스 (`--source`)

| 소스 | baseline | current | 로컬 파일 필요 |
|------|----------|---------|:-----------:|
| `local` (기본) | 로컬 baseline JSON | 로컬 latest.json | O |
| `langfuse` | Langfuse API | Langfuse API | X |
| `langsmith` | 로컬 baseline JSON | LangSmith API | O |

#### Langfuse 소스 사용법 (권장)

Langfuse에 저장된 실험 결과를 직접 가져오므로 **로컬 파일 관리가 필요 없습니다**.

```bash
# 최신 2개 run 자동 비교 (가장 간단한 사용법)
# baseline = 두번째 최신 run, current = 최신 run
poetry run python main.py regression --name {name} --source langfuse

# 특정 run 2개를 직접 비교
poetry run python main.py regression --name {name} --source langfuse \
  --baseline "leader_scoring-full-20260206-113005" \
  --experiment "leader_scoring-full-20260209-110841"

# baseline만 지정 (current = 최신 run)
poetry run python main.py regression --name {name} --source langfuse \
  --baseline "leader_scoring-full-20260206-113005"

# CI/CD에서 사용 (회귀 시 exit code 1)
poetry run python main.py regression --name {name} --source langfuse --fail
```

> **Tip**: run 이름은 Langfuse UI의 Experiments 탭에서 확인할 수 있습니다.

#### Local 소스 사용법

```bash
# 1. 먼저 baseline 설정 (최초 1회)
poetry run python main.py baseline set-local {name}

# 2. 실험 실행 후 회귀 비교
poetry run python main.py regression --name {name}
```

Langfuse에서 직접 baseline을 생성할 수도 있습니다:

```bash
# Langfuse 최신 run으로 baseline 저장
poetry run python main.py baseline set-langfuse {name}

# 특정 run 지정
poetry run python main.py baseline set-langfuse {name} \
  --experiment "leader_scoring-full-20260206-113005"
```

#### 회귀 판단 기준

| 지표 | 허용 변동폭 | 조치 |
|------|:----------:|------|
| 평균 점수 | -0.2 이내 | 초과 시 리뷰 필요 |
| Pass Rate | -5% 이내 | 초과 시 경고 |
| 특정 케이스 실패 | Pass → Fail | 반드시 리뷰 필요 |

---

## 7. 기존 프롬프트 마이그레이션

### 7.1. .py 파일 프롬프트

기존 `.py` 파일이 있는 경우:

```
# Before (평가 불가)
targets/prep_output/
├── coaching_analyzer.py
└── question_generator.py

# After (평가 가능)
targets/coaching_analyzer/
├── prompt.py              # 기존 파일 이동 또는 복사
└── config.yaml            # 새로 작성
```

### 7.2. 변환 단계

1. 새 폴더 생성: `mkdir -p targets/{name}`
2. 프롬프트 파일 이동: `prompt.py`로 이름 변경
3. `config.yaml` 작성
4. 테스트 데이터 생성: `datasets/{name}/`
5. 검증: `poetry run python main.py validate --name {name}`

---

## 8. 문제 해결

### config 검증 실패

```
✗ 프롬프트 파일 없음
```
→ `targets/{name}/prompt.*` 파일 확인

```
⚠ eval_prompt 파일 없음
```
→ `eval_prompts/{criterion}.txt` 파일 생성 필요 (criteria는 `domain/name` 전체 경로)

### 평가 실행 오류

```
KeyError: '{placeholder}'
```
→ `test_cases.json`의 `inputs`가 프롬프트 placeholder와 일치하는지 확인

---

## 9. 참고

- [기능 명세서](./SPECIFICATION.md) - 시스템 상세 스펙
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md) - 버전 관리 상세
- [Langfuse 마이그레이션 계획](./langfuse-migration-plan.md) - Langfuse 통합 상세
- [CLI 레퍼런스](./features/cli-reference.md) - 전체 CLI 명령어
