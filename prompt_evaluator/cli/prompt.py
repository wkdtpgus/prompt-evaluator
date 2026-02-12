"""프롬프트 버전 관리 CLI 명령어"""

from typing import Annotated, Optional

import typer

from prompt_evaluator.loaders import find_prompt_file, load_prompt_file
from prompt_evaluator.versioning.prompt_metadata import (
    load_metadata,
    init_metadata,
    add_version,
    get_version_history,
)
from prompt_evaluator.utils.prompt_sync import (
    push_prompt,
    get_prompt,
    list_prompt_versions,
)
from prompt_evaluator.utils.git import get_git_user_email


app = typer.Typer(help="프롬프트 버전 관리 (LangSmith + Langfuse)")


@app.command(name="info")
def prompt_info(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
):
    """프롬프트 메타데이터 조회 (로컬 버전 이력).

    Usage: prompt info prep_generate
    """
    typer.echo(f"\n📋 프롬프트 정보: {name}")
    typer.echo("-" * 60)

    metadata = load_metadata(name)

    if metadata is None:
        typer.echo("메타데이터 없음. 'prompt init'으로 초기화하세요.")
        typer.echo()
        return

    typer.echo(f"  소유자: {metadata.get('owner', '(미지정)')}")
    typer.echo(f"  생성일: {metadata.get('created_at', '(미지정)')}")
    typer.echo(f"  현재 버전: {metadata.get('current_version', '(미지정)')}")

    history = get_version_history(name)
    if history:
        typer.echo(f"\n  [버전 이력] ({len(history)}개)")
        for v in history[:5]:
            hash_str = (
                f" | {v['langsmith_hash'][:8]}" if v.get("langsmith_hash") else ""
            )
            typer.echo(f"    • {v['version']} ({v['date']}) - {v['changes']}{hash_str}")
        if len(history) > 5:
            typer.echo(f"    ... 외 {len(history) - 5}개")

    typer.echo()


@app.command(name="init")
def prompt_init(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    owner: Annotated[
        Optional[str],
        typer.Option("--owner", "-o", help="소유자 이메일 (생략시 git config 사용)"),
    ] = None,
):
    """프롬프트 메타데이터 초기화.

    Usage: prompt init prep_generate
    """
    from prompt_evaluator.context import get_context

    if owner is None:
        owner = get_git_user_email()
        if owner is None:
            typer.echo(
                "git config user.email이 설정되지 않았습니다. --owner 옵션을 사용하세요."
            )
            raise typer.Exit(1)

    ctx = get_context()
    prompt_dir = ctx.targets_dir / name
    if not prompt_dir.exists():
        typer.echo(f"프롬프트 폴더 없음: {prompt_dir}")
        raise typer.Exit(1)

    existing = load_metadata(name)
    if existing:
        typer.echo(
            f"이미 메타데이터가 존재합니다. (현재 버전: {existing.get('current_version')})"
        )
        raise typer.Exit(1)

    init_metadata(name, owner)
    typer.echo(f"\n✓ 메타데이터 초기화 완료: {name}")
    typer.echo(f"  소유자: {owner}")
    typer.echo("  버전: v1.0")
    typer.echo(f"  파일: targets/{name}/.metadata.yaml")
    typer.echo()


@app.command(name="add-version")
def prompt_add_version(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    version: Annotated[str, typer.Argument(help="버전 태그 (예: v1.2)")],
    changes: Annotated[str, typer.Argument(help="변경 내용")],
    author: Annotated[
        Optional[str],
        typer.Option("--author", "-a", help="작성자 이메일 (생략시 git config 사용)"),
    ] = None,
):
    """새 버전 추가.

    Usage: prompt add-version prep_generate v1.2 "톤 개선"
    """
    if author is None:
        author = get_git_user_email()
        if author is None:
            typer.echo(
                "git config user.email이 설정되지 않았습니다. --author 옵션을 사용하세요."
            )
            raise typer.Exit(1)

    try:
        add_version(name, version, author, changes)
        typer.echo(f"\n✓ 버전 추가 완료: {name} {version}")
        typer.echo(f"  작성자: {author}")
        typer.echo(f"  변경: {changes}")
        typer.echo()
    except FileNotFoundError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@app.command(name="push")
