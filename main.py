"""프롬프트 평가 CLI

Usage:
    # 로컬 평가
    poetry run python main.py eval --name prep_analyzer
    poetry run python main.py eval --name prep_analyzer --mode full

    # LangSmith Experiment (정식 평가)
    poetry run python main.py experiment --name prep_analyzer

    # 프롬프트 버전 관리
    poetry run python main.py prompt push --name prep_analyzer --tag v1.0
    poetry run python main.py prompt versions --name prep_analyzer

    # 평가 세트 목록
    poetry run python main.py list

    # 사용 가능한 평가 기준 확인
    poetry run python main.py criteria
"""

from typing import Annotated, Optional

import typer
from dotenv import load_dotenv

from src.data_loader import (
    find_prompt_file,
    list_evaluation_sets,
    list_prompt_versions,
    load_prompt_file,
    pull_prompt,
    push_prompt,
    upload_to_langsmith,
)
from src.evaluators.llm_judge import list_available_criteria
from src.pipeline import run_langsmith_experiment, run_pipeline
from src.report import (
    generate_markdown_report,
    print_case_details,
    print_failed_cases,
    print_summary,
    save_results,
)
from utils.models import execution_llm

load_dotenv()

app = typer.Typer(
    name="prompt-evaluator",
    help="프롬프트 평가 시스템 CLI"
)


@app.command()
def eval(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름 (예: prep_analyzer)")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="실행 모드 (quick/full)")] = "quick",
    upload: Annotated[bool, typer.Option("--upload", "-u", help="LangSmith에 업로드 후 평가")] = False,
    case_id: Annotated[Optional[str], typer.Option("--case-id", "-c", help="특정 케이스만 실행 (쉼표 구분)")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="상세 출력")] = False,
    save: Annotated[bool, typer.Option("--save", help="결과 파일 저장")] = True,
):
    """프롬프트 평가 실행."""
    # 모드 검증
    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

    # 케이스 ID 파싱
    case_ids = None
    if case_id:
        case_ids = [c.strip() for c in case_id.split(",")]

    typer.echo(f"\n프롬프트 평가 시작: {name}")
    typer.echo(f"  모드: {mode}")
    typer.echo(f"  모델: {execution_llm.model_name}")
    if case_ids:
        typer.echo(f"  케이스: {case_ids}")
    typer.echo()

    # LangSmith 업로드 (선택)
    if upload:
        typer.echo("LangSmith 데이터셋 업로드 중...")
        dataset_name = upload_to_langsmith(name)
        typer.echo(f"  완료: {dataset_name}\n")

    # 파이프라인 실행
    typer.echo("평가 실행 중...")
    result = run_pipeline(
        prompt_name=name,
        mode=mode,
        case_ids=case_ids,
    )

    # 결과 출력
    print_summary(result)

    if verbose:
        print_case_details(result, verbose=True)
    else:
        print_failed_cases(result)

    # 결과 저장
    if save:
        save_results(result)
        generate_markdown_report(result)


@app.command(name="list")
def list_sets():
    """사용 가능한 평가 세트 목록 출력."""
    sets = list_evaluation_sets()

    if not sets:
        typer.echo("사용 가능한 평가 세트가 없습니다.")
        typer.echo("targets/{name}_prompt.txt와 datasets/{name}_data/, configs/{name}.yaml 구조가 필요합니다.")
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
):
    """LangSmith Experiment 실행 (정식 평가, 버전 비교용)."""
    # 모드 검증
    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

    run_langsmith_experiment(
        prompt_name=name,
        mode=mode,
        experiment_prefix=prefix,
        prompt_version=version,
    )


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
    typer.echo("사용법: configs/{name}.yaml의 llm_judge.criteria에 추가")
    typer.echo("  예: criteria: [purpose_alignment, coaching_quality]")
    typer.echo()


# =============================================================================
# 프롬프트 버전 관리 (LangSmith Prompts)
# =============================================================================

prompt_app = typer.Typer(help="프롬프트 버전 관리 (LangSmith)")
app.add_typer(prompt_app, name="prompt")


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
