"""데이터셋 및 평가 세트 CLI 명령어"""

from typing import Annotated

import typer

from prompt_evaluator.loaders import list_evaluation_sets
from prompt_evaluator.utils.dataset_sync import upload_dataset


def list_sets():
    """사용 가능한 평가 세트 목록 출력."""
    from prompt_evaluator.context import get_context

    ctx = get_context()
    sets = list_evaluation_sets(
        targets_dir=ctx.targets_dir,
        datasets_dir=ctx.datasets_dir,
    )

    if not sets:
        typer.echo("사용 가능한 평가 세트가 없습니다.")
        typer.echo(
            f"{ctx.targets_dir}/{{name}}/config.yaml, {ctx.datasets_dir}/{{name}}/ 구조가 필요합니다."
        )
        return

    typer.echo("\n사용 가능한 평가 세트:")
    for s in sets:
        typer.echo(f"  - {s}")
    typer.echo()


def upload(
    name: Annotated[str, typer.Option("--name", "-n", help="평가 세트 이름")],
    backend: Annotated[
        str,
        typer.Option("--backend", "-b", help="업로드 대상 (langsmith/langfuse/both)"),
    ] = "both",
):
    """데이터셋을 LangSmith/Langfuse에 업로드."""
    if backend not in ("langsmith", "langfuse", "both"):
        typer.echo(f"Invalid backend: {backend}. Use langsmith/langfuse/both")
        raise typer.Exit(1)

    from prompt_evaluator.context import get_context

    ctx = get_context()
    typer.echo(f"\n데이터셋 업로드: {name} (backend: {backend})")
    result = upload_dataset(
        name,
        backend=backend,
        targets_dir=str(ctx.targets_dir),
        datasets_dir=str(ctx.datasets_dir),
    )

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


def profiles():
    """사용 가능한 Langfuse 프로필 목록 출력."""
    from prompt_evaluator.utils.trace_collector import list_profiles

    found = list_profiles()
    if not found:
        typer.echo("Langfuse 프로필이 없습니다.")
        typer.echo("  .env에 LANGFUSE_{NAME}_PUBLIC_KEY / SECRET_KEY를 추가하세요.")
        return

    typer.echo(f"\nLangfuse 프로필 ({len(found)}개):")
    for p in found:
        typer.echo(f"  - {p}")
    typer.echo()