def prompt_push(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    tag: Annotated[
        Optional[str],
        typer.Option("--tag", "-t", help="버전 태그 (예: v1.0, production)"),
    ] = None,
    description: Annotated[
        Optional[str], typer.Option("--desc", "-d", help="프롬프트 설명")
    ] = None,
    key: Annotated[
        Optional[str],
        typer.Option(
            "--key", "-k", help=".py/.xml 파일의 특정 프롬프트 키 (예: SYSTEM_PROMPT)"
        ),
    ] = None,
    backend: Annotated[
        str,
        typer.Option("--backend", "-b", help="업로드 대상 (langsmith/langfuse/both)"),
    ] = "both",
):
    """로컬 프롬프트를 LangSmith/Langfuse에 업로드.

    지원 형식: .txt, .py, .xml
    """
    if backend not in ("langsmith", "langfuse", "both"):
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse/both")
        raise typer.Exit(1)

    typer.echo(f"\n프롬프트 업로드: {name} (backend: {backend})")
    if tag:
        typer.echo(f"  태그: {tag}")
    if key:
        typer.echo(f"  키: {key}")

    try:
        push_prompt(
            name,
            backend=backend,
            version_tag=tag,
            description=description,
            prompt_key=key,
        )
        typer.echo("\n완료!")
    except FileNotFoundError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@app.command(name="pull")
def prompt_pull(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    tag: Annotated[
        Optional[str], typer.Option("--tag", "-t", help="특정 버전 태그")
    ] = None,
    save: Annotated[
        bool, typer.Option("--save", "-s", help="로컬 파일로 저장")
    ] = False,
    backend: Annotated[
        str, typer.Option("--backend", "-b", help="조회 대상 (langsmith/langfuse)")
    ] = "langsmith",
):
    """LangSmith/Langfuse에서 프롬프트 가져오기."""
    if backend not in ("langsmith", "langfuse"):
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse")
        raise typer.Exit(1)

    typer.echo(f"\n프롬프트 가져오기: {name} (backend: {backend})")
    if tag:
        typer.echo(f"  태그: {tag}")

    try:
        template = get_prompt(name, backend=backend, version_tag=tag)

        if save:
            from prompt_evaluator.context import get_context

            ctx = get_context()
            output_file = ctx.targets_dir / f"{name}_prompt.txt"
            output_file.write_text(template, encoding="utf-8")
            typer.echo(f"\n저장 완료: {output_file}")
        else:
            typer.echo("\n" + "-" * 60)
            typer.echo(template[:500] + "..." if len(template) > 500 else template)
            typer.echo("-" * 60)

    except Exception as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@app.command(name="keys")
def prompt_keys(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
):
    """로컬 프롬프트 파일의 키 목록 조회 (.py/.xml 파일용)."""
    from prompt_evaluator.context import get_context

    try:
        ctx = get_context()
        prompt_file = find_prompt_file(name, ctx.targets_dir)
        prompts = load_prompt_file(prompt_file)

        typer.echo(f"\n프롬프트 파일: {prompt_file}")
        typer.echo(f"형식: {prompt_file.suffix}")
        typer.echo("-" * 60)

        for key, value in prompts.items():
            preview = value[:100].replace("\n", " ")
            if len(value) > 100:
                preview += "..."
            typer.echo(f"  • {key}: {preview}")

        typer.echo()
        if prompt_file.suffix != ".txt":
            typer.echo("특정 프롬프트 업로드: prompt push --name {name} --key {KEY}")
        typer.echo()

    except FileNotFoundError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@app.command(name="versions")
def prompt_versions(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
):
    """프롬프트의 버전 목록 조회."""
    typer.echo(f"\n프롬프트 버전 목록: {name}")
    typer.echo("-" * 60)

    versions = list_prompt_versions(name)

    if not versions:
        typer.echo("버전 정보가 없습니다. 먼저 prompt push를 실행하세요.")
        return

    for i, v in enumerate(versions, 1):
        tags_str = ", ".join(v["tags"]) if v["tags"] else "(태그 없음)"
        typer.echo(f"  {i}. {v['commit_hash'][:8]} | {tags_str} | {v['created_at']}")

    typer.echo()
