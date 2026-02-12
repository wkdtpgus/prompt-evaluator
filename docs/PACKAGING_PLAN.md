# Prompt Evaluator 패키지화 계획

> **버전**: 0.1.0
> **작성일**: 2026-02-11
> **상태**: ✅ 구현 완료

---

## 1. 개요

prompt-evaluator를 `pip install` 가능한 Python 패키지로 전환하여, 프로덕션 코드베이스에서 평가 엔진을 직접 사용할 수 있게 한다.

### 1.1. 핵심 원칙

- **패키지 = 평가 엔진만 제공**: 실행/평가/회귀 테스트 로직
- **데이터는 사용자 제공**: targets, datasets, eval_prompts는 프로덕션 프로젝트에서 관리
- **스킬은 프로젝트별 커스텀**: 각 프로덕션 프로젝트가 `.claude/skills/`로 자체 데이터 생성

### 1.2. 역할 분리

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

## 2. 현재 상태 분석

### 2.1. 패키지화 불가 사유

| 항목 | 현재 상태 | 문제 |
|------|-----------|------|
| `pyproject.toml` | `package-mode = false` | 빌드/설치 불가 |
| 패키지 디렉토리 | `src/`, `utils/`, `configs/`, `cli/` 분산 | 단일 패키지로 인식 안 됨 |
| import 경로 | `from src.loaders import ...` | 설치 후 경로 해석 불가 |
| eval_prompts 경로 | `Path(__file__).parent.parent.parent / "eval_prompts"` | 설치 위치에서 잘못된 경로 |

### 2.2. 경로 처리 현황

현재 함수들은 대부분 경로를 파라미터로 받되, 기본값이 CWD 기준 상대경로:

| 함수 | 파라미터 | 기본값 |
|------|----------|--------|
| `load_evaluation_set()` | `targets_dir`, `datasets_dir` | `"targets"`, `"datasets"` |
| `validate_config()` | `targets_dir`, `datasets_dir`, `eval_prompts_dir` | 동일 |
| `list_evaluation_sets()` | `targets_dir`, `datasets_dir` | 동일 |
| `prompt_metadata.*()` | `targets_dir` | `"targets"` |
| `run_checklist_evaluation()` | (없음 — `__file__` 기반 하드코딩) | `Path(__file__)/../../eval_prompts` |
| `baseline.py` | (없음 — 모듈 상수) | `Path("results/baselines")` |
| CLI 명령어들 | (없음 — 함수 내 하드코딩) | `Path("targets") / name` |

**문제**: 프로덕션 프로젝트의 루트 경로가 제각각이므로, CWD에 의존하는 방식은 불안정하다.
예를 들어 `my-app/evaluation/` 하위에 평가 데이터를 두면 CLI를 반드시 해당 디렉토리에서 실행해야 한다.

### 2.3. 이미 잘 되어 있는 부분

- 핵심 함수들의 경로 파라미터화 구조 (기본값만 바꾸면 됨)
- CLI entry point `prompt-eval` 정의됨
- 모듈 간 관심사 분리 깔끔

---

## 3. 목표 디렉토리 구조

```
prompt-evaluator/
  prompt_evaluator/                  # pip install 대상 패키지
    __init__.py                      # 공개 API (필수)
    context.py                       # EvalContext — 프로젝트 루트/경로 설정 (신규)
    config.py                        # ← configs/config.py
    models.py                        # ← utils/models.py
    loaders/
      __init__.py                    # (기존 유지)
      dataset_loader.py
      prompt_loader.py
    evaluators/
      adapters.py
      llm_judge.py
      rule_based.py
    pipelines/
      pipeline.py
    regression/
      baseline.py
      comparator.py
    versioning/
      prompt_metadata.py
    utils/
      config_validator.py
      dataset_sync.py
      git.py
      langfuse_client.py
      prompt_sync.py
    cli/
      __init__.py                    # Typer app 정의 (entry point용 필수)
      experiment.py
      config.py
      dataset.py
      prompt.py
      baseline.py

  # --- 패키지에 포함되지 않는 개발용 데이터 ---
  targets/
  datasets/
  eval_prompts/
  results/
  tests/
  main.py                           # 개발용 thin wrapper
  pyproject.toml
```

