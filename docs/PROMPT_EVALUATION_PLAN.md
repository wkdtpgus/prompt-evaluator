# 프롬프트 정량 평가 체계 구축 기획안

> **문서 버전**: v2.2
> **최종 수정일**: 2026-01-22
> **수정 내역**: 다중 프롬프트 형식 지원(.txt/.py/.xml), LangSmith Experiment 연동 완료, eval_prompts 중괄호 이스케이프 수정

## 1. 개요 (Overview)
본 기획안은 **LangSmith**를 활용하여 LLM 프롬프트의 성능을 정량적으로 측정하고, 지속적으로 개선하기 위한 평가 체계를 구축하는 것을 목표로 합니다. 감에 의존한 수정이 아닌, 데이터에 기반한 의사결정을 가능하게 합니다.

### 1.1. 설계 원칙

1. **LangSmith 기능 최대 활용**: 별도 인프라 구축 없이 LangSmith 내장 기능 우선 사용
2. **모듈화된 파이프라인**: 데이터만 교체하면 동일 파이프라인 재사용 가능
3. **점진적 복잡도**: 단순한 Rule-based부터 시작, 필요시 LLM-Judge 추가

## 2. 목표 (Objectives)
*   **정량적 지표 확보**: 프롬프트 성능을 점수화하여 객관적으로 판단.
*   **버전 관리 및 비교**: 프롬프트 수정 전후의 성능 변화를 명확히 비교.
*   **테스트 자동화**: 반복적인 테스트 과정을 자동화하여 효율성 증대.
*   **엣지 케이스 발견**: 다양한 테스트 케이스를 통해 모델이 실패하는 유형 식별.
*   **회귀 방지 (Regression Prevention)**: 프롬프트 변경 시 기존 성능 저하 여부 자동 감지.

## 3. LangSmith 핵심 기능 활용

LangSmith가 제공하는 기능을 최대한 활용하여 별도 인프라 구축을 최소화합니다.

### 3.1. LangSmith 주요 기능

| 기능 | 설명 | 활용 방법 |
|------|------|----------|
| **Datasets** | 테스트 케이스 저장/관리 | 입력-정답 쌍을 버전 관리하며 저장 |
| **Experiments** | 평가 실행 및 결과 기록 | 프롬프트 버전별 성능 비교 |
| **Built-in Evaluators** | 내장 평가자 (정확도, 유사도 등) | 커스텀 구현 없이 바로 사용 |
| **Tracing** | LLM 호출 추적/디버깅 | 실패 케이스 원인 분석 |
| **Prompt Hub** | 프롬프트 버전 관리 | 프롬프트 변경 이력 추적 |

### 3.2. LangSmith 내장 평가자 (Built-in Evaluators)

**별도 구현 없이 사용 가능한 평가자:**

```python
from langsmith.evaluation import LangChainStringEvaluator

# 1. 정확도 평가 (Correctness)
correctness = LangChainStringEvaluator("correctness")

# 2. 임베딩 유사도 (벡터 DB 불필요 - LangSmith가 자동 처리)
embedding_distance = LangChainStringEvaluator("embedding_distance")

# 3. 문자열 거리
string_distance = LangChainStringEvaluator("string_distance")

# 4. 커스텀 LLM-Judge (criteria 기반)
from langsmith.evaluation import LangChainStringEvaluator
helpfulness = LangChainStringEvaluator(
    "labeled_criteria",
    config={"criteria": "helpfulness"}
)
```

> **핵심**: `embedding_distance`는 LangSmith가 내부적으로 임베딩을 처리하므로 **별도의 벡터 DB가 필요 없습니다**.

### 3.3. 평가 실행 코드 예시

```python
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

# 1. 데이터셋 로드 (LangSmith에서)
dataset_name = "my-prompt-tests"

# 2. 타겟 함수 정의 (평가 대상)
def my_prompt_chain(inputs: dict) -> str:
    # 프롬프트 실행 로직
    return llm.invoke(prompt.format(**inputs))

# 3. 평가 실행
results = evaluate(
    my_prompt_chain,
    data=dataset_name,
    evaluators=[
        LangChainStringEvaluator("correctness"),
        LangChainStringEvaluator("embedding_distance"),
    ],
    experiment_prefix="prompt-v2",
)
```

---

## 4. 시스템 구성 요소 (Core Components)

### 4.1. 데이터셋 (Dataset)
평가의 기준이 되는 "문제은행"입니다.
*   **구성**: `Input` (질문/상황) + `Reference Output` (모범 답안/기대 결과) + `Metadata` (태그, 난이도 등)
*   **관리**: LangSmith Dataset 기능을 사용하여 관리.
*   **유형**:
    *   **Golden Set**: 정답이 명확한 케이스 (예: 사실 추출, 분류).
    *   **Silver Set**: 정답이 모호하지만 지향점이 있는 케이스 (예: 창의적 글쓰기, 톤앤매너).
    *   **Edge Case Set**: 모델이 실패하기 쉬운 경계 케이스 (예: 모호한 입력, 긴 컨텍스트, 다국어).

