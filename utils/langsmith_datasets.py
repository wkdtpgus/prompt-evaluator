"""LangSmith 데이터셋 관리

로컬 테스트 케이스를 LangSmith Dataset으로 업로드합니다.
"""

from typing import Optional

from langsmith import Client

from src.loaders import load_evaluation_set


def upload_to_langsmith(
    prompt_name: str,
    targets_dir: str = "targets",
    datasets_dir: str = "datasets",
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
