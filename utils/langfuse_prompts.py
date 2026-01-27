"""
Langfuse 프롬프트 관리 유틸리티

프롬프트 업로드, 조회, 버전 관리 기능 제공
"""

from pathlib import Path
from typing import Optional

from utils.langfuse_client import get_langfuse_client


def upload_prompt(
    name: str,
    content: str | list[dict],
    labels: Optional[list[str]] = None,
    config: Optional[dict] = None,
) -> None:
    """
    프롬프트를 Langfuse에 업로드

    Args:
        name: 프롬프트 이름 (고유 식별자)
        content: 프롬프트 내용 (str: text 타입, list[dict]: chat 타입)
        labels: 레이블 목록 (예: ["staging", "production"])
        config: 추가 설정 (model, temperature 등)
    """
    client = get_langfuse_client()

    # chat 형식인지 text 형식인지 판별
    if isinstance(content, list):
        # chat 형식: [{"role": "system", "content": "..."}, ...]
        client.create_prompt(
            name=name,
            type="chat",
            prompt=content,
            labels=labels or ["staging"],
            config=config or {},
        )
    else:
        # text 형식: 단일 문자열
        client.create_prompt(
            name=name,
            type="text",
            prompt=content,
            labels=labels or ["staging"],
            config=config or {},
        )


def get_prompt(name: str, label: Optional[str] = None, version: Optional[int] = None):
    """
    Langfuse에서 프롬프트 조회

    Args:
        name: 프롬프트 이름
        label: 레이블로 조회 (기본값: production)
        version: 특정 버전 조회

    Returns:
        프롬프트 객체 (compile() 메서드로 변수 치환 가능)
    """
    client = get_langfuse_client()
    return client.get_prompt(name, label=label, version=version)


def promote_to_production(name: str, version: int) -> None:
    """
    특정 버전을 production으로 승격

    Args:
        name: 프롬프트 이름
        version: 승격할 버전 번호
    """
    client = get_langfuse_client()
    # 해당 버전에 production 레이블 추가
    prompt = client.get_prompt(name, version=version)
    client.update_prompt(
        name=name,
        version=version,
        labels=list(set(prompt.labels or []) | {"production"}),
    )


def upload_from_file(
    name: str,
    file_path: str | Path,
    labels: Optional[list[str]] = None,
) -> None:
    """
    파일에서 프롬프트를 읽어 Langfuse에 업로드

    Args:
        name: 프롬프트 이름
        file_path: 프롬프트 파일 경로 (.txt, .py 등)
        labels: 레이블 목록
    """
    file_path = Path(file_path)

    if file_path.suffix == ".py":
        # Python 파일에서 PROMPT 변수 추출
        content = _extract_prompt_from_py(file_path)
    else:
        # 텍스트 파일 직접 읽기
        content = file_path.read_text(encoding="utf-8")

    upload_prompt(name=name, content=content, labels=labels)


def _extract_prompt_from_py(file_path: Path) -> str | list[dict]:
    """
    Python 파일에서 프롬프트 추출

    Returns:
        str: 단일 프롬프트인 경우
        list[dict]: SYSTEM_PROMPT + USER_PROMPT가 있는 경우 chat 메시지 배열
    """
    namespace = {}
    exec(file_path.read_text(encoding="utf-8"), namespace)

    # SYSTEM_PROMPT + USER_PROMPT 조합 확인 (chat 형식)
    if "SYSTEM_PROMPT" in namespace and "USER_PROMPT" in namespace:
        return [
            {"role": "system", "content": namespace["SYSTEM_PROMPT"]},
            {"role": "user", "content": namespace["USER_PROMPT"]},
        ]

    # 단일 프롬프트 변수 찾기
    for var_name in ["PROMPT", "prompt", "SYSTEM_PROMPT", "system_prompt"]:
        if var_name in namespace:
            return namespace[var_name]

    raise ValueError(f"No PROMPT variable found in {file_path}")


def upload_all_prompts(targets_dir: str | Path = "targets") -> dict[str, bool]:
    """
    targets 디렉토리의 모든 프롬프트를 Langfuse에 업로드

    Args:
        targets_dir: targets 디렉토리 경로

    Returns:
        {프롬프트명: 성공여부} 딕셔너리
    """
    targets_dir = Path(targets_dir)
    results = {}

    for prompt_dir in targets_dir.iterdir():
        if not prompt_dir.is_dir():
            continue

        # prompt.txt 또는 prompt.py 찾기
        prompt_file = None
        for suffix in [".txt", ".py", ".md", ".xml"]:
            candidate = prompt_dir / f"prompt{suffix}"
            if candidate.exists():
                prompt_file = candidate
                break

        if prompt_file is None:
            continue

        name = prompt_dir.name
        try:
            upload_from_file(name=name, file_path=prompt_file, labels=["staging"])
            results[name] = True
            print(f"✓ {name} 업로드 완료")
        except Exception as e:
            results[name] = False
            print(f"✗ {name} 업로드 실패: {e}")

    return results