#### 4.1.1. 데이터셋 스키마 (Dataset Schema)

```json
{
  "id": "test_001",
  "input": {
    "query": "사용자 질문 또는 입력",
    "context": "추가 컨텍스트 (선택)",
    "variables": {
      "var1": "템플릿 변수 값"
    }
  },
  "reference": {
    "output": "기대 출력 (정답)",
    "keywords": ["필수 포함 키워드"],
    "forbidden": ["금지어 목록"]
  },
  "metadata": {
    "category": "분류/추출/생성/요약",
    "difficulty": "easy|medium|hard",
    "tags": ["edge_case", "multi_turn"],
    "created_at": "2026-01-20"
  }
}
```

#### 4.1.2. 데이터셋 규모 가이드라인

| 단계 | 최소 개수 | 권장 개수 | 용도 |
|------|----------|----------|------|
| MVP | 10개 | 20개 | 빠른 검증, 개발 중 테스트 |
| Production | 50개 | 100개+ | 본격 평가, 회귀 테스트 |
| Edge Cases | 10개 | 20개+ | 취약점 탐지 |

### 4.2. 평가자 (Evaluator)
모델의 답변을 채점하는 로직입니다.

#### 4.2.1. 평가 유형 및 방식

| 평가 유형 | 방식 | LangSmith 지원 | 비용 |
|----------|------|---------------|------|
| **Rule-based** | 코드 로직 | 커스텀 함수로 구현 | 무료 |
| **Embedding 유사도** | 벡터 유사도 | `embedding_distance` 내장 | 저렴 (API 호출) |
| **문자열 거리** | 편집 거리 등 | `string_distance` 내장 | 무료 |
| **LLM-as-a-Judge** | LLM 평가 | `labeled_criteria` 내장 | 고비용 |

> **Embedding 관련**: LangSmith의 `embedding_distance` 평가자가 내부적으로 임베딩을 처리하므로 **별도의 벡터 DB 구축이 불필요**합니다.

#### 4.2.2. 평가 지표 (Metrics) 상세

**A. Rule-based 평가자** (커스텀 구현)

| 지표 | 측정 방법 | 점수 범위 | 임계값 | 용도 |
|------|----------|----------|--------|------|
| `keyword_inclusion` | 필수 키워드 포함 비율 | 0.0 ~ 1.0 | ≥ 0.8 Pass | 핵심 정보 포함 여부 |
| `forbidden_word_check` | 금지어 포함 여부 | 0 또는 1 | = 1 Pass | 금지 표현 필터링 |
| `length_compliance` | 지정 길이 범위 준수 | 0 또는 1 | = 1 Pass | 답변 길이 제어 |
| `format_validity` | JSON/구조 유효성 | 0 또는 1 | = 1 Pass | 구조화 출력 검증 |
| `exact_match` | 해시 비교 (완전 일치) | 0 또는 1 | = 1 Pass | 분류 라벨, 고정 포맷 |

> **`exact_match` 사용 시 주의**: 출력이 **완전히 고정**된 경우에만 사용 (분류 라벨, 코드명, 특정 포맷). 자연어 답변에는 부적합 (공백, 표현 차이로 실패함)

**B. LangSmith 내장 평가자**

| 평가자 | 설명 | 점수 범위 | 임계값 |
|--------|------|----------|--------|
| `embedding_distance` | Reference와 의미적 유사도 | 0.0 ~ 1.0 | ≥ 0.75 Pass |
| `string_distance` | 문자열 편집 거리 | 0.0 ~ 1.0 | ≥ 0.8 Pass |
| `correctness` | Reference와 정확도 (LLM) | 0 또는 1 | = 1 Pass |

**C. LLM-as-a-Judge 평가자** (labeled_criteria)

| 지표 | 평가 기준 | 점수 범위 | 임계값 |
|------|----------|----------|--------|
| `helpfulness` | 도움이 되는 답변인가 | 0 또는 1 | = 1 Pass |
| `relevance` | 질문에 적절히 답변했는가 | 0 또는 1 | = 1 Pass |
| `coherence` | 논리적 일관성 | 0 또는 1 | = 1 Pass |
| `harmfulness` | 유해 콘텐츠 여부 | 0 또는 1 | = 0 Pass |

#### 3.2.3. LLM-as-a-Judge 프롬프트 템플릿

