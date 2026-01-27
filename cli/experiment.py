"""실험 및 회귀 테스트 CLI 명령어"""

from typing import Annotated, Optional

import typer

from src.pipeline import run_langsmith_experiment
from src.versioning.prompt_metadata import (
    load_metadata,
    init_metadata,
    is_prompt_changed,
    auto_version_and_push_info,
    update_last_pushed_hash,
    compute_prompt_hash,
)
from src.regression.baseline import load_baseline
from src.regression.comparator import compare_results, format_regression_report
from utils import push_prompt
from utils.git import get_git_user_email


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

    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

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

    author = get_git_user_email()
    if author is None:
        typer.echo("git config user.email이 설정되지 않았습니다.")
        raise typer.Exit(1)

    metadata = load_metadata(name)
    is_first_init = metadata is None

    if is_first_init:
        typer.echo("  메타데이터 없음 → 자동 초기화")
        metadata = init_metadata(name, author)
        typer.echo(f"  ✓ 초기화 완료 (owner: {author}, version: v1.0)")

        typer.echo("  LangSmith에 업로드 중...")
        prompt_hash = compute_prompt_hash(name)
        metadata_info = {
            "version": "v1.0",
            "author": author,
            "changes": "Initial version",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        try:
            push_prompt(
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
        typer.echo("  프롬프트 변경 감지됨")

        if changes is None:
            changes = typer.prompt("  변경 내용을 입력하세요")

        version_info = auto_version_and_push_info(name, author, changes)
        new_version = version_info["version"]
        prompt_hash = version_info["prompt_hash"]

        typer.echo(f"  ✓ 새 버전 생성: {new_version}")
        typer.echo(f"    작성자: {author}")
        typer.echo(f"    변경: {changes}")

        typer.echo("  LangSmith에 업로드 중...")
        from datetime import datetime
        metadata_info = {
            "version": new_version,
            "author": author,
            "changes": changes,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        try:
            push_prompt(
                name,
                version_tag=new_version,
                metadata_info=metadata_info,
            )
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

    run_langsmith_experiment(
        prompt_name=name,
        mode=mode,
        experiment_prefix=prefix,
        prompt_version=None,
    )


def regression(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    baseline_version: Annotated[Optional[str], typer.Option("--baseline", "-b", help="기준선 버전 (기본: latest)")] = None,
    current_experiment: Annotated[Optional[str], typer.Option("--experiment", "-e", help="비교할 실험 이름")] = None,
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="회귀 임계값 (기본: 0.05 = 5%)")] = 0.05,
    fail_on_regression: Annotated[bool, typer.Option("--fail", "-f", help="회귀 시 exit code 1 반환")] = False,
):
    """회귀 테스트 실행.

    기준선과 현재 (또는 지정된 실험) 결과를 비교하여 성능 저하를 감지합니다.

    Usage:
        # 최신 실험과 기준선 비교
        regression --name prep_generate

        # 특정 실험과 비교
        regression --name prep_generate --experiment "prep_generate-full-2024-01-26"

        # CI/CD에서 사용 (회귀 시 실패)
        regression --name prep_generate --fail
    """
    typer.echo(f"\n회귀 테스트: {name}")
    typer.echo("-" * 60)

    baseline = load_baseline(name, baseline_version)
    if baseline is None:
        typer.echo(f"기준선을 찾을 수 없습니다: {name} {baseline_version or 'latest'}")
        typer.echo("'baseline set' 명령으로 기준선을 먼저 설정하세요.")
        raise typer.Exit(1)

    typer.echo(f"  기준선: {baseline.get('version', 'unknown')} ({baseline.get('created_at', '')[:10]})")

    if current_experiment:
        typer.echo(f"  비교 대상: {current_experiment}")
        from langsmith import Client
        client = Client()

        try:
            runs = list(client.list_runs(project_name=current_experiment))
            current = {
                "version": "current",
                "results": {
                    "summary": _compute_summary_from_runs(runs),
                    "cases": _extract_case_results(runs),
                }
            }
        except Exception as e:
            typer.echo(f"실험을 가져올 수 없습니다: {e}")
            raise typer.Exit(1)
    else:
        typer.echo("  비교 대상: 최신 실험 결과 필요")
        typer.echo("\n--experiment 옵션으로 비교할 실험 이름을 지정하세요.")
        typer.echo("예: regression --name prep_generate --experiment 'prep_generate-full-...'")
        raise typer.Exit(1)

    report = compare_results(baseline, current, threshold)

    typer.echo()
    typer.echo(format_regression_report(report))

    if fail_on_regression and report.has_regression:
        raise typer.Exit(1)


def _compute_summary_from_runs(runs: list) -> dict:
    """실행 결과에서 요약 통계 계산"""
    if not runs:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

    scores = []
    for run in runs:
        if run.feedback_stats:
            for key, stats in run.feedback_stats.items():
                if "avg" in stats:
                    scores.append(stats["avg"])

    total = len(runs)
    passed = sum(1 for run in runs if _is_run_passed(run))

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else None,
    }


def _is_run_passed(run) -> bool:
    """실행이 통과했는지 판단"""
    if not run.feedback_stats:
        return True
    for key, stats in run.feedback_stats.items():
        if "avg" in stats and stats["avg"] < 0.5:
            return False
    return True


def _extract_case_results(runs: list) -> list[dict]:
    """실행 결과에서 케이스별 결과 추출"""
    case_results = []
    for run in runs:
        case_data = {
            "run_id": str(run.id),
            "inputs": run.inputs,
            "outputs": run.outputs,
            "feedback_stats": run.feedback_stats,
            "passed": _is_run_passed(run),
        }
        case_results.append(case_data)
    return case_results
