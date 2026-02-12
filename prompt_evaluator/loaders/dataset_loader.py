"""데이터셋 로더

평가용 테스트 케이스, 기대 결과, 설정 파일을 로드합니다.
"""

import json
from pathlib import Path

import yaml

from prompt_evaluator.loaders.prompt_loader import (
    SUPPORTED_EXTENSIONS,
    find_prompt_file,
    load_prompt_file,
)


def load_evaluation_set(
    prompt_name: str,
    targets_dir: str | Path = "targets",
    datasets_dir: str | Path = "datasets",
) -> dict:
    """평가 대상 프롬프트와 데이터셋 로드

    Args:
        prompt_name: 프롬프트 이름 (예: "prep_chatbot")
        targets_dir: 평가 대상 프롬프트 폴더 경로
        datasets_dir: datasets 폴더 경로

    Returns:
        {
            "template": str,           # 단일 템플릿
            "prompts": dict[str, str], # 원본 프롬프트 dict
            "test_cases": list[dict],
            "expected": dict,
            "eval_config": dict
        }
    """
    targets_dir = Path(targets_dir)
    datasets_dir = Path(datasets_dir)

    # 파일 경로 구성
    prompt_file = find_prompt_file(prompt_name, targets_dir)
    data_dir = datasets_dir / prompt_name
    config_file = targets_dir / prompt_name / "config.yaml"

    # 필수 파일 확인
    required_data_files = ["test_cases.json", "expected.json"]
    for f in required_data_files:
        if not (data_dir / f).exists():
            raise FileNotFoundError(f"데이터 파일 없음: {data_dir / f}")

    if not config_file.exists():
        raise FileNotFoundError(f"설정 파일 없음: {config_file}")

    # 프롬프트 로드
    prompts = load_prompt_file(prompt_file)

    # 단일 템플릿 추출
    template = _extract_template(prompts)

    # 데이터 파일 로드
    with open(data_dir / "test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected = json.load(f)

    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    return {
        "template": template,
        "prompts": prompts,
        "test_cases": test_cases,
        "expected": expected,
        "eval_config": eval_config
    }


def _extract_template(prompts: dict[str, str]) -> str:
    """프롬프트 dict에서 단일 템플릿 추출"""
    if "template" in prompts:
        return prompts["template"]

    # SYSTEM_PROMPT + USER_PROMPT 조합
    if "SYSTEM_PROMPT" in prompts and "USER_PROMPT" in prompts:
        return prompts["SYSTEM_PROMPT"] + "\n\n" + prompts["USER_PROMPT"]

    # XML 스타일: system + user
    if "system" in prompts and "user" in prompts:
        return prompts["system"] + "\n\n" + prompts["user"]

    # 첫 번째 프롬프트 사용
    return list(prompts.values())[0]


def list_evaluation_sets(
    targets_dir: str | Path = "targets",
    datasets_dir: str | Path = "datasets",
) -> list[str]:
    """사용 가능한 평가 세트 목록

    폴더 구조: targets/{name}/prompt.[txt|md|py|xml]
    """
    targets_dir = Path(targets_dir)
    datasets_dir = Path(datasets_dir)
    sets = []

    for folder in targets_dir.iterdir():
        if not folder.is_dir():
            continue

        name = folder.name

        # prompt.* 파일 존재 확인
        has_prompt = any(
            (folder / f"prompt{ext}").exists()
            for ext in SUPPORTED_EXTENSIONS
        )
        if not has_prompt:
            continue

        # config.yaml 존재 확인 (targets/{name}/config.yaml)
        config_file = folder / "config.yaml"
        if not config_file.exists():
            continue

        # 데이터셋 확인
        data_dir = datasets_dir / name
        required_data = ["test_cases.json", "expected.json"]
        if (data_dir.exists()
            and all((data_dir / f).exists() for f in required_data)):
            sets.append(name)

    return sets
