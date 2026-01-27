"""데이터셋 및 평가 세트 CLI 명령어"""

from typing import Annotated

import typer

from src.loaders import list_evaluation_sets
from utils import upload_to_langsmith


def list_sets():
    """사용 가능한 평가 세트 목록 출력."""
    sets = list_evaluation_sets()

    if not sets:
        typer.echo("사용 가능한 평가 세트가 없습니다.")
        typer.echo("targets/{name}/prompt.*, targets/{name}/config.yaml, datasets/{name}/ 구조가 필요합니다.")
        return

    typer.echo("\n사용 가능한 평가 세트:")
    for s in sets:
        typer.echo(f"  - {s}")
    typer.echo()


def upload(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
):
    """데이터셋을 LangSmith에 업로드."""
    typer.echo(f"\nLangSmith 데이터셋 업로드: {name}")
    dataset_name = upload_to_langsmith(name)
    typer.echo(f"완료: {dataset_name}\n")
