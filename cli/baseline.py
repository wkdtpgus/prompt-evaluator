"""기준선(Baseline) 관리 CLI 명령어"""

from typing import Annotated, Optional

import typer

from src.regression.baseline import (
    list_baselines,
    set_as_baseline,
    delete_baseline,
)
from src.versioning.prompt_metadata import load_metadata


app = typer.Typer(help="기준선 관리 및 회귀 테스트")


@app.command(name="list")
def baseline_list(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
):
    """프롬프트의 기준선 목록 조회.

    Usage: baseline list prep_generate
    """
    typer.echo(f"\n📋 기준선 목록: {name}")
    typer.echo("-" * 60)

    baselines = list_baselines(name)

    if not baselines:
        typer.echo("저장된 기준선이 없습니다.")
        typer.echo("'baseline set' 명령으로 기준선을 설정하세요.")
        typer.echo()
        return

    for b in baselines:
        pass_rate = b.get("pass_rate")
        pass_rate_str = f"{pass_rate:.1%}" if pass_rate is not None else "-"
        typer.echo(f"  • {b['version']} | {b['created_at'][:10]} | pass_rate: {pass_rate_str}")

    typer.echo()


@app.command(name="set")
def baseline_set(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    experiment: Annotated[str, typer.Argument(help="LangSmith 실험 이름")],
    version: Annotated[Optional[str], typer.Option("--version", "-v", help="버전 태그")] = None,
):
    """LangSmith 실험 결과를 기준선으로 설정.

    Usage: baseline set prep_generate "prep_generate-full-2024-01-26"
    """
    typer.echo(f"\n기준선 설정: {name}")
    typer.echo(f"  실험: {experiment}")

    if version is None:
        metadata = load_metadata(name)
        version = metadata.get("current_version", "latest") if metadata else "latest"

    typer.echo(f"  버전: {version}")

    try:
        path = set_as_baseline(name, experiment, version)
        typer.echo(f"\n✓ 기준선 저장 완료: {path}")
    except Exception as e:
        typer.echo(f"\n✗ 기준선 설정 실패: {e}")
        raise typer.Exit(1)


@app.command(name="delete")
def baseline_delete(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    version: Annotated[str, typer.Argument(help="삭제할 버전 태그")],
):
    """기준선 삭제.

    Usage: baseline delete prep_generate v1.0
    """
    if delete_baseline(name, version):
        typer.echo(f"✓ 기준선 삭제 완료: {name} {version}")
    else:
        typer.echo(f"기준선을 찾을 수 없습니다: {name} {version}")
        raise typer.Exit(1)
