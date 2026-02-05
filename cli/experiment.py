"""실험 및 회귀 테스트 CLI 명령어"""

from typing import Annotated, Literal, Optional

import typer

from src.pipelines.pipeline import run_experiment, run_langsmith_experiment
from src.versioning.prompt_metadata import (
    load_metadata,
    init_metadata,
    is_prompt_changed,
    auto_version_and_push_info,
    update_last_pushed_hash,
    update_langfuse_version,
    compute_prompt_hash,
)
from src.regression.baseline import (
    load_baseline,
    save_experiment_result,
    load_latest_experiment,
    normalize_experiment_to_baseline,
)
from src.regression.comparator import compare_results, format_regression_report
from utils.prompt_sync import push_prompt
from utils.git import get_git_user_email


def _auto_version_and_push(
    name: str,
    backend: str,
    changes: str | None = None,
) -> dict | None:
    """공유 버저닝 함수: 메타데이터 체크 → 변경 감지 → 버전 증가 → push

    Args:
        name: 프롬프트 이름
        backend: "langsmith" | "langfuse" | "both"
        changes: 변경 내용 설명 (변경 시 필요, None이면 프롬프트로 입력)

    Returns:
        버전 정보 dict 또는 None (에러 시 typer.Exit 호출)
    """
    from pathlib import Path
    from datetime import datetime

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

        prompt_hash = compute_prompt_hash(name)
        version_tag = "v1.0"
        metadata_info = {
            "version": version_tag,
            "author": author,
            "changes": "Initial version",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        typer.echo("  업로드 중...")
        result = push_prompt(name, backend=backend, version_tag=version_tag, metadata_info=metadata_info)
        if result.get("langsmith_error") or result.get("langfuse_error"):
            for key in ("langsmith_error", "langfuse_error"):
                if result.get(key):
                    typer.echo(f"  ✗ {key}: {result[key]}")
            raise typer.Exit(1)
        if result.get("langfuse_version") is not None:
            update_langfuse_version(name, version_tag, result["langfuse_version"])
        typer.echo("  ✓ 업로드 완료")

        update_last_pushed_hash(name, prompt_hash)
        return {"version": version_tag, "is_new": True}

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

        metadata_info = {
            "version": new_version,
            "author": author,
            "changes": changes,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        typer.echo("  업로드 중...")
        result = push_prompt(name, backend=backend, version_tag=new_version, metadata_info=metadata_info)
        if result.get("langsmith_error") or result.get("langfuse_error"):
            for key in ("langsmith_error", "langfuse_error"):
                if result.get(key):
                    typer.echo(f"  ✗ {key}: {result[key]}")
            raise typer.Exit(1)
        if result.get("langfuse_version") is not None:
            update_langfuse_version(name, new_version, result["langfuse_version"])
        typer.echo("  ✓ 업로드 완료")

        update_last_pushed_hash(name, prompt_hash)
        return {"version": new_version, "is_new": True}

    else:
        current_version = metadata.get("current_version", "v1.0")
        typer.echo("  프롬프트 변경 없음 → 기존 버전 사용")
        typer.echo(f"  현재 버전: {current_version}")
        return {"version": current_version, "is_new": False}


def _save_langfuse_result(name: str, result: dict) -> None:
    """Langfuse 실험 결과를 로컬에 저장"""
    if result and isinstance(result, dict):
        path = save_experiment_result(name, result)
        typer.echo(f"  결과 저장: {path}")


def experiment(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="실행 모드 (quick/full)")] = "full",
    prefix: Annotated[Optional[str], typer.Option("--prefix", "-p", help="실험 이름 접두사")] = None,
    version: Annotated[Optional[str], typer.Option("--version", "-v", help="프롬프트 버전 태그")] = None,
    changes: Annotated[Optional[str], typer.Option("--changes", "-c", help="변경 내용 (프롬프트 변경 시)")] = None,
    no_push: Annotated[bool, typer.Option("--no-push", help="자동 push 비활성화")] = False,
    backend: Annotated[str, typer.Option("--backend", "-b", help="실험 백엔드 (langsmith/langfuse/both)")] = "both",
):
    """평가 실험 실행 (LangSmith 또는 Langfuse).

    자동화 플로우:
    1. 메타데이터 없으면 자동 init
    2. 프롬프트 변경 감지 시 자동 버전 증가 + push (양쪽 플랫폼)
    3. 평가 실행
    4. Langfuse 결과는 로컬에 자동 저장

    --no-push 또는 --version 지정 시 버저닝 건너뜀.
    """
    from pathlib import Path

    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

    if backend not in ["langsmith", "langfuse", "both"]:
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse/both")
        raise typer.Exit(1)

    prompt_dir = Path("targets") / name
    if not prompt_dir.exists():
        typer.echo(f"프롬프트 폴더 없음: {prompt_dir}")
        raise typer.Exit(1)

    # 자동 버저닝 (--no-push, --version 미지정 시)
    if not no_push and not version:
        _auto_version_and_push(name, backend=backend, changes=changes)
        typer.echo("-" * 60)

    # Chain 파이프라인 감지 → E2E 파이프라인으로 위임
    import yaml
    config_file = prompt_dir / "config.yaml"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            eval_config = yaml.safe_load(f)
        if eval_config.get("pipeline_type") == "chain":
            from src.pipelines.e2e_chain import (
                run_e2e_pipeline,
                run_e2e_langfuse_experiment,
                run_e2e_langsmith_experiment,
            )
            typer.echo(f"\nChain Pipeline: {name}")
            if backend == "both":
                typer.echo("-" * 60)
                result = run_e2e_langfuse_experiment(prompt_name=name, mode=mode, experiment_prefix=prefix)
                _save_langfuse_result(name, result)
                typer.echo("-" * 60)
                run_e2e_langsmith_experiment(prompt_name=name, mode=mode, experiment_prefix=prefix)
            elif backend == "langfuse":
                result = run_e2e_langfuse_experiment(prompt_name=name, mode=mode, experiment_prefix=prefix)
                _save_langfuse_result(name, result)
            elif backend == "langsmith":
                run_e2e_langsmith_experiment(prompt_name=name, mode=mode, experiment_prefix=prefix)
            return

    # both: Langfuse + LangSmith 동시 실행
    if backend == "both":
        typer.echo(f"\n🔬 [1/2] Langfuse Experiment 실행: {name}")
        typer.echo("-" * 60)
        result = run_experiment(
            prompt_name=name,
            mode=mode,
            experiment_prefix=prefix,
            prompt_version=version,
            backend="langfuse",
        )
        _save_langfuse_result(name, result)
        typer.echo(f"\n🔬 [2/2] LangSmith Experiment 실행: {name}")
        typer.echo("-" * 60)
        run_experiment(
            prompt_name=name,
            mode=mode,
            experiment_prefix=prefix,
            prompt_version=version,
            backend="langsmith",
        )
        return

    # Langfuse 백엔드
    if backend == "langfuse":
        typer.echo(f"\n🔬 Langfuse Experiment 실행: {name}")
        typer.echo("-" * 60)
        result = run_experiment(
            prompt_name=name,
            mode=mode,
            experiment_prefix=prefix,
            prompt_version=version,
            backend="langfuse",
        )
        _save_langfuse_result(name, result)
        return

    # LangSmith 백엔드
    run_experiment(
        prompt_name=name,
        mode=mode,
        experiment_prefix=prefix,
        prompt_version=version,
        backend="langsmith",
    )