def collect(
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="데이터셋 이름 (미지정 시 프로필명 사용)"),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="수집할 트레이스 최대 개수")
    ] = 10,
    since: Annotated[
        str | None,
        typer.Option("--since", help="시작 날짜 (예: 2026-01-25)"),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="종료 날짜 (예: 2026-02-01)"),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "-t", help="필터링할 태그 (여러 개 가능)"),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option("--session", help="세션 ID 필터"),
    ] = None,
    trace_name: Annotated[
        str | None,
        typer.Option("--trace-name", help="트레이스 이름 필터"),
    ] = None,
    user_id: Annotated[
        str | None,
        typer.Option("--user-id", help="사용자 ID 필터"),
    ] = None,
    input_key: Annotated[
        str | None,
        typer.Option("--input-key", help="이 키가 input에 있는 트레이스만 수집"),
    ] = None,
    input_contains: Annotated[
        str | None,
        typer.Option(
            "--input-contains", help="input에 이 문자열이 포함된 트레이스만 수집"
        ),
    ] = None,
    classify: Annotated[
        bool,
        typer.Option(
            "--classify", "-c", help="input/output 자동 분리 (LangGraph state 패턴)"
        ),
    ] = False,
    input_fields_str: Annotated[
        str | None,
        typer.Option("--input-fields", help="명시적 input 필드 (쉼표 구분)"),
    ] = None,
    output_fields_str: Annotated[
        str | None,
        typer.Option("--output-fields", help="명시적 output 필드 (쉼표 구분)"),
    ] = None,
    append: Annotated[
        bool,
        typer.Option("--append", help="기존 데이터셋에 추가"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="저장하지 않고 미리보기만"),
    ] = False,
    key_map_str: Annotated[
        str | None,
        typer.Option(
            "--key-map", help="입력 키 매핑 (예: prod_key:prompt_var,key2:var2)"
        ),
    ] = None,
    prompt_file: Annotated[
        str | None,
        typer.Option("--prompt-file", help="프롬프트 파일 경로 (자동 키 매핑에 사용)"),
    ] = None,
    langfuse_profile: Annotated[
        str | None,
        typer.Option(
            "--langfuse-profile",
            "-p",
            help="Langfuse 프로필명 (.env의 LANGFUSE_{NAME}_* 키)",
        ),
    ] = None,
):
    """Langfuse 트레이스에서 데이터셋을 수집."""
    import json as json_mod

    from prompt_evaluator.context import get_context
    from prompt_evaluator.utils.trace_collector import collect_traces

    ctx = get_context()

    # key-map 파싱
    key_map = None
    if key_map_str:
        key_map = {}
        for pair in key_map_str.split(","):
            parts = pair.strip().split(":")
            if len(parts) == 2:
                key_map[parts[0].strip()] = parts[1].strip()
            else:
                typer.echo(f"키 매핑 형식 오류: '{pair}' (예: prod_key:prompt_var)")
                raise typer.Exit(1)

    # 필드 목록 파싱
    input_fields = (
        [f.strip() for f in input_fields_str.split(",")] if input_fields_str else None
    )
    output_fields = (
        [f.strip() for f in output_fields_str.split(",")] if output_fields_str else None
    )

    # name 미지정 시 프로필명 사용
    if not name:
        if not langfuse_profile:
            typer.echo("✗ --name 또는 --langfuse-profile(-p)을 지정하세요.")
            raise typer.Exit(1)
        name = langfuse_profile.lower()

    # 헤더 출력
    typer.echo(f"\nLangfuse 트레이스 수집: {name}")
    if langfuse_profile:
        typer.echo(f"  프로필: {langfuse_profile}")
    if classify:
        typer.echo("  모드: input/output 자동 분리")
    if since:
        typer.echo(f"  시작: {since}")
    if until:
        typer.echo(f"  종료: {until}")
    typer.echo(f"  최대: {limit}개")
    if dry_run:
        typer.echo("  [DRY RUN] 저장하지 않습니다")
    typer.echo()

    try:
        result = collect_traces(
            name=name,
            datasets_dir=str(ctx.datasets_dir),
            limit=limit,
            since=since,
            until=until,
            tags=tags,
            session_id=session_id,
            user_id=user_id,
            trace_name=trace_name,
            input_key=input_key,
            input_contains=input_contains,
            classify=classify,
            input_fields=input_fields,
            output_fields=output_fields,
            append=append,
            dry_run=dry_run,
            key_map=key_map,
            prompt_file=prompt_file,
            langfuse_profile=langfuse_profile,
        )
    except Exception as e:
        typer.echo(f"✗ 트레이스 수집 실패: {e}")
        raise typer.Exit(1)

    typer.echo(f"수집된 트레이스: {result['collected']}개")
    typer.echo(f"새 테스트 케이스: {result['new']}개")
    if result.get("filtered_out", 0) > 0:
        typer.echo(f"필터링 제외: {result['filtered_out']}개")
    if result["skipped_duplicates"] > 0:
        typer.echo(f"중복 건너뜀: {result['skipped_duplicates']}개")

    if dry_run and result["test_cases"]:
        typer.echo("\n--- 미리보기 (첫 3개) ---")
        for case in result["test_cases"][:3]:
            typer.echo(f"\n  [{case['id']}]")
            typer.echo(f"    inputs: {list(case['inputs'].keys())}")
            stub = result["expected_stubs"].get(case["id"], {})
            ref = stub.get("_reference_output", "")
            try:
                typer.echo(f"    outputs: {list(json_mod.loads(ref).keys())}")
            except (json_mod.JSONDecodeError, TypeError):
                if ref:
                    typer.echo(f"    output: {ref[:100]}...")
    elif not dry_run and result["new"] > 0:
        data_dir = ctx.datasets_dir / name
        typer.echo("\n저장 위치:")
        typer.echo(f"  {data_dir / 'test_cases.json'}")
        typer.echo(f"  {data_dir / 'expected.json'}")
        typer.echo("\n다음 단계: expected.json을 큐레이션한 후 업로드하세요")
        typer.echo(f"  prompt-eval upload --name {name}")

    typer.echo()
