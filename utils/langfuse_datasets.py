"""
Langfuse 데이터셋 관리 유틸리티

데이터셋 생성, 업로드, 조회 기능 제공
"""

import json
from pathlib import Path
from typing import Optional

from utils.langfuse_client import get_langfuse_client


def create_dataset(name: str, description: Optional[str] = None) -> None:
    """
    Langfuse에 새 데이터셋 생성

    Args:
        name: 데이터셋 이름
        description: 데이터셋 설명
    """
    client = get_langfuse_client()
    client.create_dataset(name=name, description=description)


def upload_dataset_item(
    dataset_name: str,
    input_data: dict,
    expected_output: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    데이터셋에 아이템 추가

    Args:
        dataset_name: 데이터셋 이름
        input_data: 입력 데이터
        expected_output: 기대 출력
        metadata: 추가 메타데이터
    """
    client = get_langfuse_client()
    client.create_dataset_item(
        dataset_name=dataset_name,
        input=input_data,
        expected_output=expected_output,
        metadata=metadata,
    )


def get_dataset(name: str):
    """
    Langfuse에서 데이터셋 조회

    Args:
        name: 데이터셋 이름

    Returns:
        데이터셋 객체 (items 속성으로 아이템 접근)
    """
    client = get_langfuse_client()
    return client.get_dataset(name)


def upload_from_files(
    dataset_name: str,
    test_cases_path: str | Path,
    expected_path: str | Path,
    description: Optional[str] = None,
) -> dict[str, bool]:
    """
    기존 test_cases.json + expected.json 파일에서 데이터셋 업로드

    Args:
        dataset_name: 생성할 데이터셋 이름
        test_cases_path: test_cases.json 파일 경로
        expected_path: expected.json 파일 경로
        description: 데이터셋 설명

    Returns:
        {case_id: 성공여부} 딕셔너리
    """
    test_cases_path = Path(test_cases_path)
    expected_path = Path(expected_path)

    # 파일 로드
    with open(test_cases_path, encoding="utf-8") as f:
        test_cases = json.load(f)
    with open(expected_path, encoding="utf-8") as f:
        expected = json.load(f)

    # 데이터셋 생성 (이미 존재하면 무시)
    try:
        create_dataset(name=dataset_name, description=description)
    except Exception:
        pass  # 이미 존재하는 경우

    results = {}
    for case in test_cases:
        case_id = case["id"]
        try:
            # expected에서 해당 케이스 정보 가져오기
            expected_data = expected.get(case_id, {})

            upload_dataset_item(
                dataset_name=dataset_name,
                input_data=case["inputs"],
                expected_output=expected_data,
                metadata={
                    "case_id": case_id,
                    "description": case.get("description", ""),
                },
            )
            results[case_id] = True
        except Exception as e:
            print(f"  ✗ {case_id} 실패: {e}")
            results[case_id] = False

    return results


def upload_all_datasets(datasets_dir: str | Path = "datasets") -> dict[str, dict]:
    """
    datasets 디렉토리의 모든 데이터셋을 Langfuse에 업로드

    Args:
        datasets_dir: datasets 디렉토리 경로

    Returns:
        {데이터셋명: {case_id: 성공여부}} 딕셔너리
    """
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
        print(f"📦 {name} 데이터셋 업로드 중...")

        # expected.json이 없으면 빈 딕셔너리로 처리
        if not expected_file.exists():
            expected_file = None

        try:
            if expected_file:
                results = upload_from_files(
                    dataset_name=name,
                    test_cases_path=test_cases_file,
                    expected_path=expected_file,
                )
            else:
                # expected 없이 업로드
                with open(test_cases_file, encoding="utf-8") as f:
                    test_cases = json.load(f)

                try:
                    create_dataset(name=name)
                except Exception:
                    pass

                results = {}
                for case in test_cases:
                    case_id = case["id"]
                    try:
                        upload_dataset_item(
                            dataset_name=name,
                            input_data=case["inputs"],
                            metadata={
                                "case_id": case_id,
                                "description": case.get("description", ""),
                            },
                        )
                        results[case_id] = True
                    except Exception as e:
                        print(f"  ✗ {case_id} 실패: {e}")
                        results[case_id] = False

            success_count = sum(results.values())
            total_count = len(results)
            print(f"  ✓ {name}: {success_count}/{total_count} 케이스 업로드 완료")
            all_results[name] = results

        except Exception as e:
            print(f"  ✗ {name} 데이터셋 업로드 실패: {e}")
            all_results[name] = {"error": str(e)}

    return all_results
