"""프롬프트 메타데이터 관리 모듈

targets/{name}/.metadata.yaml 파일을 통해 프롬프트 버전 이력을 관리합니다.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from src.loaders import find_prompt_file, load_prompt_file


METADATA_FILENAME = ".metadata.yaml"


def _get_metadata_path(prompt_name: str, targets_dir: Path = Path("targets")) -> Path:
    """메타데이터 파일 경로 반환"""
    return targets_dir / prompt_name / METADATA_FILENAME


def load_metadata(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> dict | None:
    """프롬프트 메타데이터 로드

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        메타데이터 dict 또는 None (파일 없음)
    """
    metadata_path = _get_metadata_path(prompt_name, targets_dir)

    if not metadata_path.exists():
        return None

    with open(metadata_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_metadata(
    prompt_name: str, metadata: dict, targets_dir: Path = Path("targets")
) -> Path:
    """프롬프트 메타데이터 저장

    Args:
        prompt_name: 프롬프트 이름
        metadata: 저장할 메타데이터
        targets_dir: targets 디렉토리 경로

    Returns:
        저장된 파일 경로
    """
    metadata_path = _get_metadata_path(prompt_name, targets_dir)

    # 폴더가 없으면 생성
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    with open(metadata_path, "w", encoding="utf-8") as f:
        yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return metadata_path


def init_metadata(
    prompt_name: str,
    owner: str,
    targets_dir: Path = Path("targets"),
) -> dict:
    """새 프롬프트의 메타데이터 초기화

    Args:
        prompt_name: 프롬프트 이름
        owner: 소유자 이메일
        targets_dir: targets 디렉토리 경로

    Returns:
        생성된 메타데이터
    """
    today = datetime.now().strftime("%Y-%m-%d")

    metadata = {
        "owner": owner,
        "created_at": today,
        "current_version": "v1.0",
        "versions": {
            "v1.0": {
                "date": today,
                "author": owner,
                "changes": "Initial version",
                "langsmith_hash": None,
                "langfuse_version": None,
            }
        },
    }

    save_metadata(prompt_name, metadata, targets_dir)
    return metadata


def add_version(
    prompt_name: str,
    version: str,
    author: str,
    changes: str,
    langsmith_hash: Optional[str] = None,
    langfuse_version: Optional[int] = None,
    targets_dir: Path = Path("targets"),
) -> dict:
    """새 버전 추가

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그 (예: v1.2)
        author: 작성자 이메일
        changes: 변경 내용 설명
        langsmith_hash: LangSmith 커밋 해시 (선택)
        langfuse_version: Langfuse 프롬프트 버전 번호 (선택)
        targets_dir: targets 디렉토리 경로

    Returns:
        업데이트된 메타데이터

    Raises:
        FileNotFoundError: 메타데이터 파일이 없는 경우
        ValueError: 이미 존재하는 버전인 경우
    """
    metadata = load_metadata(prompt_name, targets_dir)

    if metadata is None:
        raise FileNotFoundError(
            f"메타데이터 없음: {prompt_name}. "
            f"먼저 init_metadata()로 초기화하세요."
        )

    if version in metadata.get("versions", {}):
        raise ValueError(f"이미 존재하는 버전: {version}")

    today = datetime.now().strftime("%Y-%m-%d")

    if "versions" not in metadata:
        metadata["versions"] = {}

    metadata["versions"][version] = {
        "date": today,
        "author": author,
        "changes": changes,
        "langsmith_hash": langsmith_hash,
        "langfuse_version": langfuse_version,
    }
    metadata["current_version"] = version

    save_metadata(prompt_name, metadata, targets_dir)
    return metadata


def get_current_version(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> str | None:
    """현재 버전 조회

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        현재 버전 문자열 또는 None
    """
    metadata = load_metadata(prompt_name, targets_dir)

    if metadata is None:
        return None

    return metadata.get("current_version")


def get_version_history(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> list[dict]:
    """버전 이력 조회 (최신순)

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        버전 정보 리스트 [{version, date, author, changes, langsmith_hash}, ...]
    """
    metadata = load_metadata(prompt_name, targets_dir)

    if metadata is None or "versions" not in metadata:
        return []

    history = []
    for version, info in metadata["versions"].items():
        history.append({
            "version": version,
            "date": info.get("date"),
            "author": info.get("author"),
            "changes": info.get("changes"),
            "langsmith_hash": info.get("langsmith_hash"),
            "langfuse_version": info.get("langfuse_version"),
        })

    # 날짜 역순 정렬 (최신 먼저)
    history.sort(key=lambda x: x["date"] or "", reverse=True)
    return history


def update_langsmith_hash(
    prompt_name: str,
    version: str,
    langsmith_hash: str,
    targets_dir: Path = Path("targets"),
) -> dict:
    """특정 버전의 LangSmith 해시 업데이트

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그
        langsmith_hash: LangSmith 커밋 해시
        targets_dir: targets 디렉토리 경로

    Returns:
        업데이트된 메타데이터

    Raises:
        FileNotFoundError: 메타데이터 파일이 없는 경우
        ValueError: 존재하지 않는 버전인 경우
    """
    metadata = load_metadata(prompt_name, targets_dir)

    if metadata is None:
        raise FileNotFoundError(f"메타데이터 없음: {prompt_name}")

    if version not in metadata.get("versions", {}):
        raise ValueError(f"존재하지 않는 버전: {version}")

    metadata["versions"][version]["langsmith_hash"] = langsmith_hash
    save_metadata(prompt_name, metadata, targets_dir)
    return metadata


def update_langfuse_version(
    prompt_name: str,
    version: str,
    langfuse_version: int,
    targets_dir: Path = Path("targets"),
) -> dict:
    """특정 버전의 Langfuse 버전 번호 업데이트

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그
        langfuse_version: Langfuse 프롬프트 버전 번호
        targets_dir: targets 디렉토리 경로

    Returns:
        업데이트된 메타데이터

    Raises:
        FileNotFoundError: 메타데이터 파일이 없는 경우
        ValueError: 존재하지 않는 버전인 경우
    """
    metadata = load_metadata(prompt_name, targets_dir)

    if metadata is None:
        raise FileNotFoundError(f"메타데이터 없음: {prompt_name}")

    if version not in metadata.get("versions", {}):
        raise ValueError(f"존재하지 않는 버전: {version}")

    metadata["versions"][version]["langfuse_version"] = langfuse_version
    save_metadata(prompt_name, metadata, targets_dir)
    return metadata


def compute_prompt_hash(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> str:
    """프롬프트 파일의 해시 계산

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        프롬프트 내용의 SHA256 해시 (앞 16자리)
    """
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    prompts = load_prompt_file(prompt_file)

    # 프롬프트 내용을 정렬된 문자열로 변환하여 해시
    content = ""
    for key in sorted(prompts.keys()):
        content += f"{key}:{prompts[key]}"

    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_last_pushed_hash(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> str | None:
    """마지막 push 시점의 프롬프트 해시 조회

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        마지막 push된 프롬프트 해시 또는 None
    """
    metadata = load_metadata(prompt_name, targets_dir)
    if metadata is None:
        return None

    return metadata.get("last_pushed_hash")


def update_last_pushed_hash(
    prompt_name: str,
    prompt_hash: str,
    targets_dir: Path = Path("targets"),
) -> dict:
    """마지막 push 해시 업데이트

    Args:
        prompt_name: 프롬프트 이름
        prompt_hash: 프롬프트 해시
        targets_dir: targets 디렉토리 경로

    Returns:
        업데이트된 메타데이터
    """
    metadata = load_metadata(prompt_name, targets_dir)
    if metadata is None:
        raise FileNotFoundError(f"메타데이터 없음: {prompt_name}")

    metadata["last_pushed_hash"] = prompt_hash
    save_metadata(prompt_name, metadata, targets_dir)
    return metadata


def is_prompt_changed(
    prompt_name: str, targets_dir: Path = Path("targets")
) -> bool:
    """프롬프트가 마지막 push 이후 변경되었는지 확인

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: targets 디렉토리 경로

    Returns:
        변경 여부 (True: 변경됨, False: 변경 없음)
    """
    current_hash = compute_prompt_hash(prompt_name, targets_dir)
    last_hash = get_last_pushed_hash(prompt_name, targets_dir)

    if last_hash is None:
        return True  # 한 번도 push 안 됨 = 변경됨으로 취급

    return current_hash != last_hash


def increment_version(version: str) -> str:
    """버전 자동 증가 (v1.0 -> v1.1, v1.9 -> v1.10)

    Args:
        version: 현재 버전 (예: "v1.0", "v2.3")

    Returns:
        다음 버전 문자열
    """
    if not version.startswith("v"):
        return "v1.0"

    try:
        parts = version[1:].split(".")
        if len(parts) == 2:
            major, minor = int(parts[0]), int(parts[1])
            return f"v{major}.{minor + 1}"
        elif len(parts) == 1:
            major = int(parts[0])
            return f"v{major}.1"
    except ValueError:
        pass

    return "v1.0"


def ensure_metadata_exists(
    prompt_name: str,
    owner: str,
    targets_dir: Path = Path("targets"),
) -> dict:
    """메타데이터가 없으면 자동 초기화

    Args:
        prompt_name: 프롬프트 이름
        owner: 소유자 이메일
        targets_dir: targets 디렉토리 경로

    Returns:
        메타데이터 (기존 또는 새로 생성된)
    """
    metadata = load_metadata(prompt_name, targets_dir)
    if metadata is None:
        metadata = init_metadata(prompt_name, owner, targets_dir)
    return metadata


def auto_version_and_push_info(
    prompt_name: str,
    author: str,
    changes: str,
    targets_dir: Path = Path("targets"),
) -> dict:
    """자동 버전 증가 및 push 정보 생성

    변경이 있으면 새 버전을 추가하고, 없으면 현재 버전 정보 반환.

    Args:
        prompt_name: 프롬프트 이름
        author: 작성자 이메일
        changes: 변경 내용
        targets_dir: targets 디렉토리 경로

    Returns:
        {
            "version": str,
            "is_new_version": bool,
            "metadata": dict,
            "prompt_hash": str,
        }
    """
    metadata = load_metadata(prompt_name, targets_dir)
    if metadata is None:
        raise FileNotFoundError(f"메타데이터 없음: {prompt_name}")

    current_version = metadata.get("current_version", "v1.0")
    prompt_hash = compute_prompt_hash(prompt_name, targets_dir)
    is_changed = is_prompt_changed(prompt_name, targets_dir)

    if is_changed:
        # 새 버전 생성
        new_version = increment_version(current_version)
        metadata = add_version(
            prompt_name, new_version, author, changes, targets_dir=targets_dir
        )
        return {
            "version": new_version,
            "is_new_version": True,
            "metadata": metadata,
            "prompt_hash": prompt_hash,
        }
    else:
        # 변경 없음 - 현재 버전 유지
        return {
            "version": current_version,
            "is_new_version": False,
            "metadata": metadata,
            "prompt_hash": prompt_hash,
        }
