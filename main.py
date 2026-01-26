"""프롬프트 평가 CLI

Usage:
    # 설정 검증
    poetry run python main.py validate --name prep_generate
    poetry run python main.py validate --all

    # LangSmith Experiment (정식 평가)
    poetry run python main.py experiment --name prep_generate

    # 프롬프트 버전 관리
    poetry run python main.py prompt push --name prep_generate --tag v1.0
    poetry run python main.py prompt versions --name prep_generate

    # 평가 세트 목록
    poetry run python main.py list

    # 사용 가능한 평가 기준 확인
    poetry run python main.py criteria
"""

import subprocess
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv


def get_git_user_email() -> str | None:
    """git config에서 user.email 가져오기"""
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

from src.loaders import (
    find_prompt_file,
    list_evaluation_sets,
    load_prompt_file,
)
from utils import (
    list_prompt_versions,
    pull_prompt,
    push_prompt,
    upload_to_langsmith,
)
from src.versioning.prompt_metadata import (
    load_metadata,
    init_metadata,
    add_version,
    get_version_history,
    ensure_metadata_exists,
    is_prompt_changed,
    auto_version_and_push_info,
    update_last_pushed_hash,
    compute_prompt_hash,
)
from src.evaluators.llm_judge import list_available_criteria
from src.pipeline import run_langsmith_experiment
from utils.config_validator import validate_config, validate_all_configs

load_dotenv()

app = typer.Typer(
    name="prompt-evaluator",
    help="프롬프트 평가 시스템 CLI"
)


@app.command(name="list")
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


@app.command()
def upload(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
):
    """데이터셋을 LangSmith에 업로드."""
    typer.echo(f"\nLangSmith 데이터셋 업로드: {name}")
    dataset_name = upload_to_langsmith(name)
    typer.echo(f"완료: {dataset_name}\n")


