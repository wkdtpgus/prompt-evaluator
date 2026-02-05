"""프롬프트 동기화 유틸리티

로컬 프롬프트를 Langfuse / LangSmith에 업로드/조회하고 버전을 관리합니다.
backend: "langfuse" | "langsmith" | "both"
"""

from pathlib import Path
from typing import Literal

from src.loaders import find_prompt_file, load_prompt_file

Backend = Literal["langsmith", "langfuse", "both"]


# ---------------------------------------------------------------------------
# Push (로컬 → 원격)
# ---------------------------------------------------------------------------

def push_prompt(
    prompt_name: str,
    backend: Backend = "both",
    targets_dir: str | Path = "targets",
    version_tag: str | None = None,
    description: str | None = None,
    prompt_key: str | None = None,
    metadata_info: dict | None = None,
) -> dict:
    """로컬 프롬프트를 Langfuse/LangSmith에 업로드

    Returns:
        {"url": str | None, "langfuse_version": int | None}
    """
    targets_dir = Path(targets_dir)
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    prompts = load_prompt_file(prompt_file)

    result: dict = {}

    if backend in ("langsmith", "both"):
        try:
            url = _push_langsmith(
                prompt_name, prompts, version_tag, description,
                prompt_key, metadata_info,
            )
            result["url"] = url
        except Exception as e:
            result["langsmith_error"] = str(e)
            print(f"✗ [LangSmith] 업로드 실패: {e}")

    if backend in ("langfuse", "both"):
        try:
            ver = _push_langfuse(prompt_name, prompts, version_tag, metadata_info)
            result["langfuse_version"] = ver
        except Exception as e:
            result["langfuse_error"] = str(e)
            print(f"✗ [Langfuse] 업로드 실패: {e}")

    return result


def _push_langsmith(
    prompt_name: str,
    prompts: dict,
    version_tag: str | None,
    description: str | None,
    prompt_key: str | None,
    metadata_info: dict | None,
) -> str:
    from langsmith import Client

    client = Client()
    prompt = _build_prompt_template(prompts, prompt_key)

    langsmith_name = f"prompt-eval-{prompt_name}"

    tags = []
    if version_tag:
        tags.append(version_tag)

    if description:
        final_description = description
    elif metadata_info:
        final_description = _build_description_with_metadata(prompt_name, metadata_info)
    else:
        final_description = f"Prompt for {prompt_name}"

    url = client.push_prompt(
        langsmith_name,
        object=prompt,
        tags=tags if tags else None,
        description=final_description,
    )

    print(f"✓ [LangSmith] 프롬프트 업로드 완료: {langsmith_name}")
    if version_tag:
        print(f"  태그: {version_tag}")
    return url


def _push_langfuse(
    prompt_name: str,
    prompts: dict,
    version_tag: str | None,
    metadata_info: dict | None,
) -> int:
    from utils.langfuse_client import get_langfuse_client

    content = _build_langfuse_content(prompts)

    labels = ["latest"]
    if version_tag:
        labels.append(version_tag)

    config = {}
    if metadata_info:
        config["metadata"] = metadata_info

    langfuse_name = f"prompt-eval-{prompt_name}"

    client = get_langfuse_client()
    if isinstance(content, list):
        prompt_obj = client.create_prompt(
            name=langfuse_name, type="chat", prompt=content,
            labels=labels, config=config,
        )
    else:
        prompt_obj = client.create_prompt(
            name=langfuse_name, type="text", prompt=content,
            labels=labels, config=config,
        )

    print(f"✓ [Langfuse] 프롬프트 업로드 완료: {langfuse_name} (version: {prompt_obj.version})")
    if version_tag:
        print(f"  태그: {version_tag}")
    return prompt_obj.version


# ---------------------------------------------------------------------------
# Get (원격 → 로컬)
# ---------------------------------------------------------------------------

def get_prompt(
    prompt_name: str,
    backend: Backend = "langsmith",
    version_tag: str | None = None,
    label: str | None = None,
    version: int | None = None,
):
    """Langfuse 또는 LangSmith에서 프롬프트 조회

    backend="both"는 지원하지 않음 (조회는 단일 백엔드만 의미 있음)
    """
    if backend == "both":
        raise ValueError("get_prompt은 backend='both'를 지원하지 않습니다. 하나를 지정하세요.")

    if backend == "langsmith":
        return _get_langsmith_prompt(prompt_name, version_tag)
    else:
        return _get_langfuse_prompt(prompt_name, label, version)


