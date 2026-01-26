# PromptOps 확장 기획서

> **목표**: "프롬프트를 잘 짠다" → "프롬프트 변경이 품질에 미치는 영향을 계량하고 회귀를 막는 PromptOps를 구축했다"

---

## 1. PromptOps 개념

### 1.1. DevOps vs PromptOps

```
DevOps                          PromptOps
──────────────────────────────────────────────────────────
코드 저장소 (Git)         →     프롬프트 저장소 (LangSmith)
버전 관리 (tag, branch)   →     프롬프트 버전 + 메타데이터
CI/CD 파이프라인          →     평가 파이프라인
유닛 테스트               →     Rule-based 평가
통합 테스트               →     LLM Judge 평가
A/B 테스트                →     프롬프트 A/B 비교
모니터링 (APM)            →     LangSmith Tracing
롤백                      →     이전 버전 복원
```

### 1.2. PromptOps 운영 사이클

```
┌─────────────────────────────────────────────────────────────┐
│                     PromptOps Lifecycle                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│   │  1.저장   │───▶│ 2.버전관리 │───▶│  3.테스트  │            │
│   │ (Store)  │    │(Version) │    │  (Test)  │             │
│   └──────────┘    └──────────┘    └────┬─────┘             │
│                                        │                    │
│                                        ▼                    │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│   │ 6.재배포  │◀───│ 5.개선    │◀───│4.모니터링 │            │
│   │(Deploy) │    │(Improve) │    │(Monitor) │             │
│   └──────────┘    └──────────┘    └──────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| 단계 | 활동 | 도구/산출물 |
|:----:|------|------------|
| 1 | 프롬프트 중앙 저장 | `targets/{name}/prompt.*` |
| 2 | 버전·메타데이터 관리 | `.metadata.yaml`, LangSmith |
| 3 | 자동 평가 + 회귀 테스트 | CI/CD, Rule-based, LLM Judge |
| 4 | 실시간 성능 추적 | LangSmith Tracing, 리포트 |
| 5 | 실패 분석 → 개선 | 패턴 분석, Human Spot-check |
| 6 | 승인 후 배포 | 버전 태그, 롤백 지원 |

---

## 2. 현재 상태 (As-Is)

### 2.1. 구현된 기능

| 단계 | 기능 | 상태 |
|:----:|------|:----:|
| 저장 | 프롬프트 파일 관리 (.txt, .py, .xml, .md) | ✅ |
| 버전 | LangSmith push/pull, 태그 | ✅ |
| 테스트 | Rule-based (키워드, 금지어) | ✅ |
| 테스트 | LLM Judge (체크리스트) | ✅ |
| 테스트 | 유사도 평가 (문자열, 임베딩) | ✅ |
| 모니터링 | LangSmith Experiment 기록 | ✅ |

### 2.2. 미구현 기능

| 단계 | 기능 | 우선순위 |
|:----:|------|:--------:|
| 버전 | owner, change_log 메타데이터 | P1 |
| 버전 | 데이터셋 버전 관리 | P1 |
| 테스트 | 회귀 테스트 (기준선 비교) | P1 |
| 테스트 | CI/CD 연동 (GitHub Actions) | P1 |
| 모니터링 | 자동 리포트 생성 | P1 |
| 모니터링 | 실패 패턴 분석 | P2 |
| 개선 | Human spot-check | P2 |
| 배포 | 버전별 롤백 지원 | P2 |

### 2.3. 현재 폴더 구조

```
prompt-evaluator/
├── main.py                      # CLI (Typer)
├── configs/
│   └── config.py                # 기본 설정값
├── src/
│   ├── pipeline.py              # 평가 파이프라인
│   ├── evaluators/
│   │   ├── rule_based.py
│   │   ├── llm_judge.py
│   │   └── similarity.py
│   └── loaders/
│       ├── prompt_loader.py
│       └── dataset_loader.py
├── utils/
│   ├── models.py
│   ├── config_validator.py
│   ├── langsmith_prompts.py
│   └── langsmith_datasets.py
├── targets/{name}/
│   ├── prompt.*
│   └── config.yaml
├── datasets/{name}/
│   ├── test_cases.json
│   └── expected.json
└── eval_prompts/{domain}/
    └── {criterion}.txt
