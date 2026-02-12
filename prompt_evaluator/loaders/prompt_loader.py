"""프롬프트 파일 로더

다양한 형식의 프롬프트 파일을 로드합니다.

지원 형식:
- .txt: 단일 템플릿 텍스트
- .md: 마크다운 형식 프롬프트
- .py: Python 변수로 정의된 프롬프트 (SYSTEM_PROMPT, USER_PROMPT 등)
- .xml: XML 구조의 프롬프트
"""

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

SUPPORTED_EXTENSIONS = [".txt", ".py", ".xml", ".md"]


def load_prompt_file(prompt_file: Path) -> dict[str, str]:
    """프롬프트 파일 로드 (다중 형식 지원)

    Args:
        prompt_file: 프롬프트 파일 경로 (.txt, .md, .py, .xml)

    Returns:
        dict: 프롬프트 내용
            - .txt/.md: {"template": "..."}
            - .py: {"SYSTEM_PROMPT": "...", "USER_PROMPT": "...", ...}
            - .xml: {"system": "...", "user": "...", ...}
    """
    suffix = prompt_file.suffix.lower()

    if suffix in [".txt", ".md"]:
        return {"template": prompt_file.read_text(encoding="utf-8")}
    elif suffix == ".py":
        return _load_prompt_from_py(prompt_file)
    elif suffix == ".xml":
        return _load_prompt_from_xml(prompt_file)
    else:
        raise ValueError(f"지원하지 않는 프롬프트 형식: {suffix} (지원: .txt, .md, .py, .xml)")


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

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
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

    Args:
        prompt_file: .xml 파일 경로

    Returns:
        dict: 태그명 -> 프롬프트 내용
    """
    content = prompt_file.read_text(encoding="utf-8")
    prompts = {}

    try:
        root = ET.fromstring(content)
        for child in root:
            text = child.text
            if text:
                text = text.strip()
                prompts[child.tag] = text
    except ET.ParseError as e:
        raise ValueError(f"XML 파일 파싱 실패: {e}")

    if not prompts:
        raise ValueError(f"프롬프트를 찾을 수 없음: {prompt_file}")

    return prompts


def find_prompt_file(prompt_name: str, targets_dir: Path) -> Path:
    """프롬프트 파일 찾기 (다중 형식 지원)

    파일명 패턴:
    - targets/{name}/prompt.txt/.py/.xml/.md

    Args:
        prompt_name: 프롬프트 이름
        targets_dir: 프롬프트 파일 디렉토리

    Returns:
        프롬프트 파일 경로

    Raises:
        FileNotFoundError: 프롬프트 파일이 없는 경우
    """
    folder_path = targets_dir / prompt_name

    if folder_path.is_dir():
        for ext in SUPPORTED_EXTENSIONS:
            prompt_file = folder_path / f"prompt{ext}"
            if prompt_file.exists():
                return prompt_file

    raise FileNotFoundError(
        f"프롬프트 파일 없음: {targets_dir}/{prompt_name}/prompt.[txt|py|xml|md]"
    )
