"""평가 컨텍스트 - 프로젝트 경로 설정"""

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
    targets_dir: str | Path | None = None
    datasets_dir: str | Path | None = None
    eval_prompts_dir: str | Path | None = None
    results_dir: str | Path | None = None

    def __post_init__(self):
        root = Path(self.root) if self.root else Path(".")

        if self.targets_dir is None:
            self.targets_dir = root / "targets"
        else:
            self.targets_dir = Path(self.targets_dir)

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
                return cls()

        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            root=data.get("root"),
            targets_dir=data.get("targets_dir"),
            datasets_dir=data.get("datasets_dir"),
            eval_prompts_dir=data.get("eval_prompts_dir"),
            results_dir=data.get("results_dir"),
        )


_default_context: EvalContext | None = None


def get_context() -> EvalContext:
    global _default_context
    if _default_context is None:
        _default_context = EvalContext.from_config()
    return _default_context


def set_context(ctx: EvalContext):
    global _default_context
    _default_context = ctx
