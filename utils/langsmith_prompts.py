"""LangSmith Prompt 버전 관리

로컬 프롬프트를 LangSmith에 업로드/다운로드하고 버전을 관리합니다.
"""

from pathlib import Path
from typing import Optional

from langsmith import Client

from src.loaders import find_prompt_file, load_prompt_file


def push_prompt(
    prompt_name: str,
    targets_dir: str | Path = "targets",
    version_tag: Optional[str] = None,
    description: Optional[str] = None,
    prompt_key: Optional[str] = None,
    metadata_info: Optional[dict] = None,
) -> str:
    """로컬 프롬프트를 LangSmith Prompts에 업로드 (버전 관리)

    Args:
        prompt_name: 프롬프트 이름 (예: "prep_analyzer")
        targets_dir: 프롬프트 파일 경로
        version_tag: 버전 태그 (예: "v1.0", "production")
        description: 프롬프트 설명
        prompt_key: .py/.xml 파일의 경우 특정 프롬프트 키 지정
                    (예: "SYSTEM_PROMPT", "ANALYZE_USER_PROMPT")
        metadata_info: 메타데이터 정보 (version, author, changes, date)
                       제공되면 description에 자동 포함

    Returns:
        LangSmith 프롬프트 URL
    """
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

    targets_dir = Path(targets_dir)

    # 프롬프트 파일 찾기 (다중 형식 지원)
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    prompts = load_prompt_file(prompt_file)

    client = Client()

    # 프롬프트 템플릿 생성
    prompt = _build_prompt_template(prompts, prompt_key)

    # LangSmith에 푸시 (프롬프트 이름만 사용, 슬래시 경로 없이)
    langsmith_prompt_name = f"prompt-eval-{prompt_name}"

    tags = []
    if version_tag:
        tags.append(version_tag)

    # description 생성: 메타데이터 정보가 있으면 포함
    if description:
        final_description = description
    elif metadata_info:
        final_description = _build_description_with_metadata(prompt_name, metadata_info)
    else:
        final_description = f"Prompt for {prompt_name}"

    url = client.push_prompt(
        langsmith_prompt_name,
        object=prompt,
        tags=tags if tags else None,
        description=final_description,
    )

    print(f"✓ 프롬프트 업로드 완료: {langsmith_prompt_name}")
    if version_tag:
        print(f"  태그: {version_tag}")
    print(f"  URL: {url}")

    return url


def _build_prompt_template(prompts: dict, prompt_key: Optional[str] = None):
    """프롬프트 딕셔너리를 LangChain 템플릿으로 변환

    Args:
        prompts: 프롬프트 딕셔너리 (예: {"SYSTEM_PROMPT": "...", "USER_PROMPT": "..."})
        prompt_key: 특정 키만 사용할 경우 지정

    Returns:
        PromptTemplate 또는 ChatPromptTemplate
    """
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

    # 특정 키 지정된 경우
    if prompt_key and prompt_key in prompts:
        return PromptTemplate.from_template(prompts[prompt_key])

    # 단일 템플릿인 경우
    if "template" in prompts:
        return PromptTemplate.from_template(prompts["template"])

    if len(prompts) == 1:
        return PromptTemplate.from_template(list(prompts.values())[0])

    # 여러 프롬프트가 있는 경우 ChatPromptTemplate으로 변환
    messages = []

    # SYSTEM_PROMPT 처리
    system_keys = ["SYSTEM_PROMPT", "system_prompt", "system"]
    for key in system_keys:
        if key in prompts:
            messages.append(("system", prompts[key]))
            break

    # USER_PROMPT 처리
    user_keys = ["USER_PROMPT", "user_prompt", "user", "human"]
    for key in user_keys:
        if key in prompts:
            messages.append(("human", prompts[key]))
            break

    # 매칭되지 않은 나머지 키들도 human 메시지로 추가
    used_keys = set(system_keys + user_keys)
    for key, value in prompts.items():
        if key not in used_keys:
            # 키 이름에 따라 역할 추정
            if "system" in key.lower():
                messages.append(("system", value))
            else:
                messages.append(("human", value))

    if not messages:
        raise ValueError("프롬프트를 찾을 수 없습니다.")

    return ChatPromptTemplate.from_messages(messages)


def _build_description_with_metadata(prompt_name: str, metadata_info: dict) -> str:
    """메타데이터를 포함한 description 생성

    Args:
        prompt_name: 프롬프트 이름
        metadata_info: {version, author, changes, date}

    Returns:
        포맷된 description 문자열
    """
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


def pull_prompt(
    prompt_name: str,
    version_tag: Optional[str] = None,
) -> str:
    """LangSmith에서 프롬프트 가져오기

    Args:
        prompt_name: 프롬프트 이름
        version_tag: 특정 버전 태그 (None이면 최신)

    Returns:
        프롬프트 템플릿 문자열
    """
    client = Client()

    langsmith_prompt_name = f"prompt-eval-{prompt_name}"
    if version_tag:
        langsmith_prompt_name = f"{langsmith_prompt_name}:{version_tag}"

    prompt = client.pull_prompt(langsmith_prompt_name)

    # PromptTemplate에서 템플릿 문자열 추출
    if hasattr(prompt, "template"):
        return prompt.template
    elif hasattr(prompt, "messages"):
        # ChatPromptTemplate인 경우
        return str(prompt.messages)
    else:
        return str(prompt)


def list_prompt_versions(prompt_name: str) -> list[dict]:
    """프롬프트의 모든 버전/태그 목록 조회

    Args:
        prompt_name: 프롬프트 이름

    Returns:
        버전 정보 목록
    """
    client = Client()
    langsmith_prompt_name = f"prompt-eval-{prompt_name}"

    try:
        # 프롬프트 정보 조회
        prompt_info = client.get_prompt(langsmith_prompt_name)
        commits = client.list_prompt_commits(langsmith_prompt_name)

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