---

## 4. 구현 단계

### 4.1. 디렉토리 이동

`git mv`로 모든 소스 코드를 `prompt_evaluator/` 하위로 이동:

```bash
mkdir -p prompt_evaluator/utils prompt_evaluator/cli

# src/ 하위 모듈 이동
git mv src/loaders    prompt_evaluator/loaders
git mv src/evaluators prompt_evaluator/evaluators
git mv src/pipelines  prompt_evaluator/pipelines
git mv src/regression prompt_evaluator/regression
git mv src/versioning prompt_evaluator/versioning

# configs, utils 흡수
git mv configs/config.py               prompt_evaluator/config.py
git mv utils/models.py                 prompt_evaluator/models.py
git mv utils/config_validator.py       prompt_evaluator/utils/config_validator.py
git mv utils/dataset_sync.py           prompt_evaluator/utils/dataset_sync.py
git mv utils/git.py                    prompt_evaluator/utils/git.py
git mv utils/langfuse_client.py        prompt_evaluator/utils/langfuse_client.py
git mv utils/prompt_sync.py            prompt_evaluator/utils/prompt_sync.py

# cli 이동
git mv cli/experiment.py               prompt_evaluator/cli/experiment.py
git mv cli/config.py                   prompt_evaluator/cli/config.py
git mv cli/dataset.py                  prompt_evaluator/cli/dataset.py
git mv cli/prompt.py                   prompt_evaluator/cli/prompt.py
git mv cli/baseline.py                 prompt_evaluator/cli/baseline.py
```

### 4.2. 필수 파일 생성

#### `prompt_evaluator/__init__.py`

```python
"""prompt-evaluator: LLM 프롬프트 정량 평가 엔진"""

from prompt_evaluator.context import EvalContext, get_context, set_context
from prompt_evaluator.pipelines.pipeline import run_experiment, execute_prompt
from prompt_evaluator.loaders.dataset_loader import load_evaluation_set, list_evaluation_sets
from prompt_evaluator.loaders.prompt_loader import load_prompt_file, find_prompt_file
from prompt_evaluator.evaluators.rule_based import keyword_inclusion, forbidden_word_check
from prompt_evaluator.evaluators.llm_judge import run_checklist_evaluation

__version__ = "0.1.0"
```

#### `prompt_evaluator/cli/__init__.py`

```python
"""CLI 모듈 — prompt-eval 엔트리 포인트"""

import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(name="prompt-evaluator", help="프롬프트 평가 시스템 CLI")

def _register():
    from prompt_evaluator.cli import prompt as prompt_cli, baseline as baseline_cli
    from prompt_evaluator.cli.experiment import experiment, regression
    from prompt_evaluator.cli.config import validate
    from prompt_evaluator.cli.dataset import list_sets, upload

    app.add_typer(prompt_cli.app, name="prompt")
    app.add_typer(baseline_cli.app, name="baseline")
    app.command()(experiment)
    app.command()(regression)
    app.command()(validate)
    app.command(name="list")(list_sets)
    app.command()(upload)

_register()
```

#### `main.py` (루트, 개발용 thin wrapper)

```python
"""개발용 CLI 진입점"""
from prompt_evaluator.cli import app

if __name__ == "__main__":
    app()
```

### 4.3. import 경로 전체 수정

모든 소스 파일에서 아래 치환 수행 (18개 파일):

