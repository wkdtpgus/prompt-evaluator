# 회귀 테스트 (Regression Testing)

> Phase 2 구현 완료 ✅

프롬프트 변경이 품질에 미치는 영향을 감지하고, 성능 저하를 방지하는 시스템입니다.

---

## 1. 개요

### 1.1. 목표

- 기준선(Baseline) 기반 성능 비교
- 통과율/점수 하락 자동 감지
- 개별 케이스 수준 회귀 추적
- CI/CD 연동 (회귀 시 머지 차단)

### 1.2. 핵심 개념

| 개념 | 설명 |
|------|------|
| 기준선 (Baseline) | 비교 기준이 되는 검증된 평가 결과 |
| 회귀 (Regression) | 기존 대비 성능 저하 |
| 임계값 (Threshold) | 회귀 판정 기준 (기본 5%) |
| New Failures | 기존에 통과하던 케이스가 실패로 전환 |
| Fixed Cases | 기존에 실패하던 케이스가 통과로 전환 |

---

## 2. 기준선(Baseline) 관리

### 2.1. 저장 경로

```
results/baselines/{name}/{version}.json
```

### 2.2. 기준선 스키마

```json
{
  "prompt_name": "prep_generate",
  "version": "v1.2",
  "created_at": "2026-01-25T10:00:00",
  "metadata": {
    "author": "user@example.com",
    "changes": "톤 개선"
  },
  "results": {
    "experiment_name": "prep_generate-full-2026-01-25",
    "summary": {
      "total": 15,
      "passed": 13,
      "failed": 2,
      "pass_rate": 0.867,
      "avg_score": 0.82
    },
    "cases": [
      {
        "case_id": "scenario_01",
        "passed": true,
        "scores": {
          "tone_appropriateness": 0.9,
          "keyword_inclusion": 1.0
        }
      }
    ]
  }
}
```

### 2.3. 구현 모듈

**파일**: `src/regression/baseline.py`

| 함수 | 설명 |
|------|------|
| `save_baseline(prompt_name, version, results, metadata)` | 평가 결과를 기준선으로 저장 |
| `load_baseline(prompt_name, version)` | 기준선 로드 (version=None이면 latest) |
| `set_as_baseline(prompt_name, experiment_name)` | LangSmith 실험을 기준선으로 설정 |
| `list_baselines(prompt_name)` | 프롬프트의 기준선 목록 조회 |
| `delete_baseline(prompt_name, version)` | 기준선 삭제 |
| `get_baseline_path(prompt_name, version)` | 기준선 파일 경로 반환 |

### 2.4. 사용 예시

```python
from src.regression.baseline import save_baseline, load_baseline, list_baselines

# 기준선 저장
save_baseline(
    prompt_name="prep_generate",
    version="v1.0",
    results={
        "summary": {"total": 15, "passed": 13, "pass_rate": 0.867},
        "cases": [...]
    },
    metadata={"author": "user@example.com"}
)

# 기준선 로드
baseline = load_baseline("prep_generate")  # latest
baseline = load_baseline("prep_generate", "v1.0")  # 특정 버전

# 기준선 목록
baselines = list_baselines("prep_generate")
# [{"version": "v1.0", "created_at": "..."}, {"version": "v1.1", ...}]
```

---

## 3. 회귀 비교

### 3.1. 비교 로직

```
기준선 (Baseline)          현재 결과 (Current)
        │                         │
        └─────────┬───────────────┘
                  ▼
         ┌─────────────────┐
         │  compare_results │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │ RegressionReport │
         └─────────────────┘
```

### 3.2. RegressionReport 구조

**파일**: `src/regression/comparator.py`

```python
@dataclass
class RegressionReport:
    prompt_name: str
    baseline_version: str
    current_version: str
    baseline_pass_rate: float
    current_pass_rate: float
    pass_rate_delta: float      # current - baseline (음수면 성능 저하)
    baseline_avg_score: float | None
    current_avg_score: float | None
    avg_score_delta: float | None
    has_regression: bool         # pass_rate_delta < -threshold
    regression_threshold: float  # 기본 0.05 (5%)
    case_regressions: list[dict] # 개별 케이스 회귀
    new_failures: list[str]      # Pass → Fail
    fixed_cases: list[str]       # Fail → Pass
```

### 3.3. 회귀 판정 기준

| 조건 | 판정 |
|------|------|
| `pass_rate_delta < -threshold` | 회귀 (기본 5% 이상 하락) |
| `new_failures` 존재 | 개별 케이스 회귀 |

### 3.4. 구현 함수

