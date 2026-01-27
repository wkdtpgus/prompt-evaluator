# PromptOps 확장 기획서

> **목표**: "프롬프트를 잘 짠다" → "프롬프트 변경이 품질에 미치는 영향을 계량하고 회귀를 막는 PromptOps를 구축했다"

---

## 1. PromptOps란?

### 1.1. 정의

**PromptOps**는 AI 시스템에서 프롬프트를 **확장·운영·관리**하는 일련의 운영 실무(Operations)입니다.

단순한 프롬프트 설계(Prompt Engineering)를 넘어:
- 프롬프트 **버전 관리**
- 성능 **모니터링**
- **A/B 테스팅**
- 조직 내 **공유/표준화**

까지 포함하는 전체 생명주기 관리 체계입니다.

> 🚗 **비유**: Prompt Engineering이 "엔진 설계"라면, PromptOps는 "자동차의 유지·점검·최적화 운영 전체"

### 1.2. 왜 PromptOps가 필요한가?

| 문제 | 설명 | PromptOps 해결책 |
|------|------|-----------------|
| **모델 업데이트** | 모델 버전 변경 시 기존 프롬프트 성능 저하 | 회귀 테스트로 자동 감지 |
| **Prompt Drift** | 시간 경과에 따른 출력 품질 저하 | 지속적 모니터링 |
| **품질 편차** | 팀별 프롬프트 품질 불균일 | 중앙 저장소 + 표준화 |
| **변경 영향 불명** | 수정이 어떤 영향을 미치는지 모름 | A/B 테스트 + 정량 비교 |
| **재사용 불가** | 좋은 프롬프트가 개인에게만 존재 | 공유 + 버전 관리 |

### 1.3. 실무 적용 사례

#### 사례 1: Dify의 Prompt Template PromptOps

**무엇을 했나?**
- 팀 단위로 프롬프트를 저장·공유·버전 관리
- 여러 프롬프트를 성능 비교하는 구조 구축

**사용처:**
- 다국어 광고 카피 생성
- SNS 게시물, 이메일 콘텐츠 자동 생성
- 브랜드 톤·스타일에 맞춘 텍스트 생성

**핵심 Ops:** 프롬프트 저장소 + 성능 비교 + 버전 관리

#### 사례 2: A/B 테스트 기반 프롬프트 최적화

**목표:** 여러 스타일/파라미터 프롬프트의 성능 차이 테스트

**실행 내용:**
1. Prompt A vs Prompt B를 동시에 서비스 배포
2. 반응 품질·정확도·응답 속도 모니터링
3. 데이터 기반으로 더 좋은 프롬프트 선택 → 운영본 반영

**핵심 Ops:** 지속적 테스트 + 데이터 기반 프롬프트 개선

#### 사례 3: 조직 내 프롬프트 중앙 저장 + 분류 체계

**문제:** 프롬프트가 개발팀, 마케팅팀, CS팀 등에서 산발적 생성

**솔루션:**
1. 프롬프트를 중앙 저장소에 등록
2. 목적별 분류 (요약/번역/문의응답/광고문)
3. 버전 변경 기록 + 메타데이터로 성능 추적

**효과:**
- 중복 개발 감소
- 일관된 답변·서비스 품질 유지

---

## 2. DevOps vs PromptOps 비교

```
DevOps                          PromptOps
──────────────────────────────────────────────────────────
코드 저장소 (Git)         →     프롬프트 저장소 (LangSmith/Langfuse)
버전 관리 (tag, branch)   →     프롬프트 버전 + 메타데이터
CI/CD 파이프라인          →     평가 파이프라인
유닛 테스트               →     Rule-based 평가 (빠른 검증)
통합 테스트               →     LLM Judge 평가 (품질 판단)
A/B 테스트                →     프롬프트 A/B 비교
모니터링 (APM)            →     LangSmith Tracing
롤백                      →     이전 버전 복원
코드 리뷰                 →     프롬프트 리뷰 + Human Spot-check
```

---

## 3. PromptOps 운영 사이클

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

| 단계 | 활동 | 산출물 | 본 프로젝트 구현 |
|:----:|------|--------|-----------------|
| 1 | 프롬프트 중앙 저장 | `targets/{name}/prompt.*` | ✅ 구현됨 |
| 2 | 버전·메타데이터 관리 | `.metadata.yaml`, LangSmith | 🔧 확장 예정 |
| 3 | 자동 평가 + 회귀 테스트 | CI/CD, Rule-based, LLM Judge | 🔧 확장 예정 |
| 4 | 실시간 성능 추적 | LangSmith Tracing, 리포트 | 🔧 확장 예정 |
| 5 | 실패 분석 → 개선 | 패턴 분석, Human Spot-check | 🔧 확장 예정 |
| 6 | 승인 후 배포 | 버전 태그, 롤백 지원 | 🔧 확장 예정 |

---