| 기존 import | 신규 import |
|-------------|-------------|
| `from src.loaders` | `from prompt_evaluator.loaders` |
| `from src.evaluators` | `from prompt_evaluator.evaluators` |
| `from src.pipelines` | `from prompt_evaluator.pipelines` |
| `from src.regression` | `from prompt_evaluator.regression` |
| `from src.versioning` | `from prompt_evaluator.versioning` |
| `from configs.config` | `from prompt_evaluator.config` |
| `from utils.models` | `from prompt_evaluator.models` |
| `from utils.langfuse_client` | `from prompt_evaluator.utils.langfuse_client` |
| `from utils.config_validator` | `from prompt_evaluator.utils.config_validator` |
| `from utils.dataset_sync` | `from prompt_evaluator.utils.dataset_sync` |
| `from utils.prompt_sync` | `from prompt_evaluator.utils.prompt_sync` |
| `from utils.git` | `from prompt_evaluator.utils.git` |
| `from cli.experiment` | `from prompt_evaluator.cli.experiment` |
| `from cli.config` | `from prompt_evaluator.cli.config` |
| `from cli.dataset` | `from prompt_evaluator.cli.dataset` |
| `from cli import` | `from prompt_evaluator.cli import` |

### 4.4. 프로젝트 루트 경로 해결

프로덕션 프로젝트의 루트 경로가 제각각이므로, **`EvalContext`** 객체로 경로를 한 곳에서 관리한다.

#### `prompt_evaluator/context.py` (신규)

```python
"""평가 컨텍스트 — 프로젝트 경로 설정"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EvalContext:
    """평가 실행에 필요한 경로 설정.

    프로덕션 프로젝트에서 root만 지정하면 하위 디렉토리는 컨벤션대로 해석.
    개별 경로를 직접 지정할 수도 있음.

    Usage:
        # 프로덕션: init 후 config.yaml이 있으면 자동 로드
        ctx = EvalContext.from_config()  # .prompt-eval/config.yaml 자동 탐색

        # 또는 직접 지정
        ctx = EvalContext(
            targets_dir="src/prompts",
            root=".prompt-eval",
        )

        # 개발 (이 프로젝트): 기본값 = CWD 기준 (기존 동작 그대로)
        ctx = EvalContext()
    """

    root: str | Path | None = None
    targets_dir: str | Path | None = None     # 프롬프트 위치 (프로덕션 코드 경로)
    datasets_dir: str | Path | None = None    # root 기준
    eval_prompts_dir: str | Path | None = None  # root 기준
    results_dir: str | Path | None = None     # root 기준

    def __post_init__(self):
        root = Path(self.root) if self.root else Path(".")

        # targets_dir는 root와 독립 — 프로덕션 프롬프트는 별도 위치에 있을 수 있음
        if self.targets_dir is None:
            self.targets_dir = root / "targets"
        else:
            self.targets_dir = Path(self.targets_dir)

        # 나머지는 root 기준
        if self.datasets_dir is None:
            self.datasets_dir = root / "datasets"
        else:
            self.datasets_dir = Path(self.datasets_dir)
        if self.eval_prompts_dir is None:
            self.eval_prompts_dir = root / "eval_prompts"
        else:
            self.eval_prompts_dir = Path(self.eval_prompts_dir)
        if self.results_dir is None:
            self.results_dir = root / "results"
        else:
            self.results_dir = Path(self.results_dir)

    @property
    def baselines_dir(self) -> Path:
        return self.results_dir / "baselines"

    @property
    def experiments_dir(self) -> Path:
        return self.results_dir / "experiments"

    @classmethod
    def from_config(cls, config_path: str | Path | None = None) -> "EvalContext":
        """config.yaml에서 컨텍스트 로드.

        config_path 미지정 시 자동 탐색:
          1. .prompt-eval/config.yaml
          2. config.yaml (CWD)

        파일이 없으면 기본 EvalContext() 반환 (하위 호환).
        """
        if config_path:
            path = Path(config_path)
        else:
            for candidate in [Path(".prompt-eval/config.yaml"), Path("config.yaml")]:
                if candidate.exists():
                    path = candidate
                    break
            else:
                return cls()  # config 없음 → 기본값

        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            root=data.get("root"),
            targets_dir=data.get("targets_dir"),
            datasets_dir=data.get("datasets_dir"),
            eval_prompts_dir=data.get("eval_prompts_dir"),
            results_dir=data.get("results_dir"),
        )


# 전역 컨텍스트 — 모듈 로드 시 config.yaml 자동 탐색
_default_context: EvalContext | None = None


def get_context() -> EvalContext:
    global _default_context
    if _default_context is None:
        _default_context = EvalContext.from_config()
    return _default_context


def set_context(ctx: EvalContext):
    global _default_context
    _default_context = ctx
```