```
You are an expert evaluator. Score the AI response based on the criteria below.

[Input]
{input}

[Reference Answer]
{reference}

[AI Response]
{response}

[Evaluation Criteria]
- Correctness (1-5): Does the response match the reference meaning?
- Relevance (1-5): Does it directly answer the question?
- Coherence (1-5): Is it logically consistent and readable?

[Output Format]
Return JSON only:
{
  "correctness": <score>,
  "correctness_reason": "<brief explanation>",
  "relevance": <score>,
  "relevance_reason": "<brief explanation>",
  "coherence": <score>,
  "coherence_reason": "<brief explanation>"
}
```

#### 3.2.4. 평가자 선택 가이드

```
평가 목적에 따른 권장 조합:

1. 빠른 개발 중 테스트 (저비용)
   └─ Rule-based + Embedding

2. PR 머지 전 품질 검증 (중비용)
   └─ Rule-based + Embedding + LLM-Judge (샘플링 20%)

3. 릴리즈 전 전수 검사 (고비용)
   └─ Rule-based + Embedding + LLM-Judge (전체)
```

### 3.3. 실행 환경 (Runner)
*   Python 스크립트를 통해 데이터셋을 불러오고, 프롬프트를 실행하며, 평가자를 통해 점수를 매깁니다.
*   결과는 LangSmith 대시보드에 자동으로 기록됩니다.

#### 4.3.1. 실행 환경

**두 가지 실행 환경 지원:**

```
[로컬 모드] 개발 단계 - 빠른 반복
────────────────────────────────
datasets/ → 로컬 파이프라인 → 콘솔 출력 + results/
           (LangSmith 트레이싱만)

[LangSmith 모드] 정식 평가 - 버전 비교/분석
────────────────────────────────
datasets/ → LangSmith Dataset 업로드
                    ↓
            evaluate() + Experiment 기록
                    ↓
            대시보드에서 버전 비교/분석
```

**CLI 인터페이스:**
```bash
# 로컬 개발 (빠름, 결과 콘솔+파일)
poetry run python main.py eval --name prep_analyzer

# 정식 평가 (LangSmith Experiment)
poetry run python main.py experiment --name prep_analyzer
```

#### 4.3.2. 평가 모드

| 모드 | 용도 | 데이터셋 | 평가자 |
|------|------|----------|--------|
| `quick` | 개발 중 빠른 검증 | 10개 샘플 | Rule-based만 |
| `standard` | PR 검증 | 전체 | Rule + String Distance |
| `full` | 릴리즈 전 전수 | 전체 | 모든 평가자 + LLM Judge |

#### 4.3.3. 병렬 처리 설정

```python
# 권장 설정
CONCURRENCY = 5          # 동시 실행 수
RATE_LIMIT = 60          # 분당 요청 수 (API 제한 고려)
RETRY_COUNT = 3          # 실패 시 재시도 횟수
TIMEOUT_SECONDS = 30     # 개별 요청 타임아웃
```

### 4.4. 모듈화된 파이프라인 설계

**핵심 원칙**: 파이프라인 코드는 고정, 데이터만 교체하면 재사용 가능

#### 4.4.1. 입력 데이터 구조 (분리된 구조)

**핵심**: 평가 대상(프롬프트)과 평가 데이터(테스트케이스)를 분리하여 관리

```
┌─────────────────────────────────────────────────────────────────────┐
│                    평가 파이프라인 입력 구조                            │
└─────────────────────────────────────────────────────────────────────┘

[1. 평가 대상 프롬프트]              [2. 평가 데이터셋]
        │                                   │
        ▼                                   ▼
┌─────────────────────┐       ┌─────────────────────────┐       ┌─────────────────┐
│ targets/            │       │ datasets/               │       │ configs/        │
│   {name}.txt        │       │   {name}_data/          │       │   {name}.yaml   │
│   {name}.py         │       │     ├── test_cases.json │       │                 │
│   {name}.xml        │       │     └── expected.json   │       │                 │
└──────────┬──────────┘       └────────────┬────────────┘       └────────┬────────┘
           │                               │
           └───────────┬───────────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │   평가 파이프라인      │
            │   (main.py eval)    │
            └─────────────────────┘
```

**분리의 장점**:
- 동일 프롬프트에 여러 데이터셋 적용 가능 (A/B 테스트, 언어별 테스트)
- 프롬프트 버전 관리와 데이터 관리 독립
- 데이터셋 재사용 용이

#### 4.4.2. 각 데이터 파일 형식

**1) 평가 대상 프롬프트 (다중 형식 지원)**

| 형식 | 파일 패턴 | 설명 |
|------|----------|------|
| `.txt` | `{name}.txt` 또는 `{name}_prompt.txt` | 단일 템플릿 텍스트 |
| `.py` | `{name}.py` 또는 `{name}_prompt.py` | Python 변수 (`*_PROMPT`) |
| `.xml` | `{name}.xml` 또는 `{name}_prompt.xml` | XML 구조 (`<system>`, `<user>`) |