## 4. 현재 상태 (As-Is)

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
├── main.py                      # CLI 엔트리포인트 (앱 조립만)
├── cli/                         # CLI 명령어 모듈
│   ├── prompt.py                # prompt 서브커맨드
│   ├── baseline.py              # baseline 서브커맨드
│   ├── experiment.py            # experiment, regression 명령어
│   ├── config.py                # validate, criteria 명령어
│   └── dataset.py               # list, upload 명령어
├── configs/
│   └── config.py                # 기본 설정값
├── src/
│   ├── pipeline.py              # 평가 파이프라인
│   ├── evaluators/
│   │   ├── rule_based.py
│   │   ├── llm_judge.py
│   │   └── similarity.py
│   ├── loaders/
│   │   ├── prompt_loader.py
│   │   └── dataset_loader.py
│   ├── versioning/              # 버전 관리
│   │   └── prompt_metadata.py
│   └── regression/              # 회귀 테스트
│       ├── baseline.py
│       └── comparator.py
├── utils/
│   ├── models.py
│   ├── git.py                   # git 관련 유틸
│   ├── config_validator.py
│   ├── langsmith_prompts.py
│   └── langsmith_datasets.py
├── targets/{name}/
│   ├── prompt.*
│   ├── config.yaml
│   └── .metadata.yaml           # 프롬프트 버전 메타데이터
├── datasets/{name}/
│   ├── test_cases.json
│   └── expected.json
├── results/baselines/{name}/    # 기준선 저장
│   └── {version}.json
└── eval_prompts/{domain}/
    └── {criterion}.txt