#### 적용 방식

**기존 함수 시그니처는 유지**, 기본값 해석만 변경:

```python
# 변경 전 (CWD 하드코딩)
def load_evaluation_set(
    prompt_name: str,
    targets_dir: str | Path = "targets",      # CWD 고정
    datasets_dir: str | Path = "datasets",
) -> dict:

# 변경 후 (context 참조)
def load_evaluation_set(
    prompt_name: str,
    targets_dir: str | Path | None = None,    # None이면 context에서 가져옴
    datasets_dir: str | Path | None = None,
) -> dict:
    ctx = get_context()
    targets_dir = Path(targets_dir) if targets_dir else ctx.targets_dir
    datasets_dir = Path(datasets_dir) if datasets_dir else ctx.datasets_dir
    # ... 이하 동일
```

#### 적용 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `evaluators/llm_judge.py` | `PROMPTS_DIR` 상수 삭제, `eval_prompts_dir` 파라미터 추가 → `ctx.eval_prompts_dir` 폴백 |
| `regression/baseline.py` | `BASELINES_DIR`, `RESULTS_DIR` 상수 → `ctx.baselines_dir`, `ctx.experiments_dir` |
| `loaders/dataset_loader.py` | 기본값 `"targets"` → `None` + context 폴백 |
| `utils/config_validator.py` | 동일 패턴 |
| `versioning/prompt_metadata.py` | `targets_dir` 기본값 변경 |
| `cli/*.py` | `Path("targets") / name` → `ctx.targets_dir / name` |

#### 프로덕션 사용 예시

```python
from prompt_evaluator import run_experiment, EvalContext, set_context

# 방법 1: 전역 컨텍스트 설정 (한 번만)
set_context(EvalContext(root="/app/evaluation"))
run_experiment("my_prompt", backend="langfuse")

# 방법 2: 함수 호출 시 직접 경로 지정 (기존 방식도 여전히 동작)
from prompt_evaluator import load_evaluation_set
data = load_evaluation_set("my_prompt", targets_dir="/app/prompts", datasets_dir="/app/data")
```

#### CLI에서의 루트 경로 지정

```bash
# --root 옵션으로 프로젝트 루트 지정
prompt-eval --root /app/evaluation experiment --name my_prompt

# 또는 환경변수
PROMPT_EVAL_ROOT=/app/evaluation prompt-eval experiment --name my_prompt

# 미지정 시 CWD 기준 (기존 동작 그대로)
cd /app/evaluation && prompt-eval experiment --name my_prompt
```

### 4.5. pyproject.toml 수정

```toml
[tool.poetry]
name = "prompt-evaluator"
version = "0.1.0"
description = "LLM 프롬프트 정량 평가 엔진"
readme = "README.md"
authors = ["Your Name <your.email@example.com>"]
packages = [{include = "prompt_evaluator"}]
# package-mode = false 삭제

[tool.poetry.scripts]
prompt-eval = "prompt_evaluator.cli:app"
```

### 4.6. 스킬 템플릿 번들

패키지에 스킬 파일과 범용 평가 기준을 데이터로 포함:

```
prompt_evaluator/
  templates/                                    # 패키지 데이터 (신규)
    skills/
      test_case_generator/
        SKILL.md                                # ← .claude/skills/ 에서 복사
        references/
          prep_chat_patterns.md
      llm_judge_generator/
        SKILL.md
        references/
          general_criteria.md
          oneonone_criteria.md
      prompt_ab_comparator/
        SKILL.md
        references/
          format_comparison_guide.md
    eval_prompts/
      general/
        instruction_following.txt               # ← eval_prompts/general/ 에서 복사
        factual_accuracy.txt
        output_quality.txt
```

스킬 SKILL.md 내의 CLI 명령어 레퍼런스도 업데이트:

