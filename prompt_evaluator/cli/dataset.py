"""데이터셋 및 평가 세트 CLI 명령어"""

from typing import Annotated

import typer

from prompt_evaluator.loaders import list_evaluation_sets
from prompt_evaluator.utils.dataset_sync import upload_dataset


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
    backend: Annotated[str, typer.Option("--backend", "-b", help="업로드 대상 (langsmith/langfuse/both)")] = "both",
):
    """데이터셋을 LangSmith/Langfuse에 업로드."""
    if backend not in ("langsmith", "langfuse", "both"):
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse/both")
        raise typer.Exit(1)

    typer.echo(f"\n데이터셋 업로드: {name} (backend: {backend})")
    result = upload_dataset(name, backend=backend)

    if result.get("langsmith_name"):
        typer.echo(f"✓ [LangSmith] 완료: {result['langsmith_name']}")
    if result.get("langsmith_error"):
        typer.echo(f"✗ [LangSmith] 실패: {result['langsmith_error']}")
    if result.get("langfuse_results") is not None:
        success = sum(result["langfuse_results"].values())
        total = len(result["langfuse_results"])
        typer.echo(f"✓ [Langfuse] 완료: {success}/{total} 케이스")
    if result.get("langfuse_error"):
        typer.echo(f"✗ [Langfuse] 실패: {result['langfuse_error']}")

    typer.echo()