```

---

## 3. 목표 상태 (To-Be)

### 3.1. PromptOps 4대 축

```
┌─────────────────────────────────────────────────────────────┐
│                        PromptOps                            │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   버전 관리   │   평가 체계   │   회귀 테스트  │    리포트      │
│  Versioning │  Evaluation │  Regression │   Reporting    │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ • 프롬프트    │ • Rule-based│ • 기준선 관리  │ • 실패 분석    │
│   메타데이터  │ • LLM Judge │ • CI 연동     │ • 버전 비교    │
│ • 데이터셋    │ • Human     │ • 자동 차단   │ • 트렌드      │
│   스냅샷     │   spot-check│              │               │
└─────────────┴─────────────┴─────────────┴─────────────────┘
```

### 3.2. 확장 폴더 구조

```
prompt-evaluator/
├── main.py
├── configs/
│   └── config.py
├── src/
│   ├── pipeline.py
│   ├── evaluators/
│   │   ├── rule_based.py
│   │   ├── llm_judge.py
│   │   ├── similarity.py
│   │   └── human_feedback.py      # NEW
│   ├── loaders/
│   │   ├── prompt_loader.py
│   │   └── dataset_loader.py
│   ├── versioning/                 # NEW
│   │   ├── __init__.py
│   │   ├── prompt_metadata.py
│   │   └── dataset_snapshot.py
│   ├── regression/                 # NEW
│   │   ├── __init__.py
│   │   ├── baseline.py
│   │   └── comparator.py
│   └── reporters/                  # NEW
│       ├── __init__.py
│       ├── failure_analyzer.py
│       └── markdown_reporter.py
├── utils/
│   └── (기존 유지)
├── targets/{name}/
│   ├── prompt.*
│   ├── config.yaml
│   └── .metadata.yaml              # NEW
├── datasets/{name}/
│   ├── test_cases.json
│   ├── expected.json
│   └── .versions.yaml              # NEW
├── results/                        # NEW
│   └── {name}/
│       ├── baseline.json
│       └── {timestamp}.json
└── .github/workflows/              # NEW
    └── prompt-eval.yml
```

---

## 4. 구현 계획

### Phase 1: 버전 관리 강화

#### 4.1.1. 프롬프트 메타데이터

**신규 파일**: `targets/{name}/.metadata.yaml`

```yaml
owner: john@example.com
created_at: "2026-01-20"
current_version: v1.2

versions:
  v1.0:
    date: "2026-01-20"
    author: john@example.com
    changes: "Initial version"
    langsmith_hash: "abc123"
  v1.1:
    date: "2026-01-22"
    author: jane@example.com
    changes: "톤 개선: 더 친근하게"
    langsmith_hash: "def456"
```

**신규 모듈**: `src/versioning/prompt_metadata.py`

```python
def load_metadata(prompt_name: str) -> dict
def save_metadata(prompt_name: str, metadata: dict)
def add_version(prompt_name: str, version: str, author: str, changes: str)
def get_current_version(prompt_name: str) -> str
```

**CLI 추가**:
```bash
poetry run python main.py prompt info --name prep_generate
poetry run python main.py prompt push --name prep_generate \
    --tag v1.2 --author "john@example.com" --changes "민감 주제 처리 강화"
```

**리팩토링**: `utils/langsmith_prompts.py`
- `push_prompt()`: 메타데이터 자동 기록 연동

#### 4.1.2. 데이터셋 버전 관리

**신규 파일**: `datasets/{name}/.versions.yaml`

```yaml
current_hash: "abc123"
case_count: 15