@app.command()
def experiment(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="실행 모드 (quick/full)")] = "full",
    prefix: Annotated[Optional[str], typer.Option("--prefix", "-p", help="실험 이름 접두사")] = None,
    version: Annotated[Optional[str], typer.Option("--version", "-v", help="LangSmith 프롬프트 버전 태그")] = None,
    changes: Annotated[Optional[str], typer.Option("--changes", "-c", help="변경 내용 (프롬프트 변경 시)")] = None,
    no_push: Annotated[bool, typer.Option("--no-push", help="자동 push 비활성화")] = False,
):
    """LangSmith Experiment 실행 (정식 평가, 버전 비교용).

    자동화 플로우:
    1. 메타데이터 없으면 자동 init
    2. 프롬프트 변경 감지 시 자동 버전 증가 + LangSmith push
    3. 평가 실행
    """
    from pathlib import Path
    from datetime import datetime

    # 모드 검증
    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

    # 프롬프트 폴더 존재 확인
    prompt_dir = Path("targets") / name
    if not prompt_dir.exists():
        typer.echo(f"프롬프트 폴더 없음: {prompt_dir}")
        raise typer.Exit(1)

    # --no-push 또는 --version 지정 시 기존 로직 사용
    if no_push or version:
        run_langsmith_experiment(
            prompt_name=name,
            mode=mode,
            experiment_prefix=prefix,
            prompt_version=version,
        )
        return

    # 자동화 플로우 시작
    typer.echo(f"\n프롬프트 버전 관리 체크: {name}")
    typer.echo("-" * 60)

    # 1. 메타데이터 확인
    author = get_git_user_email()
    if author is None:
        typer.echo("git config user.email이 설정되지 않았습니다.")
        raise typer.Exit(1)

    metadata = load_metadata(name)
    is_first_init = metadata is None

    if is_first_init:
        # 첫 init: 메타데이터 생성 + 바로 push (변경 내용 입력 불필요)
        typer.echo("  메타데이터 없음 → 자동 초기화")
        metadata = init_metadata(name, author)
        typer.echo(f"  ✓ 초기화 완료 (owner: {author}, version: v1.0)")

        # 첫 push
        typer.echo("  LangSmith에 업로드 중...")
        prompt_hash = compute_prompt_hash(name)
        metadata_info = {
            "version": "v1.0",
            "author": author,
            "changes": "Initial version",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        try:
            url = push_prompt(
                name,
                version_tag="v1.0",
                metadata_info=metadata_info,
            )
            update_last_pushed_hash(name, prompt_hash)
            typer.echo(f"  ✓ LangSmith 업로드 완료")
        except Exception as e:
            typer.echo(f"  ✗ LangSmith 업로드 실패: {e}")
            raise typer.Exit(1)

    elif is_prompt_changed(name):
        # 2. 프롬프트 변경 감지 (기존 메타데이터가 있는 경우만)
        typer.echo("  프롬프트 변경 감지됨")

        # changes가 없으면 인터랙티브 입력
        if changes is None:
            changes = typer.prompt("  변경 내용을 입력하세요")

        # 자동 버전 증가
        version_info = auto_version_and_push_info(name, author, changes)
        new_version = version_info["version"]
        prompt_hash = version_info["prompt_hash"]

        typer.echo(f"  ✓ 새 버전 생성: {new_version}")
        typer.echo(f"    작성자: {author}")
        typer.echo(f"    변경: {changes}")

        # LangSmith에 push
        typer.echo("  LangSmith에 업로드 중...")
        metadata_info = {
            "version": new_version,
            "author": author,
            "changes": changes,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        try:
            url = push_prompt(
                name,
                version_tag=new_version,
                metadata_info=metadata_info,
            )
            # push 성공 시 해시 업데이트
            update_last_pushed_hash(name, prompt_hash)
            typer.echo(f"  ✓ LangSmith 업로드 완료")
        except Exception as e:
            typer.echo(f"  ✗ LangSmith 업로드 실패: {e}")
            raise typer.Exit(1)
    else:
        typer.echo("  프롬프트 변경 없음 → 기존 버전 사용")
        current_version = metadata.get("current_version", "v1.0")
        typer.echo(f"  현재 버전: {current_version}")

    typer.echo("-" * 60)

    # 3. 평가 실행
    run_langsmith_experiment(
        prompt_name=name,
        mode=mode,
        experiment_prefix=prefix,
        prompt_version=None,  # 최신 버전 사용
    )


@app.command()
def validate(
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="검증할 프롬프트 이름")] = None,
    all_configs: Annotated[bool, typer.Option("--all", "-a", help="모든 config 검증")] = False,
):
    """config 파일 유효성 검증."""
    from pathlib import Path
    import yaml

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


@app.command()
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


# =============================================================================
# 프롬프트 버전 관리 (LangSmith Prompts)
# =============================================================================

prompt_app = typer.Typer(help="프롬프트 버전 관리 (LangSmith)")
app.add_typer(prompt_app, name="prompt")


@prompt_app.command(name="info")
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
        for v in history[:5]:  # 최근 5개만 표시
            hash_str = f" | {v['langsmith_hash'][:8]}" if v.get('langsmith_hash') else ""
            typer.echo(f"    • {v['version']} ({v['date']}) - {v['changes']}{hash_str}")
        if len(history) > 5:
            typer.echo(f"    ... 외 {len(history) - 5}개")

    typer.echo()