**예시 - .txt 형식:**
```
당신은 {role}입니다.

사용자 질문: {query}
컨텍스트: {context}

위 정보를 바탕으로 답변해주세요.
```

**예시 - .py 형식:**
```python
SYSTEM_PROMPT = """당신은 {role}입니다."""

USER_PROMPT = """
사용자 질문: {query}
컨텍스트: {context}

위 정보를 바탕으로 답변해주세요.
"""
```

**예시 - .xml 형식:**
```xml
<prompts>
    <system>당신은 {role}입니다.</system>
    <user>
        사용자 질문: {query}
        컨텍스트: {context}
    </user>
</prompts>
```

**2) 테스트케이스 데이터** (`datasets/{name}_data/test_cases.json`)
```json
[
  {
    "id": "case_001",
    "inputs": {
      "role": "친절한 고객상담사",
      "query": "환불 절차가 어떻게 되나요?",
      "context": "7일 이내 환불 가능"
    }
  },
  {
    "id": "case_002",
    "inputs": {
      "role": "기술 지원 엔지니어",
      "query": "서버 에러가 발생했습니다",
      "context": "로그 파일 첨부됨"
    }
  }
]
```

**3) 기대 결과물** (`datasets/{name}_data/expected.json`)
```json
{
  "case_001": {
    "reference": {},
    "keywords": ["question_context", "coaching_hint"],
    "forbidden": ["불가능", "안됩니다"]
  },
  "case_002": {
    "reference": {},
    "keywords": ["question_context", "coaching_hint"],
    "forbidden": []
  }
}
```

> **참고**: `reference`가 빈 객체(`{}`)인 경우 string_distance 평가는 스킵됩니다.

**4) 평가 설정** (`configs/{name}.yaml`)
```yaml
eval_prompts_domain: oneonone  # eval_prompts/{domain}/ 폴더 지정

evaluators:
  - type: rule_based
    checks:
      - keyword_inclusion
      - forbidden_word_check
      - format_validity

  - type: similarity
    name: embedding_distance
    threshold: 0.75

  - type: llm_judge
    criteria:
      - instruction_following
      - output_quality
      - purpose_alignment
      - coaching_quality
      - tone_appropriateness
      - sensitive_topic_handling
    enabled: true

thresholds:
  pass_rate: 0.9
  min_score: 0.75

run_mode: standard
```

#### 4.4.3. 파이프라인 실행 인터페이스

```bash
# 기본 실행 (이름 기반 - convention 따름)
poetry run python main.py eval --name prep_analyzer
# → targets/prep_analyzer.txt + datasets/prep_analyzer_data/

# 특정 케이스만 실행
poetry run python main.py eval --name prep_analyzer --case-id case_001,case_002

# 모드 지정
poetry run python main.py eval --name prep_analyzer --mode full

# LangSmith Experiment 실행
poetry run python main.py experiment --name prep_analyzer
```

#### 4.4.4. 디렉토리 컨벤션 (분리 구조)

```
targets/                              # 평가 대상 프롬프트
├── prep_analyzer.txt                 # 프롬프트 1 (.txt 형식)
├── code_review.py                    # 프롬프트 2 (.py 형식)
└── customer_service.xml              # 프롬프트 3 (.xml 형식)

datasets/                             # 평가 데이터
├── prep_analyzer_data/               # 데이터셋 1
│   ├── test_cases.json
│   └── expected.json
│
└── code_review_data/                 # 데이터셋 2
    ├── test_cases.json
    └── expected.json

configs/                              # 평가 설정
├── prep_analyzer.yaml                # 설정 1
└── code_review.yaml                  # 설정 2

eval_prompts/                         # LLM Judge 평가 프롬프트
├── general/                          # 범용 평가 기준
│   ├── instruction_following.txt
│   ├── factual_accuracy.txt
│   └── output_quality.txt
└── oneonone/                         # 1on1 특화 평가 기준
    ├── purpose_alignment.txt
    ├── coaching_quality.txt
    ├── tone_appropriateness.txt
    └── sensitive_topic_handling.txt
```

> **사용법**: `python main.py eval --name prep_analyzer` 실행 시 `targets/prep_analyzer.[txt|py|xml]`, `datasets/prep_analyzer_data/`, `configs/prep_analyzer.yaml` 자동 로드

### 4.5. 구조화된 출력 처리

프롬프트 출력이 JSON 등 구조화된 형식일 경우:

*   **출력 파싱 (Output Parsing)**: 모델의 Raw Output을 평가 가능한 형태로 변환
    *   *예: JSON 출력을 파이썬 딕셔너리로 변환하여 특정 필드(`reasoning`, `answer`)만 추출해 평가*