def regression(
    name: Annotated[str, typer.Option("--name", "-n", help="프롬프트 이름")],
    baseline_version: Annotated[Optional[str], typer.Option("--baseline", help="기준선 버전 (기본: latest)")] = None,
    current_experiment: Annotated[Optional[str], typer.Option("--experiment", "-e", help="비교할 실험 이름")] = None,
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="회귀 임계값 (기본: 0.05 = 5%)")] = 0.05,
    fail_on_regression: Annotated[bool, typer.Option("--fail", "-f", help="회귀 시 exit code 1 반환")] = False,
    source: Annotated[str, typer.Option("--source", "-s", help="데이터 소스 (langsmith/local)")] = "local",
):
    """회귀 테스트 실행.

    기준선과 현재 (또는 지정된 실험) 결과를 비교하여 성능 저하를 감지합니다.

    Usage:
        # 로컬 최신 실험과 기준선 비교 (Langfuse 등)
        regression --name prep_generate

        # LangSmith 실험과 비교
        regression --name prep_generate --source langsmith --experiment "prep_generate-full-..."

        # CI/CD에서 사용 (회귀 시 실패)
        regression --name prep_generate --fail
    """
    typer.echo(f"\n회귀 테스트: {name}")
    typer.echo("-" * 60)

    baseline = load_baseline(name, baseline_version)
    if baseline is None:
        typer.echo(f"기준선을 찾을 수 없습니다: {name} {baseline_version or 'latest'}")
        typer.echo("'baseline set' 또는 'baseline set-local' 명령으로 기준선을 먼저 설정하세요.")
        raise typer.Exit(1)

    typer.echo(f"  기준선: {baseline.get('version', 'unknown')} ({baseline.get('created_at', '')[:10]})")

    if source == "local":
        # 로컬 실험 결과에서 비교
        experiment_data = load_latest_experiment(name)
        if experiment_data is None:
            typer.echo("  로컬 실험 결과를 찾을 수 없습니다.")
            typer.echo("  먼저 experiment 명령으로 실험을 실행하세요.")
            raise typer.Exit(1)

        typer.echo(f"  비교 대상: {experiment_data.get('experiment_name', 'latest')} (local)")
        current = normalize_experiment_to_baseline(experiment_data)

    elif source == "langsmith":
        if not current_experiment:
            typer.echo("  --source langsmith 사용 시 --experiment 옵션이 필요합니다.")
            typer.echo("  예: regression --name prep_generate --source langsmith --experiment 'prep_generate-full-...'")
            raise typer.Exit(1)

        typer.echo(f"  비교 대상: {current_experiment} (langsmith)")
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
        typer.echo(f"Invalid source: {source}. Use langsmith/local")
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
