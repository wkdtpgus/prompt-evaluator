"""Config 검증 및 평가 기준 CLI 명령어"""

from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml

from src.evaluators.llm_judge import list_available_criteria
from utils.config_validator import validate_config, validate_all_configs


def validate(
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="검증할 프롬프트 이름")] = None,
    all_configs: Annotated[bool, typer.Option("--all", "-a", help="모든 config 검증")] = False,
):
    """config 파일 유효성 검증."""
    if not name and not all_configs:
        typer.echo("--name 또는 --all 옵션을 지정하세요.")
        raise typer.Exit(1)

    if all_configs:
        typer.echo("\n모든 config 검증 중...")
        typer.echo("-" * 60)

        results = validate_all_configs()

        for prompt_name, result in results.items():
            status = "✓" if result.valid else "✗"
            typer.echo(f"\n{status} {prompt_name}")

            for error in result.errors:
                typer.echo(f"  ✗ {error}")
            for warning in result.warnings:
                typer.echo(f"  ⚠ {warning}")

        typer.echo("\n" + "-" * 60)
        valid_count = sum(1 for r in results.values() if r.valid)
        typer.echo(f"결과: {valid_count}/{len(results)} 통과")
    else:
        config_file = Path("targets") / name / "config.yaml"
        if not config_file.exists():
            typer.echo(f"config 파일 없음: {config_file}")
            raise typer.Exit(1)

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        typer.echo(f"\n{name} config 검증 중...")
        typer.echo("-" * 60)

        result = validate_config(config, name)

        if result.valid:
            typer.echo(f"✓ config 유효")
        else:
            typer.echo(f"✗ config 오류 발견")

        for error in result.errors:
            typer.echo(f"  ✗ {error}")
        for warning in result.warnings:
            typer.echo(f"  ⚠ {warning}")

        if not result.errors and not result.warnings:
            typer.echo("  문제 없음")

        typer.echo()

        if not result.valid:
            raise typer.Exit(1)


def criteria():
    """사용 가능한 LLM Judge 평가 기준 목록 출력."""
    typer.echo("\n📋 사용 가능한 평가 기준:")
    typer.echo("-" * 60)

    criteria_list = list_available_criteria()

    typer.echo("\n  [일반 평가 기준]")
    general = ["instruction_following", "factual_accuracy", "output_quality"]
    for c in general:
        if c in criteria_list:
            typer.echo(f"    • {c}: {criteria_list[c]}")

    typer.echo("\n  [1on1 Meeting 특화 평가 기준]")
    oneonone = ["purpose_alignment", "coaching_quality", "tone_appropriateness", "sensitive_topic_handling"]
    for c in oneonone:
        if c in criteria_list:
            typer.echo(f"    • {c}: {criteria_list[c]}")

    typer.echo("\n" + "-" * 60)
    typer.echo("사용법: targets/{name}/config.yaml의 llm_judge.criteria에 추가")
    typer.echo("  예: criteria: [purpose_alignment, coaching_quality]")
    typer.echo()