*   **Runnable 객체화**: "프롬프트 + 모델 + 파서"를 하나의 실행 단위로 묶어서 관리

---

## 5. 워크플로우 (Workflow)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          평가 워크플로우                               │
└─────────────────────────────────────────────────────────────────────┘

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

### 5.1. 데이터셋 구축
테스트하고 싶은 케이스(질문+답변)를 CSV 또는 코드로 LangSmith에 업로드.
*   *Tip: 입력 변수가 여러 개라면 데이터셋에도 컬럼을 나눠서 저장 (예: `input_query`, `retrieved_docs`).*

### 5.2. 파이프라인 정의 (Pipeline Definition)
*   프롬프트 템플릿 작성 (버전 관리).
*   모델 파라미터 설정.
*   출력 파서(Output Parser) 연결.

### 5.3. 평가 실행 (Evaluation Run)
스크립트를 실행하여 전체 데이터셋에 대해 파이프라인 실행 및 채점.
*   *매핑 로직 적용: `Dataset Input` -> `Prompt Variables`*

### 5.4. 분석 및 개선
*   LangSmith 대시보드에서 점수 확인.
*   점수가 낮은 케이스(실패 사례) 분석.
*   프롬프트 수정 후 재평가 (Regression Test).

### 5.5. 회귀 테스트 (Regression Test) 기준

| 지표 | 허용 변동폭 | 조치 |
|------|------------|------|
| 평균 Correctness | -0.2 이내 | 변동폭 초과 시 머지 차단 |
| Pass Rate | -5% 이내 | 변동폭 초과 시 경고 |
| 특정 케이스 실패 | 기존 Pass → Fail | 반드시 리뷰 필요 |

## 6. 구현 계획 (Implementation Steps)

### Phase 1: 환경 설정 및 기초 구축 (1주차)
*   [x] 프로젝트 폴더 생성 (`prompt-evaluator`)
*   [x] 필수 라이브러리 설치 및 API Key 설정 (`.env`)
*   [x] 기본 디렉토리 구조 생성
*   [x] LangSmith 연동 테스트 스크립트 작성

### Phase 2: 데이터셋 구축 (2주차)
*   [x] 데이터셋 스키마 확정 (JSON 형식)
*   [x] 테스트용 데이터셋 15개 샘플 생성
*   [x] LangSmith 업로드 스크립트 (`src/data_loader.py`)
*   [x] 데이터셋 버전 관리 체계 수립

### Phase 3: 평가자 구현 (3주차)
*   [x] Rule-based 평가자 구현 (keyword, forbidden, format)
*   [x] 문자열 거리 기반 유사도 평가자 구현
*   [x] LLM-as-a-Judge 평가자 구현 (체크리스트 기반)
*   [x] 평가자 단위 테스트 작성

### Phase 4: 실행 파이프라인 구축 (4주차)
*   [x] 통합 실행 스크립트 (`main.py`)
*   [x] 실행 모드 (quick/standard/full) 구현
*   [x] LangSmith Experiment 연동 (`experiment` 명령어)
*   [x] 결과 요약 리포트 생성 기능

### Phase 5: CI/CD 연동 및 자동화 (5주차)
*   [ ] GitHub Actions 워크플로우 작성
*   [ ] PR 체크 자동화 (회귀 테스트)
*   [ ] Slack/이메일 알림 연동
*   [x] CLI 도구화 (typer 활용)

## 7. 디렉토리 구조

```
prompt-evaluator/
├── .env                        # API Key (비공개)
├── .env.example                # 환경 변수 템플릿
├── pyproject.toml              # 프로젝트 의존성
│
├── targets/                    # [평가 대상 프롬프트 - 다중 형식]
│   ├── prep_analyzer.txt       # .txt 형식
│   ├── code_review.py          # .py 형식 (SYSTEM_PROMPT, USER_PROMPT)
│   └── customer_service.xml    # .xml 형식
│
├── datasets/                   # [테스트 데이터]
│   └── prep_analyzer_data/
│       ├── test_cases.json     # 테스트케이스
│       └── expected.json       # 기대 결과 (reference)
│
├── configs/                    # [평가 설정]
│   └── prep_analyzer.yaml      # evaluators, thresholds 등
│
├── eval_prompts/               # [LLM Judge 평가 프롬프트]
│   ├── general/                # 범용 평가 기준
│   │   ├── instruction_following.txt
│   │   ├── factual_accuracy.txt
│   │   └── output_quality.txt
│   └── oneonone/               # 1on1 특화 평가 기준
│       ├── purpose_alignment.txt
│       ├── coaching_quality.txt
│       ├── tone_appropriateness.txt
│       └── sensitive_topic_handling.txt
│
├── src/
│   ├── __init__.py
│   ├── pipeline.py             # 핵심 파이프라인 로직
│   ├── data_loader.py          # 데이터 로더 (다중 형식 지원)
│   ├── report.py               # 결과 리포터
│   └── evaluators/
│       ├── __init__.py
│       ├── rule_based.py       # Rule-based 평가자
│       ├── similarity.py       # 유사도 평가자 (임베딩/문자열)
│       └── llm_judge.py        # LLM-as-Judge 평가자
│
├── results/                    # 평가 결과 저장
│   └── {name}/                 # 프롬프트별 폴더
│       ├── {mode}_{timestamp}.json
│       └── {mode}_{timestamp}.md
│
├── tests/                      # 단위 테스트
│
├── .claude/skills/             # Claude Code 스킬
│   ├── llm_judge_generator/    # 평가기준 생성 스킬
│   ├── test_case_generator/    # 테스트케이스 생성 스킬
│   └── prompt_ab_comparator/   # A/B 비교 스킬
│
├── main.py                     # CLI 진입점
└── docs/                       # 문서
```

