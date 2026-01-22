"""데이터 로드/저장

평가 대상 프롬프트, 테스트 케이스, 설정 파일 관리

지원 프롬프트 파일 형식:
- .txt: 단일 템플릿 텍스트
- .py: Python 변수로 정의된 프롬프트 (SYSTEM_PROMPT, USER_PROMPT 등)
- .xml: XML 구조의 프롬프트
"""

import ast
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import yaml
from langsmith import Client


# =============================================================================
# 프롬프트 파일 로더 (다중 형식 지원)
# =============================================================================

def load_prompt_file(prompt_file: Path) -> dict[str, str]:
    """프롬프트 파일 로드 (다중 형식 지원)

    Args:
        prompt_file: 프롬프트 파일 경로 (.txt, .py, .xml)

    Returns:
        dict: 프롬프트 내용
            - .txt: {"template": "..."}
            - .py: {"SYSTEM_PROMPT": "...", "USER_PROMPT": "...", ...}
            - .xml: {"system": "...", "user": "...", ...}
    """
    suffix = prompt_file.suffix.lower()

    if suffix == ".txt":
        return {"template": prompt_file.read_text(encoding="utf-8")}
    elif suffix == ".py":
        return _load_prompt_from_py(prompt_file)
    elif suffix == ".xml":
        return _load_prompt_from_xml(prompt_file)
    else:
        raise ValueError(f"지원하지 않는 프롬프트 형식: {suffix} (지원: .txt, .py, .xml)")


def _load_prompt_from_py(prompt_file: Path) -> dict[str, str]:
    """Python 파일에서 프롬프트 변수 추출

    다음 패턴의 변수를 추출:
    - *_PROMPT = \"\"\"...\"\"\"
    - *_SYSTEM_PROMPT = \"\"\"...\"\"\"
    - *_USER_PROMPT = \"\"\"...\"\"\"

    Args:
        prompt_file: .py 파일 경로

    Returns:
        dict: 변수명 -> 프롬프트 내용
    """
    content = prompt_file.read_text(encoding="utf-8")
    prompts = {}

    # AST로 파싱하여 문자열 변수 추출
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        # PROMPT로 끝나는 변수만 추출
                        if var_name.endswith("_PROMPT") or var_name == "PROMPT":
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                prompts[var_name] = node.value.value
    except SyntaxError as e:
        raise ValueError(f"Python 파일 파싱 실패: {e}")

    if not prompts:
        raise ValueError(f"프롬프트 변수를 찾을 수 없음: {prompt_file} (*_PROMPT 패턴 필요)")

    return prompts


def _load_prompt_from_xml(prompt_file: Path) -> dict[str, str]:
    """XML 파일에서 프롬프트 추출

    예시 XML 구조:
    <prompts>
        <system>시스템 프롬프트...</system>
        <user>유저 프롬프트...</user>
    </prompts>

    또는:
    <prompt>
        <template>프롬프트 템플릿...</template>
    </prompt>

    Args:
        prompt_file: .xml 파일 경로

    Returns:
        dict: 태그명 -> 프롬프트 내용
    """
    content = prompt_file.read_text(encoding="utf-8")
    prompts = {}

    try:
        root = ET.fromstring(content)

        # 모든 자식 요소를 프롬프트로 추출
        for child in root:
            text = child.text
            if text:
                # 들여쓰기 정리
                text = text.strip()
                prompts[child.tag] = text

    except ET.ParseError as e:
        raise ValueError(f"XML 파일 파싱 실패: {e}")

    if not prompts:
        raise ValueError(f"프롬프트를 찾을 수 없음: {prompt_file}")

    return prompts


def find_prompt_file(prompt_name: str, targets_dir: Path) -> Path:
    """프롬프트 파일 찾기 (다중 형식 지원)

    파일명 패턴 (우선순위):
    1. {name}_prompt.txt/.py/.xml
    2. {name}.txt/.py/.xml

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: 프롬프트 파일 디렉토리

    Returns:
        프롬프트 파일 경로

    Raises:
        FileNotFoundError: 프롬프트 파일이 없는 경우
    """
    # 파일명 패턴: {name}_prompt.ext 또는 {name}.ext
    patterns = [f"{prompt_name}_prompt", prompt_name]

    for pattern in patterns:
        for ext in [".txt", ".py", ".xml"]:
            prompt_file = targets_dir / f"{pattern}{ext}"
            if prompt_file.exists():
                return prompt_file

    raise FileNotFoundError(
        f"프롬프트 파일 없음: {targets_dir}/{prompt_name}[_prompt].[txt|py|xml]"
    )