| 함수 | 설명 |
|------|------|
| `compare_results(baseline, current, threshold)` | 기준선과 현재 결과 비교 → RegressionReport |
| `format_regression_report(report)` | 리포트를 읽기 쉬운 문자열로 포맷 |

### 3.5. 사용 예시

```python
from src.regression.baseline import load_baseline
from src.regression.comparator import compare_results, format_regression_report

# 기준선 로드
baseline = load_baseline("prep_generate")

# 현재 결과 (LangSmith에서 가져온 데이터)
current = {
    "version": "current",
    "results": {
        "summary": {"total": 15, "passed": 12, "pass_rate": 0.80},
        "cases": [...]
    }
}

# 비교
report = compare_results(baseline, current, threshold=0.05)

# 출력
print(format_regression_report(report))

# 회귀 여부 확인
if report.has_regression:
    print("⚠️ 회귀 감지됨!")
    print(f"새로 실패한 케이스: {report.new_failures}")
```

---

## 4. 리포트 출력 형식

### 4.1. 회귀 테스트 출력 예시

```
회귀 테스트 리포트: prep_generate
============================================================
비교: v1.0 → current

[요약]
  Pass Rate: 90.0% → 85.0% (↓5.0%)
  Avg Score: 0.850 → 0.820 (↓0.030)

⚠️  회귀 감지됨!
  (임계값: 5% 이상 성능 저하)

[새로 실패한 케이스] (2개)
  • scenario_03
  • edge_case_01

[개선된 케이스] (1개)
  • scenario_05

============================================================
```

### 4.2. 성공 시 출력

```
회귀 테스트 리포트: prep_generate
============================================================
비교: v1.0 → current

[요약]
  Pass Rate: 85.0% → 90.0% (↑5.0%)
  Avg Score: 0.820 → 0.850 (↑0.030)

✅ 회귀 없음

[개선된 케이스] (2개)
  • edge_case_01
  • scenario_03

============================================================
```

---

## 5. CLI 명령어

### 5.1. 기준선 관리

```bash
# 기준선 목록 조회
poetry run python main.py baseline list prep_generate

# LangSmith 실험을 기준선으로 설정
poetry run python main.py baseline set prep_generate "prep_generate-full-2026-01-26"

# 기준선 삭제
poetry run python main.py baseline delete prep_generate v1.0
```

### 5.2. 회귀 테스트 실행

```bash
# 기준선과 실험 비교
poetry run python main.py regression --name prep_generate --experiment "prep_generate-full-2026-01-26"

# CI/CD에서 회귀 시 실패 처리 (exit code 1)
poetry run python main.py regression --name prep_generate --experiment "..." --fail

# 임계값 조정 (기본 5%)
poetry run python main.py regression --name prep_generate --experiment "..." --threshold 0.1
```

### 5.3. 옵션 상세

| 옵션 | 축약 | 설명 | 기본값 |
|------|------|------|--------|
| `--name` | `-n` | 프롬프트 이름 | 필수 |
| `--baseline` | `-b` | 기준선 버전 | latest |
| `--experiment` | `-e` | 비교할 실험 이름 | 필수 |
| `--threshold` | `-t` | 회귀 임계값 | 0.05 (5%) |
| `--fail` | `-f` | 회귀 시 exit code 1 반환 | false |

---

## 6. CI/CD 연동 (계획)

### 6.1. GitHub Actions 예시

**파일**: `.github/workflows/prompt-eval.yml`

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
          poetry run python main.py regression --name ${{ steps.changes.outputs.prompt }} --fail

      - name: Comment PR
        uses: actions/github-script@v7
        with:
          script: |
            // 평가 결과를 PR 코멘트로 작성
```

### 6.2. 워크플로우

```
PR 생성 (targets/ 변경)
        │
        ▼
┌─────────────────┐
│ 변경 프롬프트 감지 │
└────────┬────────┘
        │
        ▼
┌─────────────────┐
│   평가 실행      │
└────────┬────────┘
        │
        ▼
┌─────────────────┐
│  회귀 테스트     │
└────────┬────────┘
        │
    ┌───┴───┐
    ▼       ▼
  회귀     회귀
  없음     있음
    │       │
    ▼       ▼
  ✅       ❌
 머지 가능  머지 차단
```

---

## 7. 폴더 구조

```
results/
└── baselines/
    └── {prompt_name}/
        ├── v1.0.json
        ├── v1.1.json
        └── v1.2.json
```

---

## 8. 관련 문서

- [버전 관리](./versioning.md) - 프롬프트 버전 추적
- [CLI 레퍼런스](./cli-reference.md) - 전체 CLI 명령어
- [PromptOps 기획서](../PROMPTOPS_PLAN.md) - 전체 로드맵
