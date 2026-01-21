"""프롬프트 평가 CLI

Usage:
    # 로컬 평가
    poetry run python main.py eval --name prep_analyzer
    poetry run python main.py eval --name prep_analyzer --mode full

    # LangSmith Experiment (정식 평가)
    poetry run python main.py experiment --name prep_analyzer

    # 평가 세트 목록
    poetry run python main.py list

    # 사용 가능한 평가 기준 확인
    poetry run python main.py criteria
"""

from typing import Annotated, Optional

import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(
    name="prompt-evaluator",
    help="프롬프트 평가 시스템 CLI"
)


@app.command()
def eval(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름 (예: prep_analyzer)")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="실행 모드 (quick/standard/full)")] = "quick",
    upload: Annotated[bool, typer.Option("--upload", "-u", help="LangSmith에 업로드 후 평가")] = False,
    case_id: Annotated[Optional[str], typer.Option("--case-id", "-c", help="특정 케이스만 실행 (쉼표 구분)")] = None,
    model: Annotated[str, typer.Option("--model", help="LLM 모델")] = "gpt-4o-mini",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="상세 출력")] = False,
    save: Annotated[bool, typer.Option("--save", help="결과 파일 저장")] = True,
):
    """프롬프트 평가 실행."""
    from src.pipeline import run_pipeline
    from src.report import (
        print_summary,
        print_case_details,
        print_failed_cases,
        save_results,
        generate_markdown_report,
    )
    from src.data import upload_to_langsmith

    # 모드 검증
    if mode not in ["quick", "standard", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/standard/full")
        raise typer.Exit(1)

    # 케이스 ID 파싱
    case_ids = None
    if case_id:
        case_ids = [c.strip() for c in case_id.split(",")]

    typer.echo(f"\n프롬프트 평가 시작: {name}")
    typer.echo(f"  모드: {mode}")
    typer.echo(f"  모델: {model}")
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
        model=model
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
    from src.data import list_evaluation_sets

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
    from src.data import upload_to_langsmith

    typer.echo(f"\nLangSmith 데이터셋 업로드: {name}")
    dataset_name = upload_to_langsmith(name)
    typer.echo(f"완료: {dataset_name}\n")


@app.command()
def experiment(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="실행 모드 (quick/standard/full)")] = "standard",
    model: Annotated[str, typer.Option("--model", help="LLM 모델")] = "gpt-4o-mini",
    prefix: Annotated[Optional[str], typer.Option("--prefix", "-p", help="실험 이름 접두사")] = None,
):
    """LangSmith Experiment 실행 (정식 평가, 버전 비교용)."""
    from src.pipeline import run_langsmith_experiment

    # 모드 검증
    if mode not in ["quick", "standard", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/standard/full")
        raise typer.Exit(1)

    run_langsmith_experiment(
        prompt_name=name,
        mode=mode,
        model=model,
        experiment_prefix=prefix,
    )


@app.command()
def criteria():
    """사용 가능한 LLM Judge 평가 기준 목록 출력."""
    from src.evaluators.llm_judge import list_available_criteria

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


if __name__ == "__main__":
    app()