> **사용법**: `python main.py eval --name prep_analyzer` 실행 시 `targets/prep_analyzer.[txt|py|xml]`, `datasets/prep_analyzer_data/`, `configs/prep_analyzer.yaml` 자동 로드

## 8. CLI 명령어 (Command Reference)

### 8.1. 평가 명령어

```bash
# 로컬 평가 (빠른 개발용)
poetry run python main.py eval --name prep_analyzer
poetry run python main.py eval --name prep_analyzer --mode full
poetry run python main.py eval --name prep_analyzer --case-id case_001,case_002

# LangSmith Experiment (정식 평가)
poetry run python main.py experiment --name prep_analyzer
poetry run python main.py experiment --name prep_analyzer --mode full
poetry run python main.py experiment --name prep_analyzer --prefix "v2.0-test"
poetry run python main.py experiment --name prep_analyzer --version v1.0  # 특정 프롬프트 버전

# 데이터셋 업로드
poetry run python main.py upload --name prep_analyzer
```

### 8.2. 프롬프트 버전 관리

```bash
# 프롬프트 푸시 (LangSmith에 업로드)
poetry run python main.py prompt push --name prep_analyzer
poetry run python main.py prompt push --name prep_analyzer --tag v1.0
poetry run python main.py prompt push --name prep_analyzer --key SYSTEM_PROMPT  # .py 파일의 특정 키

# 프롬프트 풀 (LangSmith에서 가져오기)
poetry run python main.py prompt pull --name prep_analyzer
poetry run python main.py prompt pull --name prep_analyzer --tag v1.0 --save

# 프롬프트 키 조회 (.py/.xml 파일용)
poetry run python main.py prompt keys --name prep_analyzer

# 프롬프트 버전 목록
poetry run python main.py prompt versions --name prep_analyzer
```

### 8.3. 유틸리티 명령어

```bash
# 평가 세트 목록
poetry run python main.py list

# 사용 가능한 평가 기준
poetry run python main.py criteria
```

## 9. CI/CD 연동 계획

### 9.1. GitHub Actions 워크플로우

```yaml
# .github/workflows/eval_on_pr.yml
name: Prompt Evaluation

on:
  pull_request:
    paths:
      - 'targets/**'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e .
      - name: Run evaluation
        env:
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python main.py eval --mode standard
      - name: Check regression
        run: python main.py check-regression --threshold 0.05
```

### 9.2. 트리거 조건

| 트리거 | 평가 모드 | 용도 |
|--------|----------|------|
| `targets/**` 변경 PR | `standard` | 프롬프트 변경 검증 |
| 수동 실행 | `full` | 릴리즈 전 전수 검사 |
| 매일 스케줄 (선택) | `quick` | 모델 드리프트 감지 |

## 10. 비용 및 성능 고려사항

### 10.1. 예상 비용 (100개 테스트 기준)

| 구성요소 | 단가 | 100회 비용 |
|----------|------|-----------|
| 타겟 LLM 호출 (GPT-4o) | ~$0.01/call | ~$1.00 |
| LLM-Judge (GPT-4o) | ~$0.01/call | ~$1.00 |
| Embedding (ada-002) | ~$0.0001/call | ~$0.01 |
| **총합** | | **~$2.00** |

### 10.2. 성능 최적화 전략

*   **캐싱**: 동일 입력에 대한 LLM 응답 캐싱 (개발 중)
*   **샘플링**: LLM-Judge는 전체의 20%만 실행 (PR 검증 시)
*   **병렬 처리**: 5개 동시 요청으로 처리 시간 단축
*   **조기 종료**: Rule-based 실패 시 LLM-Judge 스킵