```diff
- poetry run python main.py experiment --name {프롬프트명}
+ prompt-eval experiment --name {프롬프트명}
```

### 4.7. 정리

```bash
# 빈 디렉토리 삭제 (git mv 후 남은 것들)
rm -rf src/ configs/ utils/ cli/

# 캐시 정리
find . -type d -name __pycache__ -exec rm -rf {} +
```

---

## 5. 검증

```bash
# 1. 설치 확인
poetry install

# 2. CLI 동작
poetry run prompt-eval --help

# 3. Python import
poetry run python -c "from prompt_evaluator import run_experiment; print('OK')"

# 4. 테스트
poetry run pytest

# 5. 빌드
poetry build
```

---

## 6. 프로덕션 사용 시나리오

### 6.1. 설치

```bash
# git 저장소에서 직접 설치
pip install git+https://github.com/{org}/prompt-evaluator.git

# 또는 로컬에서
pip install /path/to/prompt-evaluator

# 또는 PyPI (추후)
pip install prompt-evaluator
```

### 6.2. 프로덕션 프로젝트 구조

**핵심 원칙: target 프롬프트는 프로덕션 코드에 이미 존재한다. 복사하지 않는다.**

평가 산출물(datasets, eval_prompts, results)만 `.prompt-eval/` 디렉토리에 격리하여
프로덕션 코드 루트를 깔끔하게 유지한다.

```
my-app/                                    # 프로덕션 프로젝트
├── src/
│   └── prompts/
│       └── chat_prompt.py                 # ← 프롬프트는 이미 여기 있음
├── .prompt-eval/                          # ← 평가 전용 (prompt-eval init 생성)
│   ├── config.yaml                        # 경로 설정 (init이 생성, 이후 자동 로드)
│   ├── datasets/
│   │   └── chat_prompt/
│   │       ├── test_cases.json
│   │       └── expected.json
│   ├── eval_prompts/
│   │   ├── general/                       # 범용 평가 기준 (번들)
│   │   └── chat/                          # 도메인 특화 (스킬로 생성)
│   └── results/
├── .claude/
│   └── skills/                            # ← 평가 스킬 (prompt-eval init 생성)
├── .gitignore                             # .prompt-eval/results/ 추가
└── pyproject.toml
```

**targets_dir은 프로덕션 프롬프트의 기존 위치를 가리킨다.**

`init` 시 `--targets-dir`로 지정하면 config.yaml에 저장되므로, 이후 자동 적용:

```yaml
# .prompt-eval/config.yaml (init이 자동 생성)
root: .prompt-eval
targets_dir: src/prompts
```

**또는 프롬프트 파일을 직접 지정:**

현재 `find_prompt_file()`은 `targets_dir/{name}/prompt.*` 패턴을 강제한다.
프로덕션에서는 프롬프트 위치가 다양하므로, `prompt_file` 직접 지정도 지원:

```python
# 기존 컨벤션 방식 (targets_dir/{name}/prompt.*)
data = load_evaluation_set("chat_prompt", targets_dir="src/prompts")

# 직접 경로 방식 (신규)
data = load_evaluation_set(
    "chat_prompt",
    prompt_file="src/prompts/chat_prompt.py",  # 파일 직접 지정
    datasets_dir=".prompt-eval/datasets",
)
```

#### 프로젝트별 구조 예시

```
# Case A: 프롬프트가 src/prompts/ 에 있는 경우 (권장)
my-app/
├── src/prompts/chat_prompt/prompt.py      # 프로덕션 프롬프트
├── .prompt-eval/                          # 평가 산출물
│   ├── datasets/
│   ├── eval_prompts/
│   └── results/
└── ...
# → EvalContext(targets_dir="src/prompts", root=".prompt-eval")

# Case B: 프롬프트가 임의 경로에 있는 경우
my-app/
├── app/templates/system_prompt.txt
├── .prompt-eval/
└── ...
# → prompt_file="app/templates/system_prompt.txt" 직접 지정

# Case C: 이 프로젝트(prompt-evaluator) 자체 개발 시 (기존 동작)
prompt-evaluator/
├── targets/
├── datasets/
├── eval_prompts/
└── results/
# → EvalContext() (기본값 그대로, 하위 호환)
```

