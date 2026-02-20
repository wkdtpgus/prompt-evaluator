"""트레이스 데이터 수집 모듈

Langfuse 프로덕션 트레이스에서 데이터를 수집하여
test_cases.json / expected.json 형식으로 변환합니다.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def _resolve_langfuse_client(profile: Optional[str] = None):
    """Langfuse 클라이언트를 프로필 설정에 따라 반환

    프로필 미지정 시 기본 클라이언트(.env의 LANGFUSE_* 키) 사용.
    프로필 지정 시 .env의 LANGFUSE_PROFILE_{NAME}_* 환경변수에서 키를 읽어 별도 클라이언트 생성.

    .env 예시:
        # 기본
        LANGFUSE_PUBLIC_KEY=pk-lf-xxx
        LANGFUSE_SECRET_KEY=sk-lf-xxx

        # 프로필: prod-app → LANGFUSE_PROFILE_PROD_APP_*
        LANGFUSE_PROFILE_PROD_APP_PUBLIC_KEY=pk-lf-yyy
        LANGFUSE_PROFILE_PROD_APP_SECRET_KEY=sk-lf-yyy
        LANGFUSE_PROFILE_PROD_APP_HOST=https://cloud.langfuse.com
    """
    if not profile:
        from prompt_evaluator.utils.langfuse_client import get_langfuse_client

        return get_langfuse_client()

    import os

    from langfuse import Langfuse

    # 프로필명 → 환경변수 prefix (하이픈 → 언더바, 대문자)
    env_prefix = f"LANGFUSE_{profile.upper().replace('-', '_')}_"

    public_key = os.environ.get(f"{env_prefix}PUBLIC_KEY")
    secret_key = os.environ.get(f"{env_prefix}SECRET_KEY")

    if not public_key or not secret_key:
        raise ValueError(
            f"Langfuse 프로필 '{profile}'의 환경변수를 찾을 수 없습니다.\n"
            f".env에 다음을 추가하세요:\n"
            f"  {env_prefix}PUBLIC_KEY=pk-lf-...\n"
            f"  {env_prefix}SECRET_KEY=sk-lf-..."
        )

    kwargs = {"public_key": public_key, "secret_key": secret_key}
    host = os.environ.get(f"{env_prefix}HOST")
    if host:
        kwargs["host"] = host

    return Langfuse(**kwargs)


def collect_traces(
    name: str,
    datasets_dir: str | Path,
    limit: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tags: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    trace_name: Optional[str] = None,
    input_key: Optional[str] = None,
    input_contains: Optional[str] = None,
    append: bool = False,
    dry_run: bool = False,
    key_map: Optional[dict[str, str]] = None,
    prompt_file: Optional[str] = None,
    langfuse_profile: Optional[str] = None,
) -> dict:
    """Langfuse 트레이스에서 데이터를 수집하여 로컬 데이터셋으로 변환

    Args:
        name: 데이터셋 이름 (datasets/{name}/ 에 저장)
        datasets_dir: datasets 루트 디렉토리
        limit: 수집할 트레이스 최대 개수
        since: 시작 날짜 (ISO 형식, 예: 2026-01-25)
        until: 종료 날짜 (ISO 형식)
        tags: 필터링할 태그 목록
        session_id: 세션 ID 필터
        user_id: 사용자 ID 필터
        trace_name: 트레이스 이름 필터
        input_key: 이 키가 input에 존재하는 트레이스만 수집
        input_contains: input에 이 문자열이 포함된 트레이스만 수집
        append: True면 기존 데이터셋에 추가, False면 덮어쓰기
        dry_run: True면 저장하지 않고 미리보기만
        key_map: input 키 매핑 (프로덕션 키 → 프롬프트 변수)
        prompt_file: 프롬프트 파일 경로 (자동 키 매핑에 사용)
        langfuse_profile: Langfuse 프로필명 (config.yaml의 langfuse_profiles 키)

    Returns:
        {
            "collected": int,
            "new": int,
            "skipped_duplicates": int,
            "filtered_out": int,
            "test_cases": list[dict],
            "expected_stubs": dict,
        }
    """
    langfuse = _resolve_langfuse_client(langfuse_profile)
    datasets_dir = Path(datasets_dir)
    data_dir = datasets_dir / name

    # 기존 데이터 로드 (append 모드 또는 중복 제거용)
    existing_cases, existing_expected = _load_existing(data_dir) if append else ([], {})
    existing_input_hashes = {_hash_inputs(c["inputs"]) for c in existing_cases}

    # Langfuse API 호출 파라미터 구성
    list_kwargs: dict = {"limit": limit}

    if since:
        list_kwargs["from_timestamp"] = _parse_date(since)
    if until:
        list_kwargs["to_timestamp"] = _parse_date(until)
    if tags:
        list_kwargs["tags"] = tags
    if session_id:
        list_kwargs["session_id"] = session_id
    if user_id:
        list_kwargs["user_id"] = user_id
    if trace_name:
        list_kwargs["name"] = trace_name

    # 클라이언트 필터가 있으면 더 많이 가져와서 필터링
    has_client_filter = bool(input_key or input_contains)
    if has_client_filter:
        list_kwargs["limit"] = min(limit * 3, 100)

    # 트레이스 목록 조회
    traces_response = langfuse.api.trace.list(**list_kwargs)
    traces = traces_response.data

    # 클라이언트 사이드 필터링
    filtered_out = 0
    if has_client_filter:
        filtered = []
        for t in traces:
            t_input = t.input if t.input else {}
            if not isinstance(t_input, dict):
                filtered_out += 1
                continue
            if input_key and input_key not in t_input:
                filtered_out += 1
                continue
            if input_contains:
                input_str = json.dumps(t_input, ensure_ascii=False)
                if input_contains not in input_str:
                    filtered_out += 1
                    continue
            filtered.append(t)
        traces = filtered[:limit]

    # 자동 키 매핑 준비
    auto_key_map = key_map
    if not auto_key_map and prompt_file:
        placeholders = _extract_placeholders(prompt_file)
        if placeholders and traces:
            auto_key_map = _auto_map_keys(traces[0], placeholders)

    # 변환
    new_cases = []
    expected_stubs = {}
    skipped = 0

    for i, trace in enumerate(traces):
        trace_input = trace.input if trace.input else {}
        if not isinstance(trace_input, dict):
            trace_input = {"input": trace_input}

        # 키 매핑 적용
        mapped_input = (
            _apply_key_map(trace_input, auto_key_map) if auto_key_map else trace_input
        )

        # 중복 확인
        input_hash = _hash_inputs(mapped_input)
        if input_hash in existing_input_hashes:
            skipped += 1
            continue
        existing_input_hashes.add(input_hash)

        # case ID 생성
        case_id = f"trace_{i + 1:04d}_{trace.id[:8]}"

        case = {
            "id": case_id,
            "description": f"Collected from Langfuse trace {trace.id}",
            "inputs": mapped_input,
        }
        new_cases.append(case)

        # expected 스텁 생성 (output이 있으면 참고용으로 포함)
        stub: dict = {
            "keywords": [],
            "forbidden": [],
            "notes": "TODO: 수동 큐레이션 필요",
        }
        if trace.output:
            output_text = (
                trace.output
                if isinstance(trace.output, str)
                else json.dumps(trace.output, ensure_ascii=False)
            )
            stub["_reference_output"] = output_text[:500]
        expected_stubs[case_id] = stub

    result = {
        "collected": len(traces),
        "new": len(new_cases),
        "skipped_duplicates": skipped,
        "filtered_out": filtered_out if has_client_filter else 0,
        "test_cases": new_cases,
        "expected_stubs": expected_stubs,
    }

    if dry_run:
        return result

    # 저장
    _save_dataset(
        data_dir, new_cases, expected_stubs, existing_cases, existing_expected, append
    )

    return result


def _load_existing(data_dir: Path) -> tuple[list[dict], dict]:
    """기존 데이터셋 로드"""
    cases = []
    expected = {}

    test_cases_path = data_dir / "test_cases.json"
    expected_path = data_dir / "expected.json"

    if test_cases_path.exists():
        with open(test_cases_path, encoding="utf-8") as f:
            cases = json.load(f)

    if expected_path.exists():
        with open(expected_path, encoding="utf-8") as f:
            expected = json.load(f)

    return cases, expected


def _save_dataset(
    data_dir: Path,
    new_cases: list[dict],
    expected_stubs: dict,
    existing_cases: list[dict],
    existing_expected: dict,
    append: bool,
) -> None:
    """데이터셋을 로컬 파일로 저장"""
    data_dir.mkdir(parents=True, exist_ok=True)

    if append:
        all_cases = existing_cases + new_cases
        all_expected = {**existing_expected, **expected_stubs}
    else:
        all_cases = new_cases
        all_expected = expected_stubs

    with open(data_dir / "test_cases.json", "w", encoding="utf-8") as f:
        json.dump(all_cases, f, ensure_ascii=False, indent=2)

    with open(data_dir / "expected.json", "w", encoding="utf-8") as f:
        json.dump(all_expected, f, ensure_ascii=False, indent=2)


def _hash_inputs(inputs: dict) -> str:
    """inputs dict를 해시하여 중복 비교에 사용"""
    return json.dumps(inputs, sort_keys=True, ensure_ascii=False)


def _parse_date(date_str: str) -> datetime:
    """날짜 문자열을 datetime으로 파싱"""
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise ValueError(f"날짜 형식을 파싱할 수 없습니다: {date_str} (예: 2026-01-25)")


def _extract_placeholders(prompt_file: str) -> list[str]:
    """프롬프트 파일에서 placeholder 변수명 추출

    {variable_name} 패턴을 찾아 반환합니다.
    """
    path = Path(prompt_file)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    # {var} 패턴 추출 (중첩 브레이스 제외)
    placeholders = re.findall(r"\{(\w+)\}", content)
    # 중복 제거하면서 순서 유지
    seen = set()
    unique = []
    for p in placeholders:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _auto_map_keys(trace, placeholders: list[str]) -> dict[str, str] | None:
    """트레이스의 input 키와 프롬프트 placeholder를 자동 매핑

    정확히 일치하는 키, 소문자 비교, 부분 일치 순으로 시도합니다.

    Returns:
        {프로덕션_키: 프롬프트_변수} 매핑 dict, 매핑 불가능하면 None
    """
    trace_input = trace.input if trace.input else {}
    if not isinstance(trace_input, dict):
        return None

    trace_keys = list(trace_input.keys())
    if not trace_keys:
        return None

    mapping = {}
    unmapped_placeholders = list(placeholders)

    # 1차: 정확히 일치
    for tk in trace_keys:
        if tk in unmapped_placeholders:
            mapping[tk] = tk
            unmapped_placeholders.remove(tk)

    # 2차: 소문자 비교
    for tk in trace_keys:
        if tk in mapping:
            continue
        for ph in unmapped_placeholders:
            if tk.lower() == ph.lower():
                mapping[tk] = ph
                unmapped_placeholders.remove(ph)
                break

    # 3차: 부분 일치 (한쪽이 다른 쪽에 포함)
    for tk in trace_keys:
        if tk in mapping:
            continue
        for ph in unmapped_placeholders:
            if tk.lower() in ph.lower() or ph.lower() in tk.lower():
                mapping[tk] = ph
                unmapped_placeholders.remove(ph)
                break

    # 매핑이 하나도 안 되면 None
    if not mapping:
        return None

    return mapping


def _apply_key_map(inputs: dict, key_map: dict[str, str]) -> dict:
    """input 키를 매핑에 따라 변환"""
    mapped = {}
    for key, value in inputs.items():
        new_key = key_map.get(key, key)
        mapped[new_key] = value
    return mapped