```

---

## 5. 목표 상태 (To-Be)

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

## 6. 구현 계획

### Phase 1: 버전 관리 강화 ✅ 구현 완료

> 📖 **상세 문서**: [docs/features/versioning.md](./features/versioning.md)

프롬프트 변경을 추적하고, 버전을 관리하며, LangSmith와 동기화하는 시스템입니다.

**구현된 기능**:
- 프롬프트 메타데이터 관리 (`.metadata.yaml`)
- SHA256 해시 기반 자동 변경 감지
- 자동 버전 증가 (v1.0 → v1.1)
- LangSmith 자동 push 연동
- `ChatPromptTemplate` 지원 (SYSTEM_PROMPT/USER_PROMPT 구분)
- git config 연동 (owner/author 자동 감지)

**핵심 모듈**: `src/versioning/prompt_metadata.py`

**데이터셋 버전 관리**: 후순위 (필요 시 구현 예정)

---

### Phase 2: 회귀 테스트 체계 ✅ 구현 완료

> 📖 **상세 문서**: [docs/features/regression.md](./features/regression.md)

프롬프트 변경이 품질에 미치는 영향을 감지하고, 성능 저하를 방지하는 시스템입니다.

**구현된 기능**:
- 기준선(Baseline) 저장/로드/삭제
- RegressionReport 기반 버전 비교
- 회귀 판정 (pass_rate 5% 이상 하락)
- 개별 케이스 추적 (new_failures, fixed_cases)
- CI/CD 연동용 `--fail` 옵션

**핵심 모듈**:
- `src/regression/baseline.py` - 기준선 관리
- `src/regression/comparator.py` - 회귀 비교

**GitHub Actions CI**: 후순위 (필요 시 구현 예정)

---

### Phase 2.5: Langfuse 통합 ✅ 구현 완료

> 📖 **상세 문서**: [docs/langfuse-migration-plan.md](./langfuse-migration-plan.md)

LangSmith와 함께 Langfuse를 평가 백엔드로 지원합니다.

**구현된 기능**:
- Langfuse SDK 통합 (`run_experiment` 기반)
- Docker 로컬 환경 구성 (`docker-compose.yml`)
- `--backend` CLI 옵션 (langsmith/langfuse/both)
- 기본값 `both`로 두 플랫폼 동시 실행

**백엔드 옵션**:

| 옵션 | 설명 |
|------|------|
| `both` (기본값) | Langfuse → LangSmith 순서로 동시 실행 |
| `langfuse` | Langfuse만 실행 |
| `langsmith` | LangSmith만 실행 (자동 버전 관리) |

**핵심 모듈**:
- `src/pipeline.py` - `_run_langfuse_experiment()` 추가
- `cli/experiment.py` - `--backend` 옵션 추가

**향후 계획**: Langfuse 단독 사용 + 커스텀 리포트 생성

---

### Phase 3: 리포트 시스템

#### 6.3.1. 실패 분석 자동화

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

#### 6.3.2. Markdown 리포트

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

#### 6.4.1. Human Spot-Check

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

#### 6.4.2. 평가자 가중치

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

## 7. 리팩토링 항목

### 7.1. CLI 모듈화 ✅ 완료

> 📖 **CLI 레퍼런스**: [docs/features/cli-reference.md](./features/cli-reference.md)

main.py의 CLI 명령어들을 `cli/` 디렉토리로 분리하여 모듈화했습니다.

| 파일 | 역할 | 줄 수 |
|------|------|-------|
| `main.py` | 앱 엔트리포인트 (조립만) | 57줄 |
| `cli/prompt.py` | `prompt` 서브커맨드 (info, init, push, pull, versions 등) | 195줄 |
| `cli/baseline.py` | `baseline` 서브커맨드 (list, set, delete) | 82줄 |
| `cli/experiment.py` | `experiment`, `regression` 명령어 | 215줄 |
| `cli/config.py` | `validate`, `criteria` 명령어 | 93줄 |
| `cli/dataset.py` | `list`, `upload` 명령어 | 31줄 |

기존 명령어는 모두 동일하게 유지됩니다.

### 7.2. 필수 리팩토링

| 파일 | 변경 내용 | Phase | 상태 |
|------|----------|:-----:|:----:|
| `main.py` | CLI 모듈화 | 1-2 | ✅ |
| `cli/` | CLI 명령어 분리 | 1-2 | ✅ |
| `utils/langsmith_prompts.py` | 메타데이터 자동 기록 | 1 | ✅ |
| `utils/git.py` | git 유틸 분리 | 2 | ✅ |
| `src/pipeline.py` | 결과 저장, 가중치, 리포트 연동 | 3 | - |
| `configs/config.py` | 회귀 임계값, 가중치 기본값 | 3 | - |
| `utils/config_validator.py` | 새 필드 검증 | 3 | - |

### 7.2. 스키마 변경

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

## 8. 신규 생성 파일 목록

### 8.1. 소스 코드

| 경로 | 설명 | 상태 |
|------|------|:----:|
| `src/versioning/prompt_metadata.py` | 프롬프트 메타데이터 | ✅ |
| `src/versioning/dataset_snapshot.py` | 데이터셋 스냅샷 | 후순위 |
| `src/regression/baseline.py` | 기준선 관리 | ✅ |
| `src/regression/comparator.py` | 회귀 비교 | ✅ |
| `src/reporters/failure_analyzer.py` | 실패 분석 | - |
| `src/reporters/markdown_reporter.py` | MD 리포트 | - |
| `src/evaluators/human_feedback.py` | Human 평가 | - |

### 8.2. 설정/워크플로우

| 경로 | 설명 |
|------|------|
| `.github/workflows/prompt-eval.yml` | CI/CD |
| `results/.gitkeep` | 결과 저장 폴더 |

### 8.3. 메타데이터 (프롬프트별)

| 경로 | 설명 |
|------|------|
| `targets/{name}/.metadata.yaml` | 프롬프트 메타 |
| `datasets/{name}/.versions.yaml` | 데이터셋 버전 |
| `results/{name}/baseline.json` | 기준선 |

---

## 9. 마일스톤

### Phase 1: 버전 관리 (Week 1) ✅ 완료
- [x] `src/versioning/prompt_metadata.py` - 메타데이터 관리 모듈 ✅
- [x] 해시 기반 변경 감지 (`compute_prompt_hash`, `is_prompt_changed`) ✅
- [x] 자동 버전 증가 (`increment_version`, `auto_version_and_push_info`) ✅
- [x] `main.py`에 `prompt init`, `prompt add-version`, `prompt info` 명령어 ✅
- [x] `langsmith_prompts.py` 리팩토링 - push 시 메타데이터 자동 연동 ✅
- [x] `ChatPromptTemplate` 지원 (SYSTEM_PROMPT/USER_PROMPT 구분) ✅
- [x] `experiment` 명령어 자동화 (init → 변경 감지 → push → 평가) ✅
- [x] 첫 init 시 변경 내용 입력 없이 바로 v1.0 push ✅
- [ ] `src/versioning/dataset_snapshot.py` (후순위 - 필요 시 구현)

### Phase 2: 회귀 테스트 (Week 2) ✅ 완료
- [x] `src/regression/baseline.py` ✅
- [x] `src/regression/comparator.py` ✅
- [x] `main.py`에 `baseline`, `regression` 명령어 ✅
- [ ] `.github/workflows/prompt-eval.yml` (후순위)

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

## 10. 성공 지표

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

## 11. 참고

### 기능별 상세 문서
- [버전 관리 (Versioning)](./features/versioning.md) - Phase 1 상세
- [회귀 테스트 (Regression)](./features/regression.md) - Phase 2 상세
- [Langfuse 마이그레이션 계획](./langfuse-migration-plan.md) - Phase 2.5 상세
- [CLI 레퍼런스](./features/cli-reference.md) - 전체 CLI 명령어

### 내부 문서
- [현재 기능 명세](./SPECIFICATION.md)
- [사용 가이드](./GUIDE.md)
- [LangSmith 프롬프트 관리](./LANGSMITH_PROMPTS.md)

### 외부 참고 자료
- [Dify의 Prompt Template 운영 사례](https://blog.open-network.co.kr/realistic-ai-agent-dify)
- [Prompt Engineering is Dead, Long Live PromptOps](https://www.dataversity.net/articles/prompt-engineering-is-dead-long-live-promptops/)
- [PromptOps: Monitoring, A/B Testing, Continuous Improvement](https://www.linkedin.com/pulse/day-1010-promptops-monitoring-ab-testing-continuous-dr-hernani-costa-6dhve/)

---

**Version**: 1.5.0
**Created**: 2026-01-26
**Updated**: 2026-01-27 (Langfuse 통합: Phase 2.5)