### 6.3. 사용법

`init` 이후에는 config.yaml이 경로를 기억하므로, **경로 지정 없이 바로 사용**:

```python
# Python API — init 이후 경로 설정 불필요
from prompt_evaluator import run_experiment

result = run_experiment("chat_prompt", mode="full", backend="langfuse")
# → config.yaml에서 root, targets_dir 자동 로드
```

```bash
# CLI — init 이후 경로 옵션 불필요
prompt-eval experiment --name chat_prompt --backend langfuse
prompt-eval regression --name chat_prompt --source langfuse
```

```python
# set_context()는 config.yaml 없이 Python에서 직접 설정할 때만 필요
from prompt_evaluator import EvalContext, set_context, run_experiment

set_context(EvalContext(root=".prompt-eval", targets_dir="src/prompts"))
run_experiment("chat_prompt")
```

```python
# 프롬프트 파일 직접 지정도 여전히 가능
from prompt_evaluator import load_evaluation_set

data = load_evaluation_set(
    "chat_prompt",
    prompt_file="src/prompts/chat_prompt.py",
)
```

### 6.4. `prompt-eval init` — 평가 환경 초기화

패키지 설치 후 `init` 명령 한 번이면 평가 환경이 세팅된다.
**targets/ 디렉토리는 생성하지 않는다** — 프롬프트는 프로덕션 코드에 이미 있으므로.

```bash
cd my-app/
prompt-eval init --dir .prompt-eval --targets-dir src/prompts
```

이 명령이 하는 일:

```
my-app/
├── .prompt-eval/                          # --dir로 지정
│   ├── config.yaml                        # 경로 설정 (자동 생성, 이후 자동 로드)
│   ├── datasets/                          # 테스트 데이터 (스킬로 생성)
│   ├── eval_prompts/
│   │   └── general/                       # 범용 평가 기준 (번들에서 복사)
│   │       ├── instruction_following.txt
│   │       ├── factual_accuracy.txt
│   │       └── output_quality.txt
│   └── results/
├── .claude/
│   └── skills/                            # Claude Code 스킬 (자동 설치)
│       ├── test_case_generator/
│       │   ├── SKILL.md
│       │   └── references/
│       ├── llm_judge_generator/
│       │   ├── SKILL.md
│       │   └── references/
│       └── prompt_ab_comparator/
│           ├── SKILL.md
│           └── references/
└── .gitignore                             # .prompt-eval/results/ 자동 추가
```

생성된 `config.yaml` 내용:

```yaml
# .prompt-eval/config.yaml
root: .prompt-eval
targets_dir: src/prompts
```

#### 구현

```python
# prompt_evaluator/cli/init.py

import yaml

def init(
    dir: Path = Path("."),
    targets_dir: str | None = None,
    with_skills: bool = True,
    with_general_prompts: bool = True,
):
    """평가 환경 초기화 (targets 제외)"""
    # 1. 평가 산출물 디렉토리 생성 (targets 제외!)
    for d in ["datasets", "eval_prompts", "results"]:
        (dir / d).mkdir(parents=True, exist_ok=True)

    # 2. config.yaml 생성 — 이후 경로 자동 해석에 사용
    _write_config(dir, targets_dir)

    # 3. Claude Code 스킬 복사 (프로젝트 루트의 .claude/skills/)
    if with_skills:
        templates = files("prompt_evaluator.templates.skills")
        copy_tree(templates, Path(".claude") / "skills")

    # 4. 범용 평가 기준 복사
    if with_general_prompts:
        general = files("prompt_evaluator.templates.eval_prompts.general")
        copy_tree(general, dir / "eval_prompts" / "general")

    # 5. .gitignore에 results/ 추가
    _update_gitignore(dir)


def _write_config(eval_dir: Path, targets_dir: str | None):
    """config.yaml 생성 — 경로 설정을 저장하여 이후 자동 로드"""
    config = {"root": str(eval_dir)}
    if targets_dir:
        config["targets_dir"] = targets_dir

    config_path = eval_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    # 예시 결과:
    # root: .prompt-eval
    # targets_dir: src/prompts


def _update_gitignore(eval_dir: Path):
    """프로젝트 루트 .gitignore에 평가 results 경로 추가"""
    gitignore = Path(".gitignore")
    entry = f"{eval_dir}/results/"

    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content:
            return  # 이미 있음
    else:
        content = ""

    content += f"\n# prompt-eval results (실행 결과는 Langfuse에서 확인)\n{entry}\n"
    gitignore.write_text(content)
```