versions:
  - hash: "abc123"
    date: "2026-01-25"
    case_count: 15
    changes:
      added: ["edge_case_03"]
      modified: []
      removed: []
```

**신규 모듈**: `src/versioning/dataset_snapshot.py`

```python
def compute_hash(dataset_path: str) -> str
def track_changes(prompt_name: str) -> dict
def create_snapshot(prompt_name: str, message: str)
def list_snapshots(prompt_name: str) -> list
```

---

### Phase 2: 회귀 테스트 체계

#### 4.2.1. 기준선(Baseline) 관리

**신규 파일**: `results/{name}/baseline.json`

```json
{
  "version": "v1.2",
  "dataset_hash": "abc123",
  "created_at": "2026-01-25T10:00:00",
  "summary": {
    "total": 15,
    "passed": 13,
    "failed": 2,
    "pass_rate": 0.867,
    "avg_score": 0.82
  },
  "by_evaluator": {
    "keyword_inclusion": {"avg": 0.95, "failures": 1},
    "tone_appropriateness": {"avg": 0.78, "failures": 2}
  },
  "cases": {
    "scenario_01": {"passed": true, "score": 0.9},
    "scenario_02": {"passed": false, "score": 0.6, "fail_reason": "tone"}
  }
}
```

**신규 모듈**: `src/regression/baseline.py`

```python
def save_baseline(prompt_name: str, results: dict)
def load_baseline(prompt_name: str) -> dict | None
def set_as_baseline(prompt_name: str, result_file: str)
```

#### 4.2.2. 회귀 비교

**신규 모듈**: `src/regression/comparator.py`

```python
@dataclass
class RegressionReport:
    baseline_version: str
    current_version: str
    pass_rate_delta: float      # -0.05 = 5% 하락
    avg_score_delta: float
    is_regression: bool
    regression_reasons: list[str]
    new_failures: list[str]     # Pass → Fail
    new_passes: list[str]       # Fail → Pass

def compare_with_baseline(prompt_name: str, current: dict) -> RegressionReport
```

**회귀 판정 기준** (config 확장):

```yaml
# targets/{name}/config.yaml
regression:
  enabled: true
  max_pass_rate_drop: 0.05      # 5% 초과 하락 시 회귀
  max_avg_score_drop: 0.1       # 0.1점 초과 하락 시 회귀
  block_on_new_failure: true    # Pass→Fail 발생 시 차단
```

**CLI 추가**:
```bash
poetry run python main.py baseline set --name prep_generate
poetry run python main.py experiment --name prep_generate --compare-baseline
poetry run python main.py regression check --name prep_generate
```

#### 4.2.3. GitHub Actions CI

**신규 파일**: `.github/workflows/prompt-eval.yml`

```yaml
name: Prompt Evaluation

on:
  pull_request:
    paths:
      - 'targets/**'
      - 'datasets/**'
      - 'eval_prompts/**'

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
        run: |
          pip install poetry
          poetry install

      - name: Detect changed prompts
        id: changes
        run: |
          # targets/ 하위 변경된 프롬프트 감지

      - name: Run evaluation
        env:
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          poetry run python main.py experiment --name ${{ steps.changes.outputs.prompt }}

      - name: Check regression
        run: |
          poetry run python main.py regression check --name ${{ steps.changes.outputs.prompt }}

      - name: Comment PR
        uses: actions/github-script@v7
        with:
          script: |
            // 평가 결과를 PR 코멘트로 작성
```

---

### Phase 3: 리포트 시스템

#### 4.3.1. 실패 분석 자동화

**신규 모듈**: `src/reporters/failure_analyzer.py`

```python
@dataclass
class FailurePattern:
    pattern_type: str       # "long_input", "sensitive_topic"
    affected_cases: list[str]
    description: str
    frequency: float        # 전체 실패 중 비율

