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
) -> str:
    """로컬 프롬프트를 LangSmith Prompts에 업로드 (버전 관리)

    Args:
        prompt_name: 프롬프트 이름 (예: "prep_analyzer")
        targets_dir: 프롬프트 파일 경로
        version_tag: 버전 태그 (예: "v1.0", "production")
        description: 프롬프트 설명
        prompt_key: .py/.xml 파일의 경우 특정 프롬프트 키 지정
                    (예: "SYSTEM_PROMPT", "ANALYZE_USER_PROMPT")

    Returns:
        LangSmith 프롬프트 URL
    """
    from langchain_core.prompts import PromptTemplate

    targets_dir = Path(targets_dir)

    # 프롬프트 파일 찾기 (다중 형식 지원)
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    prompts = load_prompt_file(prompt_file)

    # 업로드할 템플릿 결정
    if "template" in prompts:
        template = prompts["template"]
    elif prompt_key and prompt_key in prompts:
        template = prompts[prompt_key]
    elif len(prompts) == 1:
        template = list(prompts.values())[0]
    else:
        # 여러 프롬프트가 있는 경우 안내
        available_keys = list(prompts.keys())
        raise ValueError(
            f"여러 프롬프트가 발견됨: {available_keys}\n"
            f"--key 옵션으로 특정 프롬프트를 지정하거나, "
            f"개별 프롬프트를 각각 업로드하세요."
        )

    client = Client()

    # LangChain PromptTemplate으로 변환
    prompt = PromptTemplate.from_template(template)

    # LangSmith에 푸시 (프롬프트 이름만 사용, 슬래시 경로 없이)
    langsmith_prompt_name = f"prompt-eval-{prompt_name}"

    tags = []
    if version_tag:
        tags.append(version_tag)

    url = client.push_prompt(
        langsmith_prompt_name,
        object=prompt,
        tags=tags if tags else None,
        description=description or f"Prompt for {prompt_name}",
    )

    print(f"✓ 프롬프트 업로드 완료: {langsmith_prompt_name}")
    if version_tag:
        print(f"  태그: {version_tag}")
    print(f"  URL: {url}")

    return url


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