**git 추적 정책:**

| 경로 | git 추적 | 이유 |
|------|:--------:|------|
| `.prompt-eval/datasets/` | O | 테스트 케이스는 팀원과 공유/리뷰 |
| `.prompt-eval/eval_prompts/` | O | 평가 기준도 코드 리뷰 대상 |
| `.prompt-eval/results/` | **X** | 실행마다 다름, Langfuse/LangSmith에 원본 있음 |
| `.claude/skills/` | O | 스킬 커스텀 내용 공유 |

`init`은 `.gitignore`에 **results만** 추가한다. `.prompt-eval/` 전체를 무시하면
datasets와 eval_prompts까지 날아가므로 주의.

#### 스킬 경로 커스텀

`init`으로 복사된 스킬 SKILL.md가 참조하는 경로:
- `targets/{name}/` → `init` 시 `--targets-dir` 옵션으로 스킬 내 경로를 자동 치환
- `datasets/{name}/` → `.prompt-eval/datasets/{name}/`로 치환
- `eval_prompts/{domain}/` → `.prompt-eval/eval_prompts/{domain}/`로 치환

또는 스킬은 로컬 파일이므로 직접 수정 가능:

```bash
vi .claude/skills/test_case_generator/SKILL.md
# targets/{프롬프트명}/ → src/prompts/{프롬프트명}/ 로 변경
```

#### 전체 워크플로우

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

### 6.5. 경로 해석 우선순위

```
1. 함수 인자로 직접 전달된 경로 (최우선)
2. set_context()로 설정된 EvalContext
3. config.yaml 자동 탐색 (.prompt-eval/config.yaml → config.yaml)
4. 환경변수 PROMPT_EVAL_ROOT
5. CWD 기준 기본 컨벤션 (targets/, datasets/, ...)
```

**일반적인 프로덕션 사용에서는 3번(config.yaml)에서 해결되므로,
사용자가 경로를 신경 쓸 일이 없다.**

---

## 7. 구현 결과

### 7.1. 완료 항목

| 단계 | 항목 | 상태 |
|------|------|:----:|
| 4.1 | 디렉토리 이동 (`git mv`) | ✅ |
| 4.2 | `__init__.py`, `cli/__init__.py`, `main.py` 생성 | ✅ |
| 4.3 | import 경로 전체 수정 | ✅ |
| 4.4 | `EvalContext` + `context.py` 구현 | ✅ |
| 4.5 | `pyproject.toml` 수정 (packages, scripts) | ✅ |
| 4.6 | 스킬/평가기준 번들 (`skills/`, `evaluators/eval_prompts/`) | ✅ |
| 4.6 | `prompt-eval init` CLI 명령어 (`scaffold.py`) | ✅ |
| 4.7 | 빈 디렉토리 정리 | ✅ |

### 7.2. 추가 구현 사항

- `prompt_evaluator/cli/scaffold.py`: `init` 명령어 (디렉토리 생성, config.yaml, 스킬 복사, 범용 평가기준 복사, .gitignore 업데이트)
- `prompt_evaluator/evaluators/eval_prompts/general/`: 번들 평가 기준 (instruction_following, factual_accuracy, output_quality)
- `prompt_evaluator/skills/`: 번들 스킬 (test_case_generator, llm_judge_generator, prompt_ab_comparator)
