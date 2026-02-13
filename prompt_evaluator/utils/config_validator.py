"""Config 검증

config yaml 파일의 유효성을 검증합니다.
"""

from pathlib import Path
from typing import NamedTuple

import yaml

from prompt_evaluator.loaders import SUPPORTED_EXTENSIONS


class ValidationResult(NamedTuple):
    """검증 결과"""

    valid: bool
    errors: list[str]
    warnings: list[str]


# 필수 필드
REQUIRED_FIELDS = ["name", "evaluators"]

# 허용 값
VALID_OUTPUT_FORMATS = ["text", "json"]
VALID_RUN_MODES = ["quick", "full"]
VALID_EVALUATOR_TYPES = ["rule_based", "llm_judge"]


def validate_config(
    config: dict,
    prompt_name: str,
    targets_dir: Path = Path("targets"),
    datasets_dir: Path = Path("datasets"),
    eval_prompts_dir: Path = Path("eval_prompts"),
) -> ValidationResult:
    """config yaml 유효성 검증

    Args:
        config: 로드된 config dict
        prompt_name: 프롬프트 이름
        targets_dir: targets 폴더 경로
        datasets_dir: datasets 폴더 경로
        eval_prompts_dir: eval_prompts 폴더 경로

    Returns:
        ValidationResult(valid, errors, warnings)
    """
    errors = []
    warnings = []

    # 1. 필수 필드 확인
    for field in REQUIRED_FIELDS:
        if field not in config:
            errors.append(f"필수 필드 누락: {field}")

    # 2. name 일치 확인
    if config.get("name") and config["name"] != prompt_name:
        warnings.append(f"name '{config['name']}'이 폴더명 '{prompt_name}'과 불일치")

    # 3. output_format 유효성
    output_format = config.get("output_format")
    if output_format and output_format not in VALID_OUTPUT_FORMATS:
        errors.append(
            f"잘못된 output_format: {output_format} (허용: {VALID_OUTPUT_FORMATS})"
        )

    # 4. run_mode 유효성
    run_mode = config.get("run_mode")
    if run_mode and run_mode not in VALID_RUN_MODES:
        errors.append(f"잘못된 run_mode: {run_mode} (허용: {VALID_RUN_MODES})")

    # 5. Pipeline 설정 검증 또는 프롬프트 파일 존재 확인
    pipeline_config = config.get("pipeline")
    if pipeline_config and isinstance(pipeline_config, dict):
        # Pipeline 모드 검증
        if not pipeline_config.get("module"):
            errors.append("pipeline.module은 필수입니다.")
        if not pipeline_config.get("class"):
            errors.append("pipeline.class는 필수입니다.")
        input_model = pipeline_config.get("input_model")
        if input_model and not isinstance(input_model, str):
            errors.append("pipeline.input_model은 dotted path 문자열이어야 합니다.")
        if config.get("prompt_file"):
            warnings.append(
                "pipeline과 prompt_file이 동시에 설정됨. "
                "pipeline 모드에서는 prompt_file이 무시됩니다."
            )
    else:
        # 기존 프롬프트 파일 존재 확인
        prompt_file_override = config.get("prompt_file")
        if prompt_file_override:
            prompt_path = Path(prompt_file_override)
            if not prompt_path.exists():
                errors.append(f"prompt_file 경로 없음: {prompt_path}")
            elif prompt_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append(
                    f"지원하지 않는 프롬프트 형식: {prompt_path.suffix} "
                    f"(지원: {list(SUPPORTED_EXTENSIONS)})"
                )
        else:
            prompt_folder = targets_dir / prompt_name
            if prompt_folder.is_dir():
                has_prompt = any(
                    (prompt_folder / f"prompt{ext}").exists()
                    for ext in SUPPORTED_EXTENSIONS
                )
                if not has_prompt:
                    errors.append(
                        f"프롬프트 파일 없음: {prompt_folder}/prompt.[txt|py|xml|md]"
                    )
            else:
                errors.append(f"프롬프트 폴더 없음: {prompt_folder}")

    # 6. 데이터셋 파일 존재 확인
    data_dir = datasets_dir / prompt_name
    if data_dir.is_dir():
        for required_file in ["test_cases.json", "expected.json"]:
            if not (data_dir / required_file).exists():
                errors.append(f"데이터 파일 없음: {data_dir / required_file}")
    else:
        errors.append(f"데이터셋 폴더 없음: {data_dir}")

    # 7. eval_prompts 파일 존재 확인 (criteria는 'domain/name' 전체 경로)
    for evaluator in config.get("evaluators", []):
        if evaluator.get("type") == "llm_judge":
            for criterion in evaluator.get("criteria", []):
                criterion_file = eval_prompts_dir / f"{criterion}.txt"
                if not criterion_file.exists():
                    warnings.append(f"eval_prompt 파일 없음: {criterion_file}")

    # 8. evaluators 구조 확인
    for i, evaluator in enumerate(config.get("evaluators", [])):
        eval_type = evaluator.get("type")
        if not eval_type:
            errors.append(f"evaluators[{i}]: type 필드 누락")
        elif eval_type not in VALID_EVALUATOR_TYPES:
            errors.append(f"evaluators[{i}]: 잘못된 type '{eval_type}'")

    valid = len(errors) == 0
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def validate_all_configs(
    targets_dir: Path = Path("targets"),
    datasets_dir: Path = Path("datasets"),
    eval_prompts_dir: Path = Path("eval_prompts"),
) -> dict[str, ValidationResult]:
    """모든 config 파일 검증

    targets/{name}/config.yaml 파일을 찾아서 검증합니다.

    Returns:
        {prompt_name: ValidationResult}
    """
    results = {}

    for folder in targets_dir.iterdir():
        if not folder.is_dir():
            continue

        config_file = folder / "config.yaml"
        if not config_file.exists():
            continue

        prompt_name = folder.name

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        result = validate_config(
            config=config,
            prompt_name=prompt_name,
            targets_dir=targets_dir,
            datasets_dir=datasets_dir,
            eval_prompts_dir=eval_prompts_dir,
        )
        results[prompt_name] = result

    return results