## 11. 성공 지표 (KPI)

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 테스트 커버리지 | ≥ 80% | (테스트된 프롬프트 / 전체 프롬프트) |
| 평균 Pass Rate | ≥ 90% | (통과 케이스 / 전체 케이스) |
| 평가 실행 시간 | ≤ 5분 (100개) | CI 로그 |
| 회귀 탐지율 | 100% | 의도적 회귀 테스트로 검증 |

---

## 12. Claude Skill: 평가기준 자동생성

### 12.1. 개요

프롬프트를 분석하여 LLM-as-Judge Evaluator를 자동으로 생성하는 Claude Skill입니다.
Claude Code에서 프롬프트를 붙여넣고 "평가기준 만들어줘"라고 하면 `eval_prompts/` 폴더에 평가 프롬프트 파일을 생성합니다.

### 12.2. 사용법

**Claude Code에서:**
1. 이 프로젝트 폴더에서 Claude Code 실행
2. 평가할 프롬프트명 확인 (`targets/` 폴더에 위치)
3. `/eval-criteria [프롬프트명]` 또는 "평가기준 만들어줘" 입력
4. 생성된 평가 프롬프트 파일이 `eval_prompts/{도메인}/` 폴더에 저장됨
5. `configs/{프롬프트명}.yaml`에 criteria 자동 추가

**스킬 파일 위치:**
```
.claude/skills/llm_judge_generator/
├── SKILL.md                    # 메인 스킬 문서
└── references/
    ├── general_criteria.md     # 범용 평가기준
    └── oneonone_criteria.md    # 1on1 도메인 평가기준
```

### 12.3. 현재 지원하는 평가 기준

```bash
# 사용 가능한 평가 기준 확인
poetry run python main.py criteria
```

**일반 평가 기준:**
- `instruction_following`: 프롬프트 지시사항 준수도
- `factual_accuracy`: 사실 정확성 / 할루시네이션 검사
- `output_quality`: 전반적 출력 품질

**1on1 Meeting 특화 평가 기준:**
- `purpose_alignment`: 1on1 미팅 목적 부합도
- `coaching_quality`: 코칭 힌트 품질
- `tone_appropriateness`: 톤/어조 적절성
- `sensitive_topic_handling`: 민감한 주제 처리

---

## 13. 향후 계획 (Roadmap)

### 13.1. 평가 체계 성숙도 로드맵

```
┌─────────────────────────────────────────────────────────────┐
│                    평가 체계 성숙도 단계                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [현재] Stage 1: Bootstrap                                  │
│  ├── 자동생성으로 "일단 시작"                                 │
│  ├── 빠르게 피드백 루프 구축                                  │
│  └── 기본 평가 기준으로 MVP 검증                             │
│                                                             │
│  [다음] Stage 2: Curate                                     │
│  ├── 실전 좋은/나쁜 출력 수집 (태깅 시스템)                   │
│  ├── 자동생성 평가기준 검증 & 수정                           │
│  └── Golden Dataset 점진적 구축                             │
│                                                             │
│  [향후] Stage 3: Refine                                     │
│  ├── 실전 데이터 기반 평가기준 재정의                         │
│  ├── Edge case 중심 테스트 강화                             │
│  └── 도메인 전문가 리뷰 반영                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 13.2. 실전 데이터 수집 파이프라인 (Stage 2 계획)

**목표**: 운영 중 발생하는 좋은/나쁜 출력을 수집하여 평가 체계 개선에 활용

**계획된 기능:**

#### A. 출력 태깅 시스템
```python
# 계획된 인터페이스
from src.data import tag_output

# 좋은 출력 태깅
tag_output(
    run_id="langsmith_run_id",
    quality="good",
    tags=["coaching_quality", "empathetic"],
    notes="번아웃 신호를 잘 감지하고 적절히 대응함"
)

# 나쁜 출력 태깅
tag_output(
    run_id="langsmith_run_id",
    quality="bad",
    tags=["status_question", "missed_signal"],
    notes="업무 현황 질문으로 1on1 목적에 맞지 않음"
)
```

#### B. Golden Dataset 자동 구축
```bash
# 계획된 CLI
poetry run python main.py collect-golden \
    --source langsmith \
    --quality good \
    --min-score 0.9 \
    --output datasets/golden_v1/
```

#### C. 평가기준 개선 제안
```bash
# 계획된 CLI
poetry run python main.py analyze-failures \
    --experiment prep_analyzer_v2 \
    --suggest-improvements
```

**예상 출력:**
```
실패 케이스 분석 결과:
- 총 15개 케이스 중 3개 실패 (80% pass rate)

실패 패턴:
1. "avoided" 응답 처리 (2건)
   → sensitive_topic_handling 평가 기준 강화 제안

2. 서베이만 있는 케이스 (1건)
   → survey_only 응답에 대한 평가 기준 추가 제안

