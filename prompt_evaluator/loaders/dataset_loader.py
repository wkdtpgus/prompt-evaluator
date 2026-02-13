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
    data_dir = datasets_dir / prompt_name
    config_file = targets_dir / prompt_name / "config.yaml"

    # 필수 파일 확인
    required_data_files = ["test_cases.json", "expected.json"]
    for f in required_data_files:
        if not (data_dir / f).exists():
            raise FileNotFoundError(f"데이터 파일 없음: {data_dir / f}")

    if not config_file.exists():
        raise FileNotFoundError(f"설정 파일 없음: {config_file}")

    # config 먼저 로드 (prompt_file 필드 확인)
    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    # Pipeline 모드: 프롬프트 파일 불필요
    pipeline_config = eval_config.get("pipeline")
    if pipeline_config and isinstance(pipeline_config, dict):
        template = ""
        prompts = {}
    else:
        # 프롬프트 파일 찾기 (prompt_file 오버라이드 지원)
        prompt_file_override = eval_config.get("prompt_file")
        prompt_file = find_prompt_file(
            prompt_name, targets_dir, prompt_file_override=prompt_file_override
        )

        # 프롬프트 로드
        prompts = load_prompt_file(prompt_file)

        # prompt_key가 지정된 경우 해당 키만 사용
        prompt_key = eval_config.get("prompt_key")
        if prompt_key:
            if prompt_key not in prompts:
                available = list(prompts.keys())
                raise ValueError(
                    f"prompt_key '{prompt_key}'을 찾을 수 없음. 사용 가능한 키: {available}"
                )
            prompts = {prompt_key: prompts[prompt_key]}

        # 단일 템플릿 추출
        template = _extract_template(prompts)

    # 데이터 파일 로드
    with open(data_dir / "test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected = json.load(f)

    return {
        "template": template,
        "prompts": prompts,
        "test_cases": test_cases,
        "expected": expected,
        "eval_config": eval_config,
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

    폴더 구조: targets/{name}/config.yaml + prompt 파일 (또는 prompt_file 참조)
    """
    targets_dir = Path(targets_dir)
    datasets_dir = Path(datasets_dir)
    sets = []

    if not targets_dir.exists():
        return sets

    for folder in targets_dir.iterdir():
        if not folder.is_dir():
            continue

        name = folder.name

        # config.yaml 존재 확인
        config_file = folder / "config.yaml"
        if not config_file.exists():
            continue

        # config에서 prompt_file 확인
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # pipeline 모드에서는 프롬프트 파일 불필요
        pipeline_config = config.get("pipeline")
        if pipeline_config and isinstance(pipeline_config, dict):
            has_prompt = True
        else:
            prompt_file_override = config.get("prompt_file")
            if prompt_file_override:
                has_prompt = Path(prompt_file_override).exists()
            else:
                has_prompt = any(
                    (folder / f"prompt{ext}").exists() for ext in SUPPORTED_EXTENSIONS
                )

        if not has_prompt:
            continue

        # 데이터셋 확인
        data_dir = datasets_dir / name
        required_data = ["test_cases.json", "expected.json"]
        if data_dir.exists() and all((data_dir / f).exists() for f in required_data):
            sets.append(name)

    return sets
