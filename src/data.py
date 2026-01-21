"""데이터 로드/저장

프롬프트, 테스트 케이스, 설정 파일 관리
"""

import json
from pathlib import Path
from typing import Optional

import yaml
from langsmith import Client


def load_evaluation_set(
    prompt_name: str,
    prompts_dir: str | Path = "prompts",
    datasets_dir: str | Path = "datasets"
) -> dict:
    """프롬프트와 데이터셋 로드

    Args:
        prompt_name: 프롬프트 이름 (예: "prep_analyzer")
        prompts_dir: prompts 폴더 경로
        datasets_dir: datasets 폴더 경로

    Returns:
        {
            "template": str,
            "test_cases": list[dict],
            "expected": dict,
            "eval_config": dict
        }
    """
    prompts_dir = Path(prompts_dir)
    datasets_dir = Path(datasets_dir)

    # 파일 경로 구성
    prompt_file = prompts_dir / f"{prompt_name}_prompt.txt"
    data_dir = datasets_dir / f"{prompt_name}_data"

    # 필수 파일 확인
    if not prompt_file.exists():
        raise FileNotFoundError(f"프롬프트 파일 없음: {prompt_file}")

    required_data_files = ["test_cases.json", "expected.json", "eval_config.yaml"]
    for f in required_data_files:
        if not (data_dir / f).exists():
            raise FileNotFoundError(f"데이터 파일 없음: {data_dir / f}")

    # 파일 로드
    template = prompt_file.read_text(encoding="utf-8")

    with open(data_dir / "test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected = json.load(f)

    with open(data_dir / "eval_config.yaml", "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    return {
        "template": template,
        "test_cases": test_cases,
        "expected": expected,
        "eval_config": eval_config
    }


def upload_to_langsmith(
    prompt_name: str,
    prompts_dir: str | Path = "prompts",
    datasets_dir: str | Path = "datasets",
    dataset_name: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """로컬 데이터셋을 LangSmith Dataset으로 업로드

    Args:
        prompt_name: 프롬프트 이름
        prompts_dir: prompts 폴더 경로
        datasets_dir: datasets 폴더 경로
        dataset_name: LangSmith 데이터셋 이름 (기본값: prompt_name)
        description: 데이터셋 설명

    Returns:
        생성된 데이터셋 이름
    """
    data = load_evaluation_set(prompt_name, prompts_dir, datasets_dir)

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
    prompts_dir: str | Path = "prompts",
    datasets_dir: str | Path = "datasets"
) -> list[str]:
    """사용 가능한 평가 세트 목록"""
    prompts_dir = Path(prompts_dir)
    datasets_dir = Path(datasets_dir)
    sets = []

    for prompt_file in prompts_dir.glob("*_prompt.txt"):
        name = prompt_file.stem.replace("_prompt", "")
        data_dir = datasets_dir / f"{name}_data"

        required = ["test_cases.json", "expected.json", "eval_config.yaml"]
        if data_dir.exists() and all((data_dir / f).exists() for f in required):
            sets.append(name)

    return sets