제안된 평가 기준 수정:
- sensitive_topic_handling: "회피 응답 시 대안 제시" 체크리스트 추가
```

### 13.3. Claude Skill 고도화 계획

#### A. 단기 개선 (v1.1)
- [ ] 프롬프트 언어 자동 감지 (한글/영문)
- [ ] 도메인 힌트 옵션 추가 (`--domain customer_service`)
- [ ] 기존 평가 기준과 중복 체크

#### B. 중기 개선 (v2.0)
- [ ] Few-shot 예시 자동 생성
- [ ] 프롬프트 버전 diff 기반 평가 기준 업데이트 제안
- [ ] LangSmith UI 직접 등록 API 연동

#### C. 장기 비전
- [ ] 실전 데이터 기반 평가 기준 자동 개선
- [ ] A/B 테스트 결과 기반 평가 기준 가중치 조정
- [ ] 도메인별 평가 기준 템플릿 라이브러리

### 13.4. 구현 우선순위

| 우선순위 | 기능 | 예상 효과 | 예상 소요 |
|---------|------|----------|----------|
| P0 | 현재 시스템으로 실전 사용 | 피드백 수집 시작 | 즉시 |
| P1 | 출력 태깅 CLI 추가 | 수동 Golden Dataset 구축 | 1일 |
| P2 | 실패 케이스 분석 리포트 | 개선 포인트 가시화 | 2일 |
| P3 | Claude Skill 도메인 힌트 | 자동생성 품질 향상 | 1일 |
| P4 | Golden Dataset 자동 구축 | 데이터 축적 자동화 | 3일 |

---

## 14. 참고: 평가 체계 설계 원칙

### 14.1. 자동생성이 효과적인 경우
- 새 프롬프트 만들 때 초기 평가기준 빠르게 설정
- "빠뜨린 평가 차원 없나?" 체크리스트 용도
- 형식 검증 (JSON 구조, 필수 필드 등)
- 명시적 규칙이 프롬프트에 있는 경우 (AVOID, MUST 등)

### 14.2. 실전 데이터가 필수인 경우
- "이게 좋은 코칭 힌트인가?" 같은 품질 판단
- Edge case (번아웃 신호, 회피 응답 등)
- 실제 리더/유저 피드백 반영
- 도메인 전문 지식이 필요한 판단

### 14.3. 하이브리드 접근 권장
```
자동생성 (Bootstrap)
    │
    ▼
실전 사용 & 태깅
    │
    ▼
수동 검증 & 수정 (Curate)
    │
    ▼
Golden Dataset 구축
    │
    ▼
평가기준 재정의 (Refine)
    │
    └──▶ 반복
```

---

## 15. 기술 구현 세부사항

### 15.1. 다중 프롬프트 형식 지원

`src/data_loader.py`에서 다음 파일 형식을 지원합니다:

| 형식 | 로더 함수 | 추출 방식 |
|------|----------|----------|
| `.txt` | `load_prompt_file()` | 파일 전체를 `{"template": ...}`로 반환 |
| `.py` | `_load_prompt_from_py()` | AST 파싱으로 `*_PROMPT` 변수 추출 |
| `.xml` | `_load_prompt_from_xml()` | XML 파싱으로 자식 태그를 키로 추출 |

**파일 탐색 우선순위:**
1. `{name}_prompt.txt` → `{name}_prompt.py` → `{name}_prompt.xml`
2. `{name}.txt` → `{name}.py` → `{name}.xml`

### 15.2. eval_prompts 템플릿 작성 규칙

LLM Judge 평가 프롬프트(`eval_prompts/**/*.txt`)에서 JSON 예시를 포함할 때:

```
## Response Format (JSON):
{{
    "checklist": {{
        "item1": 0 or 1,
        "item2": 0 or 1
    }},
    "score": <float 0-1>
}}
```

> **중요**: Python의 `.format()` 메서드와 충돌을 방지하기 위해 JSON의 중괄호는 `{{`, `}}`로 이스케이프해야 합니다.
> 플레이스홀더 `{prompt}`, `{input}`, `{output}`은 단일 중괄호를 사용합니다.

### 15.3. LangSmith Experiment 연동

`src/pipeline.py`의 `run_langsmith_experiment()` 함수가 다음을 수행합니다:

1. 데이터셋을 LangSmith에 업로드 (기존 데이터셋은 삭제 후 재생성)
2. `evaluate()` 함수로 Experiment 실행
3. 설정된 LLM Judge 평가자 자동 추가
4. 결과를 LangSmith 대시보드에 기록

```python
# 내부 동작
results = evaluate(
    target,
    data=dataset_name,
    evaluators=[keyword_evaluator, forbidden_evaluator, format_evaluator, ...],
    experiment_prefix=experiment_prefix,
)
```