def load_evaluation_set(
    prompt_name: str,
    targets_dir: str | Path = "targets",
    datasets_dir: str | Path = "datasets",
    configs_dir: str | Path = "configs"
) -> dict:
    """평가 대상 프롬프트와 데이터셋 로드

    Args:
        prompt_name: 프롬프트 이름 (예: "prep_analyzer")
        targets_dir: 평가 대상 프롬프트 폴더 경로
        datasets_dir: datasets 폴더 경로
        configs_dir: configs 폴더 경로

    Returns:
        {
            "template": str,           # .txt인 경우
            "prompts": dict[str, str], # .py/.xml인 경우 (여러 프롬프트)
            "test_cases": list[dict],
            "expected": dict,
            "eval_config": dict
        }
    """
    targets_dir = Path(targets_dir)
    datasets_dir = Path(datasets_dir)
    configs_dir = Path(configs_dir)

    # 파일 경로 구성 (다중 형식 지원)
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    data_dir = datasets_dir / f"{prompt_name}_data"
    config_file = configs_dir / f"{prompt_name}.yaml"

    required_data_files = ["test_cases.json", "expected.json"]
    for f in required_data_files:
        if not (data_dir / f).exists():
            raise FileNotFoundError(f"데이터 파일 없음: {data_dir / f}")

    if not config_file.exists():
        raise FileNotFoundError(f"설정 파일 없음: {config_file}")

    # 프롬프트 로드 (다중 형식 지원)
    prompts = load_prompt_file(prompt_file)

    # 단일 템플릿 추출 (하위 호환성)
    if "template" in prompts:
        template = prompts["template"]
    else:
        # .py/.xml의 경우 첫 번째 또는 특정 키 사용
        # 우선순위: SYSTEM_PROMPT + USER_PROMPT 조합 > 첫 번째 값
        if "SYSTEM_PROMPT" in prompts and "USER_PROMPT" in prompts:
            template = prompts["SYSTEM_PROMPT"] + "\n\n" + prompts["USER_PROMPT"]
        elif "system" in prompts and "user" in prompts:
            template = prompts["system"] + "\n\n" + prompts["user"]
        else:
            # 첫 번째 프롬프트 사용
            template = list(prompts.values())[0]

    with open(data_dir / "test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected = json.load(f)

    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    return {
        "template": template,
        "prompts": prompts,  # 원본 프롬프트 dict (다중 프롬프트 접근용)
        "test_cases": test_cases,
        "expected": expected,
        "eval_config": eval_config
    }


def upload_to_langsmith(
    prompt_name: str,
    targets_dir: str | Path = "targets",
    datasets_dir: str | Path = "datasets",
    dataset_name: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """로컬 데이터셋을 LangSmith Dataset으로 업로드

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: 평가 대상 프롬프트 폴더 경로
        datasets_dir: datasets 폴더 경로
        dataset_name: LangSmith 데이터셋 이름 (기본값: prompt_name)
        description: 데이터셋 설명

    Returns:
        생성된 데이터셋 이름
    """
    data = load_evaluation_set(prompt_name, targets_dir, datasets_dir)

    if dataset_name is None:
        dataset_name = f"prompt-eval-{prompt_name}"

    client = Client()

    # 기존 데이터셋 확인 및 삭제
    try:
        existing = client.read_dataset(dataset_name=dataset_name)
        print(f"기존 데이터셋 삭제: {dataset_name}")
        client.delete_dataset(dataset_id=existing.id)
    except Exception:
        pass

    # 새 데이터셋 생성
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description or f"Prompt evaluation dataset for {prompt_name}"
    )
    print(f"데이터셋 생성: {dataset_name}")

    # 테스트 케이스를 Example로 변환
    examples = []
    for case in data["test_cases"]:
        case_id = case["id"]
        inputs = case["inputs"]
        expected_output = data["expected"].get(case_id, {})

        examples.append({
            "inputs": inputs,
            "outputs": {
                "reference": expected_output.get("reference", {}),
                "keywords": expected_output.get("keywords", []),
                "forbidden": expected_output.get("forbidden", [])
            },
            "metadata": {
                "case_id": case_id,
                "description": case.get("description", "")
            }
        })

    client.create_examples(
        inputs=[ex["inputs"] for ex in examples],
        outputs=[ex["outputs"] for ex in examples],
        metadata=[ex["metadata"] for ex in examples],
        dataset_id=dataset.id
    )

    print(f"✓ {len(examples)}개 테스트 케이스 업로드 완료")
    return dataset_name


def list_evaluation_sets(
    targets_dir: str | Path = "targets",
    datasets_dir: str | Path = "datasets",
    configs_dir: str | Path = "configs"
) -> list[str]:
    """사용 가능한 평가 세트 목록"""
    targets_dir = Path(targets_dir)
    datasets_dir = Path(datasets_dir)
    configs_dir = Path(configs_dir)
    sets = []

    # 다중 형식 지원: .txt, .py, .xml
    # 파일명 패턴: *_prompt.ext 또는 *.ext (schemas.py 등 제외)
    for ext in [".txt", ".py", ".xml"]:
        for prompt_file in targets_dir.glob(f"*{ext}"):
            stem = prompt_file.stem

            # schemas.py 등 프롬프트가 아닌 파일 제외
            if stem in ["schemas", "__init__"]:
                continue

            # {name}_prompt 또는 {name} 패턴에서 이름 추출
            if stem.endswith("_prompt"):
                name = stem.replace("_prompt", "")
            else:
                name = stem

            # 중복 방지 (같은 이름의 다른 형식이 있을 수 있음)
            if name in sets:
                continue

            data_dir = datasets_dir / f"{name}_data"
            config_file = configs_dir / f"{name}.yaml"

            required_data = ["test_cases.json", "expected.json"]
            if (data_dir.exists()
                and all((data_dir / f).exists() for f in required_data)
                and config_file.exists()):
                sets.append(name)

    return sets


# =============================================================================
# LangSmith Prompt 버전 관리
# =============================================================================

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
