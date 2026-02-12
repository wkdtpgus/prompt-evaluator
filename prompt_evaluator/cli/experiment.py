"""실험 및 회귀 테스트 CLI 명령어"""

from typing import Annotated, Optional

import typer

from prompt_evaluator.pipelines.pipeline import run_experiment
from prompt_evaluator.versioning.prompt_metadata import (
    load_metadata,
    init_metadata,
    is_prompt_changed,
    auto_version_and_push_info,
    update_last_pushed_hash,
    update_langfuse_version,
    compute_prompt_hash,
)
from prompt_evaluator.regression.baseline import (
    load_baseline,
    save_experiment_result,
    load_latest_experiment,
    normalize_experiment_to_baseline,
    _compute_summary_from_runs,
    _extract_case_results,
)
from prompt_evaluator.regression.comparator import (
    compare_results,
    format_regression_report,
)
from prompt_evaluator.utils.prompt_sync import push_prompt
from prompt_evaluator.utils.git import get_git_user_email


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
        result = push_prompt(
            name, backend=backend, version_tag=version_tag, metadata_info=metadata_info
        )
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
        result = push_prompt(
            name, backend=backend, version_tag=new_version, metadata_info=metadata_info
        )
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
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="실행 모드 (quick/full)")
    ] = "full",
    prefix: Annotated[
        Optional[str], typer.Option("--prefix", "-p", help="실험 이름 접두사")
    ] = None,
    version: Annotated[
        Optional[str], typer.Option("--version", "-v", help="프롬프트 버전 태그")
    ] = None,
    changes: Annotated[
        Optional[str],
        typer.Option("--changes", "-c", help="변경 내용 (프롬프트 변경 시)"),
    ] = None,
    no_push: Annotated[
        bool, typer.Option("--no-push", help="자동 push 비활성화")
    ] = False,
    backend: Annotated[
        str,
        typer.Option("--backend", "-b", help="실험 백엔드 (langsmith/langfuse/both)"),
    ] = "both",
):
    """평가 실험 실행 (LangSmith 또는 Langfuse).

    자동화 플로우:
    1. 메타데이터 없으면 자동 init
    2. 프롬프트 변경 감지 시 자동 버전 증가 + push (양쪽 플랫폼)
    3. 평가 실행
    4. Langfuse 결과는 로컬에 자동 저장

    --no-push 또는 --version 지정 시 버저닝 건너뜀.
    """
    from prompt_evaluator.context import get_context

    if mode not in ["quick", "full"]:
        typer.echo(f"Invalid mode: {mode}. Use quick/full")
        raise typer.Exit(1)

    if backend not in ["langsmith", "langfuse", "both"]:
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse/both")
        raise typer.Exit(1)

    ctx = get_context()
    prompt_dir = ctx.targets_dir / name
    if not prompt_dir.exists():
        typer.echo(f"프롬프트 폴더 없음: {prompt_dir}")
        raise typer.Exit(1)

    # 자동 버저닝 (--no-push, --version 미지정 시)
    if not no_push and not version:
        _auto_version_and_push(name, backend=backend, changes=changes)
        typer.echo("-" * 60)

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
    baseline_version: Annotated[
        Optional[str], typer.Option("--baseline", help="기준선 버전 (기본: latest)")
    ] = None,
    current_experiment: Annotated[
        Optional[str], typer.Option("--experiment", "-e", help="비교할 실험 이름")
    ] = None,
    threshold: Annotated[
        float, typer.Option("--threshold", "-t", help="회귀 임계값 (기본: 0.05 = 5%)")
    ] = 0.05,
    fail_on_regression: Annotated[
        bool, typer.Option("--fail", "-f", help="회귀 시 exit code 1 반환")
    ] = False,
    source: Annotated[
        str,
        typer.Option("--source", "-s", help="데이터 소스 (langsmith/langfuse/local)"),
    ] = "local",
):
    """회귀 테스트 실행.

    기준선과 현재 (또는 지정된 실험) 결과를 비교하여 성능 저하를 감지합니다.

    데이터 소스별 동작:

      [local] 기본값. 로컬 JSON 파일에서 baseline/실험 결과를 로드합니다.
        - baseline: results/baselines/{name}/ 에서 로드 (baseline set-local로 생성)
        - current: results/experiments/{name}/latest.json 에서 로드

      [langfuse] Langfuse API에서 직접 가져옵니다. 로컬 파일이 필요 없습니다.
        - 둘 다 미지정: 최신 2개 run을 자동 비교 (두번째 최신=baseline, 최신=current)
        - --baseline만 지정: 해당 run=baseline, 최신 run=current
        - --experiment만 지정: 최신 run=baseline, 해당 run=current
        - 둘 다 지정: 각각 해당 run 사용
        ※ run 이름은 Langfuse Experiments 탭에서 확인 가능

      [langsmith] LangSmith API에서 실험 결과를 가져옵니다.
        - baseline: 로컬 파일에서 로드
        - --experiment 필수

    Usage:
        # [local] 로컬 최신 실험과 기준선 비교
        regression --name prep_generate

        # [langfuse] 최신 2개 run 자동 비교 (로컬 파일 불필요)
        regression --name prep_generate --source langfuse

        # [langfuse] 특정 run 지정
        regression --name prep_generate --source langfuse --baseline "run-A" --experiment "run-B"

        # [langsmith] LangSmith 실험과 비교
        regression --name prep_generate --source langsmith --experiment "prep_generate-full-..."

        # CI/CD에서 사용 (회귀 시 exit code 1)
        regression --name prep_generate --source langfuse --fail
    """
    typer.echo(f"\n회귀 테스트: {name}")
    typer.echo("-" * 60)

    if source == "langfuse":
        # Langfuse 모드: baseline/current 모두 Langfuse API에서 가져옴
        from prompt_evaluator.regression.baseline import fetch_langfuse_experiment
        from prompt_evaluator.utils.langfuse_client import get_langfuse_client

        try:
            if baseline_version and current_experiment:
                # 둘 다 지정: 각각 가져옴
                baseline_data = fetch_langfuse_experiment(
                    name, run_name=baseline_version
                )
                current_data = fetch_langfuse_experiment(
                    name, run_name=current_experiment
                )
            elif not baseline_version and not current_experiment:
                # 둘 다 미지정: 최신 2개 run 비교
                langfuse = get_langfuse_client()
                all_runs = langfuse.get_dataset_runs(dataset_name=name)
                if not all_runs.data or len(all_runs.data) < 2:
                    typer.echo(
                        f"  Langfuse에 run이 2개 이상 필요합니다. "
                        f"(현재: {len(all_runs.data) if all_runs.data else 0}개)"
                    )
                    raise typer.Exit(1)
                sorted_runs = sorted(
                    all_runs.data, key=lambda r: r.created_at, reverse=True
                )
                baseline_data = fetch_langfuse_experiment(
                    name, run_name=sorted_runs[1].name
                )
                current_data = fetch_langfuse_experiment(
                    name, run_name=sorted_runs[0].name
                )
            else:
                # 하나만 지정
                if baseline_version:
                    baseline_data = fetch_langfuse_experiment(
                        name, run_name=baseline_version
                    )
                    current_data = fetch_langfuse_experiment(name)  # 최신 run
                else:
                    baseline_data = fetch_langfuse_experiment(
                        name
                    )  # 최신 run을 baseline
                    current_data = fetch_langfuse_experiment(
                        name, run_name=current_experiment
                    )
        except typer.Exit:
            raise
        except Exception as e:
            typer.echo(f"Langfuse 실험을 가져올 수 없습니다: {e}")
            raise typer.Exit(1)

        typer.echo(f"  기준선: {baseline_data.get('experiment_name')} (langfuse)")
        typer.echo(f"  비교 대상: {current_data.get('experiment_name')} (langfuse)")

        baseline = normalize_experiment_to_baseline(baseline_data)
        baseline["prompt_name"] = name
        current = normalize_experiment_to_baseline(current_data)

    else:
        # local/langsmith 모드: baseline은 로컬 파일에서 로드
        baseline = load_baseline(name, baseline_version)
        if baseline is None:
            typer.echo(
                f"기준선을 찾을 수 없습니다: {name} {baseline_version or 'latest'}"
            )
            typer.echo(
                "'baseline set' 또는 'baseline set-local' 명령으로 기준선을 먼저 설정하세요."
            )
            raise typer.Exit(1)

        typer.echo(
            f"  기준선: {baseline.get('version', 'unknown')} ({baseline.get('created_at', '')[:10]})"
        )

        if source == "local":
            experiment_data = load_latest_experiment(name)
            if experiment_data is None:
                typer.echo("  로컬 실험 결과를 찾을 수 없습니다.")
                typer.echo("  먼저 experiment 명령으로 실험을 실행하세요.")
                raise typer.Exit(1)

            typer.echo(
                f"  비교 대상: {experiment_data.get('experiment_name', 'latest')} (local)"
            )
            current = normalize_experiment_to_baseline(experiment_data)

        elif source == "langsmith":
            if not current_experiment:
                typer.echo(
                    "  --source langsmith 사용 시 --experiment 옵션이 필요합니다."
                )
                typer.echo(
                    "  예: regression --name prep_generate --source langsmith --experiment 'prep_generate-full-...'"
                )
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
                    },
                }
            except Exception as e:
                typer.echo(f"실험을 가져올 수 없습니다: {e}")
                raise typer.Exit(1)

        else:
            typer.echo(f"Invalid source: {source}. Use langsmith/langfuse/local")
            raise typer.Exit(1)

    report = compare_results(baseline, current, threshold)

    typer.echo()
    typer.echo(format_regression_report(report))

    if fail_on_regression and report.has_regression:
        raise typer.Exit(1)