@prompt_app.command(name="init")
def prompt_init(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    owner: Annotated[Optional[str], typer.Option("--owner", "-o", help="소유자 이메일 (생략시 git config 사용)")] = None,
):
    """프롬프트 메타데이터 초기화.

    Usage: prompt init prep_generate
    """
    from pathlib import Path

    # owner 자동 감지
    if owner is None:
        owner = get_git_user_email()
        if owner is None:
            typer.echo("git config user.email이 설정되지 않았습니다. --owner 옵션을 사용하세요.")
            raise typer.Exit(1)

    # 프롬프트 폴더 존재 확인
    prompt_dir = Path("targets") / name
    if not prompt_dir.exists():
        typer.echo(f"프롬프트 폴더 없음: {prompt_dir}")
        raise typer.Exit(1)

    existing = load_metadata(name)
    if existing:
        typer.echo(f"이미 메타데이터가 존재합니다. (현재 버전: {existing.get('current_version')})")
        raise typer.Exit(1)

    metadata = init_metadata(name, owner)
    typer.echo(f"\n✓ 메타데이터 초기화 완료: {name}")
    typer.echo(f"  소유자: {owner}")
    typer.echo(f"  버전: v1.0")
    typer.echo(f"  파일: targets/{name}/.metadata.yaml")
    typer.echo()


@prompt_app.command(name="add-version")
def prompt_add_version(
    name: Annotated[str, typer.Argument(help="프롬프트 이름")],
    version: Annotated[str, typer.Argument(help="버전 태그 (예: v1.2)")],
    changes: Annotated[str, typer.Argument(help="변경 내용")],
    author: Annotated[Optional[str], typer.Option("--author", "-a", help="작성자 이메일 (생략시 git config 사용)")] = None,
):
    """새 버전 추가.

    Usage: prompt add-version prep_generate v1.2 "톤 개선"
    """
    # author 자동 감지
    if author is None:
        author = get_git_user_email()
        if author is None:
            typer.echo("git config user.email이 설정되지 않았습니다. --author 옵션을 사용하세요.")
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


@prompt_app.command(name="push")
def prompt_push(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    tag: Annotated[Optional[str], typer.Option("--tag", "-t", help="버전 태그 (예: v1.0, production)")] = None,
    description: Annotated[Optional[str], typer.Option("--desc", "-d", help="프롬프트 설명")] = None,
    key: Annotated[Optional[str], typer.Option("--key", "-k", help=".py/.xml 파일의 특정 프롬프트 키 (예: SYSTEM_PROMPT)")] = None,
):
    """로컬 프롬프트를 LangSmith에 업로드.

    지원 형식: .txt, .py, .xml
    """
    typer.echo(f"\n프롬프트 업로드: {name}")
    if tag:
        typer.echo(f"  태그: {tag}")
    if key:
        typer.echo(f"  키: {key}")

    try:
        url = push_prompt(name, version_tag=tag, description=description, prompt_key=key)
        typer.echo(f"\n완료! LangSmith에서 확인하세요.")
    except FileNotFoundError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@prompt_app.command(name="pull")
def prompt_pull(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    tag: Annotated[Optional[str], typer.Option("--tag", "-t", help="특정 버전 태그")] = None,
    save: Annotated[bool, typer.Option("--save", "-s", help="로컬 파일로 저장")] = False,
):
    """LangSmith에서 프롬프트 가져오기."""
    typer.echo(f"\n프롬프트 가져오기: {name}")
    if tag:
        typer.echo(f"  태그: {tag}")

    try:
        template = pull_prompt(name, version_tag=tag)

        if save:
            from pathlib import Path
            output_file = Path("targets") / f"{name}_prompt.txt"
            output_file.write_text(template, encoding="utf-8")
            typer.echo(f"\n저장 완료: {output_file}")
        else:
            typer.echo("\n" + "-" * 60)
            typer.echo(template[:500] + "..." if len(template) > 500 else template)
            typer.echo("-" * 60)

    except Exception as e:
        typer.echo(f"오류: {e}")
        raise typer.Exit(1)


@prompt_app.command(name="keys")
def prompt_keys(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
):
    """로컬 프롬프트 파일의 키 목록 조회 (.py/.xml 파일용)."""
    from pathlib import Path

    try:
        prompt_file = find_prompt_file(name, Path("targets"))
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


@prompt_app.command(name="versions")
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


if __name__ == "__main__":
    app()