@dataclass
class FailureAnalysis:
    total_failures: int
    by_evaluator: dict[str, list[str]]  # evaluator → [case_ids]
    patterns: list[FailurePattern]
    recommendations: list[str]

def analyze_failures(results: dict) -> FailureAnalysis
def detect_patterns(failures: list[dict]) -> list[FailurePattern]
```

**패턴 감지 예시**:
- "민감 주제 케이스에서 tone_appropriateness 실패율 40%"
- "긴 대화(10턴 이상)에서 format 오류 빈발"
- "특정 키워드('퇴사', '연봉') 포함 시 실패 집중"

#### 4.3.2. Markdown 리포트

**신규 모듈**: `src/reporters/markdown_reporter.py`

**출력 예시**: `results/{name}/{timestamp}_report.md`

```markdown
# Evaluation Report: prep_generate

> **Version**: v1.2 | **Date**: 2026-01-25 10:30:00
> **Dataset**: 15 cases (hash: abc123)

## Summary

| Metric | Value | vs Baseline |
|--------|:-----:|:-----------:|
| Pass Rate | 86.7% | -2.3% ⚠️ |
| Avg Score | 0.82 | +0.01 ✅ |

## Evaluator Breakdown

| Evaluator | Avg | Failures | Change |
|-----------|:---:|:--------:|:------:|
| keyword_inclusion | 0.95 | 1 | - |
| tone_appropriateness | 0.78 | 2 | -1 ⚠️ |

## Failure Analysis

### New Failures (Pass → Fail)
- `edge_case_03`: tone_appropriateness (0.4)

### Patterns Detected
1. **민감 주제 처리** (2/2 failures, 100%)
   - Affected: edge_case_03, scenario_12
   - Recommendation: 민감 주제 프롬프트 지시 강화

## Detailed Results
[케이스별 상세 테이블]
```

**CLI 추가**:
```bash
poetry run python main.py report --name prep_generate --format markdown
poetry run python main.py experiment --name prep_generate --save --report
```

---

### Phase 4: 평가 체계 강화

#### 4.4.1. Human Spot-Check

**신규 모듈**: `src/evaluators/human_feedback.py`

```python
@dataclass
class HumanFeedback:
    case_id: str
    reviewer: str
    timestamp: str
    overall_rating: int         # 1-5
    checklist: dict[str, bool]
    feedback: str
    tags: list[str]             # ["tone_issue", "factual_error"]

def generate_review_form(prompt_name: str, sample_size: int = 10) -> str
def submit_feedback(prompt_name: str, feedback: HumanFeedback)
def aggregate_human_scores(prompt_name: str) -> dict
```

**워크플로우**:
1. 매주 10개 샘플 자동 추출
2. 리뷰 폼 생성 (Markdown)
3. 리뷰어가 피드백 제출
4. 결과 집계 → 리포트 반영

#### 4.4.2. 평가자 가중치

**config.yaml 확장**:

```yaml
evaluators:
  - type: rule_based
    weight: 0.2
    checks:
      - keyword_inclusion
      - forbidden_word_check

  - type: llm_judge
    weight: 0.6
    criteria:
      - tone_appropriateness
      - sensitive_topic_handling

  - type: human_feedback
    weight: 0.2
    sample_rate: 0.1      # 10% 샘플링
```

**리팩토링**: `src/pipeline.py`
- 가중 평균 계산 로직 추가

---

## 5. 리팩토링 항목

### 5.1. 필수 리팩토링

| 파일 | 변경 내용 | Phase |
|------|----------|:-----:|
| `main.py` | CLI 명령어 추가 (baseline, regression, report) | 1-3 |
| `src/pipeline.py` | 결과 저장, 가중치, 리포트 연동 | 1-3 |
| `utils/langsmith_prompts.py` | 메타데이터 자동 기록 | 1 |
| `utils/langsmith_datasets.py` | 버전 추적 연동 | 1 |
| `configs/config.py` | 회귀 임계값, 가중치 기본값 | 2 |
| `utils/config_validator.py` | 새 필드 검증 | 2 |

### 5.2. 스키마 변경

**config.yaml 확장**:

```yaml
# 기존 필드
name: prep_generate
output_format: text
eval_prompts_domain: oneonone
evaluators: [...]
thresholds:
  pass_rate: 0.85
  min_score: 0.70