def _get_langsmith_prompt(prompt_name: str, version_tag: str | None = None) -> str:
    from langsmith import Client

    client = Client()
    langsmith_name = f"prompt-eval-{prompt_name}"
    if version_tag:
        langsmith_name = f"{langsmith_name}:{version_tag}"

    prompt = client.pull_prompt(langsmith_name)

    if hasattr(prompt, "template"):
        return prompt.template
    elif hasattr(prompt, "messages"):
        return str(prompt.messages)
    else:
        return str(prompt)


def _get_langfuse_prompt(
    prompt_name: str,
    label: str | None = None,
    version: int | None = None,
):
    from utils.langfuse_client import get_langfuse_client

    langfuse_name = f"prompt-eval-{prompt_name}"
    client = get_langfuse_client()
    return client.get_prompt(langfuse_name, label=label, version=version)


# ---------------------------------------------------------------------------
# LangSmith 전용
# ---------------------------------------------------------------------------

def list_prompt_versions(prompt_name: str) -> list[dict]:
    """프롬프트의 모든 버전/태그 목록 조회 (LangSmith)"""
    from langsmith import Client

    client = Client()
    langsmith_name = f"prompt-eval-{prompt_name}"

    try:
        prompt_info = client.get_prompt(langsmith_name)
        commits = client.list_prompt_commits(langsmith_name)

        versions = []
        for commit in commits:
            versions.append({
                "commit_hash": commit.commit_hash,
                "tags": commit.tags or [],
                "created_at": str(commit.created_at),
            })
        return versions
    except Exception as e:
        print(f"프롬프트 조회 실패: {e}")
        return []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_langfuse_content(prompts: dict) -> str | list[dict]:
    """프롬프트 딕셔너리를 Langfuse 업로드 형식으로 변환"""
    system_keys = ["SYSTEM_PROMPT", "system_prompt", "system"]
    user_keys = ["USER_PROMPT", "user_prompt", "user", "human"]

    system_content = None
    user_content = None

    for key in system_keys:
        if key in prompts:
            system_content = prompts[key]
            break

    for key in user_keys:
        if key in prompts:
            user_content = prompts[key]
            break

    if system_content and user_content:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    if "template" in prompts:
        return prompts["template"]

    if len(prompts) == 1:
        return list(prompts.values())[0]

    parts = []
    for key in sorted(prompts.keys()):
        parts.append(prompts[key])
    return "\n\n".join(parts)


def _build_prompt_template(prompts: dict, prompt_key: str | None = None):
    """프롬프트 딕셔너리를 LangChain 템플릿으로 변환"""
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

    if prompt_key and prompt_key in prompts:
        return PromptTemplate.from_template(prompts[prompt_key])

    if "template" in prompts:
        return PromptTemplate.from_template(prompts["template"])

    if len(prompts) == 1:
        return PromptTemplate.from_template(list(prompts.values())[0])

    messages = []

    system_keys = ["SYSTEM_PROMPT", "system_prompt", "system"]
    for key in system_keys:
        if key in prompts:
            messages.append(("system", prompts[key]))
            break

    user_keys = ["USER_PROMPT", "user_prompt", "user", "human"]
    for key in user_keys:
        if key in prompts:
            messages.append(("human", prompts[key]))
            break

    used_keys = set(system_keys + user_keys)
    for key, value in prompts.items():
        if key not in used_keys:
            if "system" in key.lower():
                messages.append(("system", value))
            else:
                messages.append(("human", value))

    if not messages:
        raise ValueError("프롬프트를 찾을 수 없습니다.")

    return ChatPromptTemplate.from_messages(messages)


def _build_description_with_metadata(prompt_name: str, metadata_info: dict) -> str:
    """메타데이터를 포함한 description 생성 (LangSmith용)"""
    lines = [f"Prompt for {prompt_name}", "", "---"]

    if metadata_info.get("version"):
        lines.append(f"version: {metadata_info['version']}")
    if metadata_info.get("author"):
        lines.append(f"author: {metadata_info['author']}")
    if metadata_info.get("changes"):
        lines.append(f"changes: {metadata_info['changes']}")
    if metadata_info.get("date"):
        lines.append(f"date: {metadata_info['date']}")

    return "\n".join(lines)


