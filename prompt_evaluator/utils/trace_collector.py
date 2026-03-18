"""트레이스 데이터 수집 모듈

Langfuse 프로덕션 트레이스에서 데이터를 수집하여
test_cases.json / expected.json 형식으로 변환합니다.

사용법:
    # 기본 (input 전체를 테스트 입력으로 사용)
    collect_traces("my_dataset", datasets_dir, langfuse_profile="PREP_OUTPUT")

    # 자동 분류 (LangGraph state 패턴 감지로 input/output 분리)
    collect_traces("my_dataset", datasets_dir, langfuse_profile="PREP_OUTPUT", classify=True)

    # 명시적 필드 지정
    collect_traces("my_dataset", datasets_dir, langfuse_profile="PREP_OUTPUT",
                   classify=True, input_fields=["chat_history", "member_name"],
                   output_fields=["recommended_questions"])
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# 자동 분류 시 항상 제외할 메타 필드
_META_FIELDS = frozenset({"status", "errors", "shared_cache_name", "language"})


# ── 설정 데이터 클래스 ──────────────────────────────────────────────


@dataclass
class TraceFilter:
    """Langfuse 트레이스 필터 조건"""

    since: str | None = None
    until: str | None = None
    tags: list[str] | None = None
    session_id: str | None = None
    user_id: str | None = None
    trace_name: str | None = None
    input_key: str | None = None
    input_contains: str | None = None

    def to_api_kwargs(self, limit: int) -> dict:
        """Langfuse API 호출 파라미터로 변환"""
        kwargs: dict = {"limit": limit}
        if self.since:
            kwargs["from_timestamp"] = _parse_date(self.since)
        if self.until:
            kwargs["to_timestamp"] = _parse_date(self.until)
        if self.tags:
            kwargs["tags"] = self.tags
        if self.session_id:
            kwargs["session_id"] = self.session_id
        if self.user_id:
            kwargs["user_id"] = self.user_id
        if self.trace_name:
            kwargs["name"] = self.trace_name
        return kwargs

    @property
    def has_client_filter(self) -> bool:
        return bool(self.input_key or self.input_contains)


@dataclass
class ClassifyOptions:
    """input/output 자동 분류 옵션"""

    enabled: bool = False
    input_fields: list[str] | None = None
    output_fields: list[str] | None = None
    exclude_fields: list[str] | None = None


# ── Langfuse 클라이언트 ─────────────────────────────────────────────


def _resolve_langfuse_client(profile: Optional[str] = None):
    """Langfuse 클라이언트를 프로필 설정에 따라 반환

    프로필 미지정 → 기본 환경변수 (LANGFUSE_PUBLIC_KEY 등) 사용
    프로필 지정 → LANGFUSE_{PROFILE}_PUBLIC_KEY 등에서 읽음

    .env 예시:
        LANGFUSE_PUBLIC_KEY=pk-lf-xxx              # 기본
        LANGFUSE_PREP_OUTPUT_PUBLIC_KEY=pk-lf-yyy   # 프로필: PREP_OUTPUT
        LANGFUSE_PREP_OUTPUT_SECRET_KEY=sk-lf-yyy
    """
    if not profile:
        from prompt_evaluator.utils.langfuse_client import get_langfuse_client

        return get_langfuse_client()

    import os

    from langfuse import Langfuse

    env_prefix = f"LANGFUSE_{profile.upper().replace('-', '_')}_"
    public_key = os.environ.get(f"{env_prefix}PUBLIC_KEY")
    secret_key = os.environ.get(f"{env_prefix}SECRET_KEY")

    if not public_key or not secret_key:
        raise ValueError(
            f"프로필 '{profile}' 환경변수를 찾을 수 없습니다.\n"
            f".env에 추가하세요:\n"
            f"  {env_prefix}PUBLIC_KEY=pk-lf-...\n"
            f"  {env_prefix}SECRET_KEY=sk-lf-..."
        )

    kwargs = {"public_key": public_key, "secret_key": secret_key}
    host = os.environ.get(f"{env_prefix}HOST") or os.environ.get("LANGFUSE_BASE_URL")
    if host:
        kwargs["host"] = host

    return Langfuse(**kwargs)


def list_profiles() -> list[str]:
    """사용 가능한 Langfuse 프로필 목록 반환"""
    import os

    profiles = set()
    for k in os.environ:
        if (
            k.startswith("LANGFUSE_")
            and k.endswith("_PUBLIC_KEY")
            and k != "LANGFUSE_PUBLIC_KEY"
        ):
            name = k.removeprefix("LANGFUSE_").removesuffix("_PUBLIC_KEY")
            profiles.add(name)
    return sorted(profiles)


# ── 메인 수집 함수 ──────────────────────────────────────────────────


def collect_traces(
    name: str,
    datasets_dir: str | Path,
    limit: int = 10,
    langfuse_profile: Optional[str] = None,
    trace_filter: Optional[TraceFilter] = None,
    classify: bool = False,
    classify_options: Optional[ClassifyOptions] = None,
    append: bool = False,
    dry_run: bool = False,
    key_map: Optional[dict[str, str]] = None,
    prompt_file: Optional[str] = None,
    # 하위호환: 개별 필터 파라미터도 여전히 동작
    since: Optional[str] = None,
    until: Optional[str] = None,
    tags: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    trace_name: Optional[str] = None,
    input_key: Optional[str] = None,
    input_contains: Optional[str] = None,
    input_fields: Optional[list[str]] = None,
    output_fields: Optional[list[str]] = None,
    exclude_fields: Optional[list[str]] = None,
) -> dict:
    """Langfuse 트레이스에서 데이터를 수집하여 로컬 데이터셋으로 변환

    Args:
        name: 데이터셋 이름 (datasets/{name}/ 에 저장)
        datasets_dir: datasets 루트 디렉토리
        limit: 수집할 트레이스 최대 개수
        langfuse_profile: Langfuse 프로필명 (.env의 LANGFUSE_{NAME}_* 키)
        trace_filter: 트레이스 필터 조건 (TraceFilter 객체)
        classify: input/output 자동 분리 활성화
        classify_options: 분류 세부 옵션 (ClassifyOptions 객체)
        append: 기존 데이터셋에 추가
        dry_run: 저장하지 않고 미리보기만
        key_map: input 키 매핑 (프로덕션 키 → 프롬프트 변수)
        prompt_file: 프롬프트 파일 경로 (자동 키 매핑에 사용)

    Returns:
        {"collected", "new", "skipped_duplicates", "filtered_out",
         "test_cases", "expected_stubs"}
    """
    # 하위호환: 개별 파라미터 → TraceFilter/ClassifyOptions 변환
    if trace_filter is None:
        trace_filter = TraceFilter(
            since=since,
            until=until,
            tags=tags,
            session_id=session_id,
            user_id=user_id,
            trace_name=trace_name,
            input_key=input_key,
            input_contains=input_contains,
        )
    if classify_options is None and classify:
        classify_options = ClassifyOptions(
            enabled=True,
            input_fields=input_fields,
            output_fields=output_fields,
            exclude_fields=exclude_fields,
        )
    elif classify:
        classify_options.enabled = True

    langfuse = _resolve_langfuse_client(langfuse_profile)
    datasets_dir = Path(datasets_dir)
    data_dir = datasets_dir / name

    # 기존 데이터 로드
    existing_cases, existing_expected = _load_existing(data_dir) if append else ([], {})
    existing_hashes = {_hash_inputs(c["inputs"]) for c in existing_cases}

    # Langfuse API 조회
    fetch_limit = min(limit * 3, 100) if trace_filter.has_client_filter else limit
    traces = langfuse.api.trace.list(**trace_filter.to_api_kwargs(fetch_limit)).data

    # 클라이언트 사이드 필터링
    traces, filtered_out = _apply_client_filter(traces, trace_filter, limit)

    # 자동 키 매핑
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
        raw_input = _safe_dict(trace.input)
        raw_output = _safe_dict(trace.output)

        # input/output 분리
        if classify_options and classify_options.enabled:
            inputs, outputs = classify_fields(
                raw_input,
                raw_output,
                input_fields=classify_options.input_fields,
                output_fields=classify_options.output_fields,
                exclude_fields=classify_options.exclude_fields,
            )
        else:
            inputs = raw_input
            outputs = {}

        # 키 매핑
        if auto_key_map:
            inputs = _apply_key_map(inputs, auto_key_map)

        # 중복 확인
        h = _hash_inputs(inputs)
        if h in existing_hashes:
            skipped += 1
            continue
        existing_hashes.add(h)

        case_id = f"trace_{i + 1:04d}_{trace.id[:8]}"
        new_cases.append(
            {
                "id": case_id,
                "description": f"Langfuse trace {trace.id}",
                "inputs": inputs,
            }
        )
        expected_stubs[case_id] = _make_expected_stub(
            outputs,
            trace.output,
            classify=(classify_options and classify_options.enabled),
        )

    result = {
        "collected": len(traces),
        "new": len(new_cases),
        "skipped_duplicates": skipped,
        "filtered_out": filtered_out,
        "test_cases": new_cases,
        "expected_stubs": expected_stubs,
    }

    if not dry_run:
        _save_dataset(
            data_dir,
            new_cases,
            expected_stubs,
            existing_cases,
            existing_expected,
            append,
        )

    return result


# ── 필드 분류 (public) ──────────────────────────────────────────────


def classify_fields(
    trace_input: dict,
    trace_output: dict,
    input_fields: list[str] | None = None,
    output_fields: list[str] | None = None,
    exclude_fields: list[str] | None = None,
) -> tuple[dict, dict]:
    """trace의 input/output에서 테스트용 inputs와 AI 생성 output을 분리

    LangGraph state 패턴 자동 감지:
    - input에서 빈값 → output에서 채워진 필드 = AI 생성물
    - input/output 값이 동일한 필드 = 컨텍스트 (테스트 input)
    - 메타 필드(status, errors 등)는 자동 제외

    명시적으로 input_fields/output_fields를 지정하면 자동 감지를 건너뜁니다.
    """
    exclude = _META_FIELDS | set(exclude_fields or [])

    # 명시적 필드 지정 모드
    if input_fields or output_fields:
        inputs = {k: trace_input[k] for k in (input_fields or []) if k in trace_input}
        src = trace_output or trace_input
        outputs = {k: src[k] for k in (output_fields or []) if k in src}
        return inputs, outputs

    # output이 없으면 input 전체를 반환
    if not trace_output or not isinstance(trace_output, dict):
        return {k: v for k, v in trace_input.items() if k not in exclude}, {}

    inputs = {}
    outputs = {}

    for key in set(trace_input) | set(trace_output):
        if key in exclude:
            continue

        in_val = trace_input.get(key)
        out_val = trace_output.get(key)

        # output에만 존재 → AI 생성
        if key not in trace_input:
            if not _is_empty(out_val):
                outputs[key] = out_val
        # input이 빈값, output이 채워짐 → AI 생성
        elif _is_empty(in_val) and not _is_empty(out_val):
            outputs[key] = out_val
        # 값 동일 → input (컨텍스트)
        elif in_val == out_val:
            if not _is_empty(in_val):
                inputs[key] = in_val
        # 둘 다 있는데 변경됨 → 양쪽 포함
        elif not _is_empty(in_val) and not _is_empty(out_val):
            inputs[key] = in_val
            outputs[key] = out_val
        # input에만 값 있음
        elif not _is_empty(in_val):
            inputs[key] = in_val

    return inputs, outputs


# ── 내부 헬퍼 ───────────────────────────────────────────────────────


def _safe_dict(val) -> dict:
    """값을 안전하게 dict로 변환"""
    if isinstance(val, dict):
        return val
    if val is not None:
        return {"_raw": val}
    return {}


def _is_empty(value) -> bool:
    """값이 비어있는지 판별

    None, 빈 문자열, 빈 컬렉션, 모든 값이 빈 dict도 비어있음으로 판별합니다.
    """
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    # {"key": "", "key2": ""} 같은 모든 값이 빈 dict도 비어있음으로 처리
    if isinstance(value, dict) and all(_is_empty(v) for v in value.values()):
        return True
    return False


def _apply_client_filter(traces, trace_filter: TraceFilter, limit: int):
    """클라이언트 사이드 필터링"""
    if not trace_filter.has_client_filter:
        return traces, 0

    filtered_out = 0
    result = []
    for t in traces:
        t_input = t.input if isinstance(t.input, dict) else {}
        if trace_filter.input_key and trace_filter.input_key not in t_input:
            filtered_out += 1
            continue
        if trace_filter.input_contains:
            if trace_filter.input_contains not in json.dumps(
                t_input, ensure_ascii=False
            ):
                filtered_out += 1
                continue
        result.append(t)
    return result[:limit], filtered_out


def _make_expected_stub(classified_outputs: dict, raw_output, classify: bool) -> dict:
    """expected.json 스텁 하나 생성"""
    stub: dict = {"keywords": [], "forbidden": []}
    if classify and classified_outputs:
        stub["_reference_output"] = json.dumps(classified_outputs, ensure_ascii=False)[
            :2000
        ]
        stub["notes"] = "classify로 자동 분리된 AI 생성 output"
    elif raw_output:
        text = (
            raw_output
            if isinstance(raw_output, str)
            else json.dumps(raw_output, ensure_ascii=False)
        )
        stub["_reference_output"] = text[:500]
        stub["notes"] = "TODO: 수동 큐레이션 필요"
    return stub


def _load_existing(data_dir: Path) -> tuple[list[dict], dict]:
    """기존 데이터셋 로드"""
    cases_path = data_dir / "test_cases.json"
    expected_path = data_dir / "expected.json"
    cases = json.loads(cases_path.read_text("utf-8")) if cases_path.exists() else []
    expected = (
        json.loads(expected_path.read_text("utf-8")) if expected_path.exists() else {}
    )
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
    all_cases = (existing_cases + new_cases) if append else new_cases
    all_expected = (
        ({**existing_expected, **expected_stubs}) if append else expected_stubs
    )

    (data_dir / "test_cases.json").write_text(
        json.dumps(all_cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (data_dir / "expected.json").write_text(
        json.dumps(all_expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _hash_inputs(inputs: dict) -> str:
    raw = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise ValueError(f"날짜 파싱 실패: {date_str} (예: 2026-01-25)")


def _extract_placeholders(prompt_file: str) -> list[str]:
    """프롬프트 파일에서 {variable_name} 패턴 추출"""
    path = Path(prompt_file)
    if not path.exists():
        return []
    return list(dict.fromkeys(re.findall(r"\{(\w+)\}", path.read_text("utf-8"))))


def _auto_map_keys(trace, placeholders: list[str]) -> dict[str, str] | None:
    """트레이스 input 키와 프롬프트 placeholder 자동 매핑 (정확 → 소문자 → 부분 일치)"""
    trace_input = trace.input if isinstance(trace.input, dict) else {}
    if not trace_input:
        return None

    trace_keys = list(trace_input.keys())
    mapping = {}
    remaining = list(placeholders)

    for match_fn in [
        lambda tk, ph: tk == ph,
        lambda tk, ph: tk.lower() == ph.lower(),
        lambda tk, ph: tk.lower() in ph.lower() or ph.lower() in tk.lower(),
    ]:
        for tk in trace_keys:
            if tk in mapping:
                continue
            for ph in remaining:
                if match_fn(tk, ph):
                    mapping[tk] = ph
                    remaining.remove(ph)
                    break

    return mapping or None


def _apply_key_map(inputs: dict, key_map: dict[str, str]) -> dict:
    return {key_map.get(k, k): v for k, v in inputs.items()}