run_mode: full

# 추가 필드
regression:                    # NEW
  enabled: true
  max_pass_rate_drop: 0.05
  max_avg_score_drop: 0.1
  block_on_new_failure: true

reporting:                     # NEW
  auto_generate: true
  format: markdown
```

---

## 6. 신규 생성 파일 목록

### 6.1. 소스 코드

| 경로 | 설명 |
|------|------|
| `src/versioning/__init__.py` | 버전 관리 모듈 |
| `src/versioning/prompt_metadata.py` | 프롬프트 메타데이터 |
| `src/versioning/dataset_snapshot.py` | 데이터셋 스냅샷 |
| `src/regression/__init__.py` | 회귀 테스트 모듈 |
| `src/regression/baseline.py` | 기준선 관리 |
| `src/regression/comparator.py` | 회귀 비교 |
| `src/reporters/__init__.py` | 리포트 모듈 |
| `src/reporters/failure_analyzer.py` | 실패 분석 |
| `src/reporters/markdown_reporter.py` | MD 리포트 |
| `src/evaluators/human_feedback.py` | Human 평가 |

### 6.2. 설정/워크플로우

| 경로 | 설명 |
|------|------|
| `.github/workflows/prompt-eval.yml` | CI/CD |
| `results/.gitkeep` | 결과 저장 폴더 |

### 6.3. 메타데이터 (프롬프트별)

| 경로 | 설명 |
|------|------|
| `targets/{name}/.metadata.yaml` | 프롬프트 메타 |
| `datasets/{name}/.versions.yaml` | 데이터셋 버전 |
| `results/{name}/baseline.json` | 기준선 |

---

## 7. 마일스톤

### Phase 1: 버전 관리 (Week 1)
- [ ] `src/versioning/prompt_metadata.py`
- [ ] `src/versioning/dataset_snapshot.py`
- [ ] `main.py`에 `prompt info` 명령어
- [ ] `langsmith_prompts.py` 리팩토링

### Phase 2: 회귀 테스트 (Week 2)
- [ ] `src/regression/baseline.py`
- [ ] `src/regression/comparator.py`
- [ ] `main.py`에 `baseline`, `regression` 명령어
- [ ] `.github/workflows/prompt-eval.yml`

### Phase 3: 리포트 (Week 3)
- [ ] `src/reporters/failure_analyzer.py`
- [ ] `src/reporters/markdown_reporter.py`
- [ ] `main.py`에 `report` 명령어
- [ ] `pipeline.py` 리팩토링

### Phase 4: 평가 강화 (Week 4)
- [ ] `src/evaluators/human_feedback.py`
- [ ] 평가자 가중치 로직
- [ ] `config_validator.py` 업데이트
- [ ] 문서 업데이트

---

## 8. 성공 지표

### 정량적
- [ ] 프롬프트 변경 시 자동 회귀 테스트 실행
- [ ] PR에 평가 결과 자동 코멘트
- [ ] 회귀 발생 시 머지 차단
- [ ] 실패 패턴 자동 감지 (80%+ 정확도)

### 정성적
- [ ] "프롬프트 변경의 영향을 숫자로 설명 가능"
- [ ] "어떤 케이스가 왜 실패했는지 즉시 파악 가능"
- [ ] "버전별 성능 추이 한눈에 확인 가능"

---

## 9. 참고

- [현재 기능 명세](./SPECIFICATION.md)
- [사용 가이드](./GUIDE.md)
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md)

---

**Version**: 1.0.0
**Created**: 2026-01-26
