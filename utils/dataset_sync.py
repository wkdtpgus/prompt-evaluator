"""데이터셋 동기화 유틸리티

로컬 데이터셋을 Langfuse / LangSmith에 업로드하고 조회합니다.
backend: "langfuse" | "langsmith" | "both"
"""

import json
from pathlib import Path
from typing import Literal, Optional

Backend = Literal["langsmith", "langfuse", "both"]


# ---------------------------------------------------------------------------
# Upload (로컬 → 원격)
# ---------------------------------------------------------------------------


def upload_dataset(
    prompt_name: str,
    backend: Backend = "both",
    targets_dir: str = "targets",
    datasets_dir: str = "datasets",
    dataset_name: str | None = None,
    description: str | None = None,
) -> dict:
    """로컬 데이터셋을 Langfuse/LangSmith에 업로드

    Returns:
        {"langsmith_name": str | None, "langfuse_results": dict | None}
    """
    result: dict = {}

    if backend in ("langsmith", "both"):
        try:
            name = _upload_langsmith(
                prompt_name,
                targets_dir,
                datasets_dir,
                dataset_name,
                description,
            )
            result["langsmith_name"] = name
        except Exception as e:
            result["langsmith_error"] = str(e)
            print(f"✗ [LangSmith] 데이터셋 업로드 실패: {e}")

    if backend in ("langfuse", "both"):
        try:
            ds_name = dataset_name or prompt_name
            ds_results = _upload_langfuse_from_local(
                prompt_name,
                datasets_dir,
                ds_name,
                description,
            )
            result["langfuse_results"] = ds_results
        except Exception as e:
            result["langfuse_error"] = str(e)
            print(f"✗ [Langfuse] 데이터셋 업로드 실패: {e}")

    return result


def _upload_langsmith(
    prompt_name: str,
    targets_dir: str,
    datasets_dir: str,
    dataset_name: str | None,
    description: str | None,
) -> str:
    from langsmith import Client
    from src.loaders import load_evaluation_set

    data = load_evaluation_set(prompt_name, targets_dir, datasets_dir)

    if dataset_name is None:
        dataset_name = f"prompt-eval-{prompt_name}"

    client = Client()

    try:
        existing = client.read_dataset(dataset_name=dataset_name)
        print(f"기존 데이터셋 삭제: {dataset_name}")
        client.delete_dataset(dataset_id=existing.id)
    except Exception:
        pass

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description or f"Prompt evaluation dataset for {prompt_name}",
    )
    print(f"데이터셋 생성: {dataset_name}")

    examples = []
    for case in data["test_cases"]:
        case_id = case["id"]
        inputs = case["inputs"]
        expected_output = data["expected"].get(case_id, {})

        examples.append(
            {
                "inputs": inputs,
                "outputs": {
                    "reference": expected_output.get("reference", {}),
                    "keywords": expected_output.get("keywords", []),
                    "forbidden": expected_output.get("forbidden", []),
                },
                "metadata": {
                    "case_id": case_id,
                    "description": case.get("description", ""),
                },
            }
        )

    client.create_examples(
        inputs=[ex["inputs"] for ex in examples],
        outputs=[ex["outputs"] for ex in examples],
        metadata=[ex["metadata"] for ex in examples],
        dataset_id=dataset.id,
    )

    print(f"✓ [LangSmith] {len(examples)}개 테스트 케이스 업로드 완료")
    return dataset_name


def _upload_langfuse_from_local(
    prompt_name: str,
    datasets_dir: str,
    dataset_name: str,
    description: str | None,
) -> dict[str, bool]:
    data_dir = Path(datasets_dir) / prompt_name
    test_cases_path = data_dir / "test_cases.json"
    expected_path = data_dir / "expected.json"

    if not test_cases_path.exists():
        raise FileNotFoundError(f"test_cases.json 없음: {test_cases_path}")

    return upload_from_files(
        dataset_name=dataset_name,
        test_cases_path=test_cases_path,
        expected_path=expected_path,
        description=description or f"Prompt evaluation dataset for {prompt_name}",
    )


# ---------------------------------------------------------------------------
# Langfuse 전용 (하위 수준 API)
# ---------------------------------------------------------------------------


def create_dataset(name: str, description: Optional[str] = None) -> None:
    """Langfuse에 새 데이터셋 생성"""
    from utils.langfuse_client import get_langfuse_client

    client = get_langfuse_client()
    client.create_dataset(name=name, description=description)


def upload_dataset_item(
    dataset_name: str,
    input_data: dict,
    expected_output: Optional[dict] = None,
    metadata: Optional[dict] = None,
    item_id: Optional[str] = None,
) -> None:
    """데이터셋에 아이템 추가 (Langfuse)

    item_id를 지정하면 upsert 동작 (중복 방지)
    """
    from utils.langfuse_client import get_langfuse_client

    client = get_langfuse_client()
    kwargs = dict(
        dataset_name=dataset_name,
        input=input_data,
        expected_output=expected_output,
        metadata=metadata,
    )
    if item_id:
        kwargs["id"] = item_id
    client.create_dataset_item(**kwargs)


def get_dataset(name: str):
    """Langfuse에서 데이터셋 조회"""
    from utils.langfuse_client import get_langfuse_client

    client = get_langfuse_client()
    return client.get_dataset(name)


def upload_from_files(
    dataset_name: str,
    test_cases_path: str | Path,
    expected_path: str | Path,
    description: Optional[str] = None,
) -> dict[str, bool]:
    """test_cases.json + expected.json → Langfuse 데이터셋 업로드"""
    test_cases_path = Path(test_cases_path)
    expected_path = Path(expected_path)

    with open(test_cases_path, encoding="utf-8") as f:
        test_cases = json.load(f)

    expected = {}
    if expected_path.exists():
        with open(expected_path, encoding="utf-8") as f:
            expected = json.load(f)

    try:
        create_dataset(name=dataset_name, description=description)
    except Exception:
        pass

    results = {}
    for case in test_cases:
        case_id = case["id"]
        try:
            expected_data = expected.get(case_id, {})
            upload_dataset_item(
                dataset_name=dataset_name,
                input_data=case["inputs"],
                expected_output=expected_data,
                metadata={
                    "case_id": case_id,
                    "description": case.get("description", ""),
                },
                item_id=case_id,
            )
            results[case_id] = True
        except Exception as e:
            print(f"  ✗ {case_id} 실패: {e}")
            results[case_id] = False

    return results


def upload_all_datasets(datasets_dir: str | Path = "datasets") -> dict[str, dict]:
    """datasets 디렉토리의 모든 데이터셋을 Langfuse에 업로드"""
    datasets_dir = Path(datasets_dir)
    all_results = {}

    for dataset_path in datasets_dir.iterdir():
        if not dataset_path.is_dir():
            continue

        test_cases_file = dataset_path / "test_cases.json"
        expected_file = dataset_path / "expected.json"

        if not test_cases_file.exists():
            continue

        name = dataset_path.name
        print(f"  {name} 데이터셋 업로드 중...")

        try:
            results = upload_from_files(
                dataset_name=name,
                test_cases_path=test_cases_file,
                expected_path=expected_file,
            )
            success_count = sum(results.values())
            total_count = len(results)
            print(f"  ✓ {name}: {success_count}/{total_count} 케이스 업로드 완료")
            all_results[name] = results
        except Exception as e:
            print(f"  ✗ {name} 데이터셋 업로드 실패: {e}")
            all_results[name] = {"error": str(e)}

    return all_results
