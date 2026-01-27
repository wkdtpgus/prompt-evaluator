"""기준선(Baseline) 관리 모듈

프롬프트 버전별 평가 결과를 기준선으로 저장하고 로드합니다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langsmith import Client


BASELINES_DIR = Path("results/baselines")


def get_baseline_path(prompt_name: str, version: Optional[str] = None) -> Path:
    """기준선 파일 경로 반환

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그 (None이면 "latest")

    Returns:
        기준선 파일 경로
    """
    version_tag = version or "latest"
    return BASELINES_DIR / prompt_name / f"{version_tag}.json"


def save_baseline(
    prompt_name: str,
    experiment_results: dict,
    version: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """평가 결과를 기준선으로 저장

    Args:
        prompt_name: 프롬프트 이름
        experiment_results: LangSmith experiment 결과 (또는 로컬 pipeline 결과)
        version: 버전 태그
        metadata: 추가 메타데이터 (author, changes 등)

    Returns:
        저장된 파일 경로
    """
    baseline_path = get_baseline_path(prompt_name, version)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_data = {
        "prompt_name": prompt_name,
        "version": version or "latest",
        "created_at": datetime.now().isoformat(),
        "metadata": metadata or {},
        "results": experiment_results,
    }

    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f, ensure_ascii=False, indent=2)

    return baseline_path


def load_baseline(
    prompt_name: str,
    version: Optional[str] = None,
) -> dict | None:
    """기준선 로드

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그 (None이면 "latest")

    Returns:
        기준선 데이터 또는 None
    """
    baseline_path = get_baseline_path(prompt_name, version)

    if not baseline_path.exists():
        return None

    with open(baseline_path, "r", encoding="utf-8") as f:
        return json.load(f)


def set_as_baseline(
    prompt_name: str,
    experiment_name: str,
    version: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """LangSmith 실험 결과를 기준선으로 설정

    Args:
        prompt_name: 프롬프트 이름
        experiment_name: LangSmith 실험 이름
        version: 버전 태그
        metadata: 추가 메타데이터

    Returns:
        저장된 기준선 파일 경로
    """
    client = Client()

    # LangSmith에서 실험 결과 가져오기
    project = client.read_project(project_name=experiment_name)

    # 실험 실행 결과 수집
    runs = list(client.list_runs(project_name=experiment_name))

    results = {
        "experiment_name": experiment_name,
        "project_id": str(project.id),
        "total_runs": len(runs),
        "summary": _compute_summary_from_runs(runs),
        "cases": _extract_case_results(runs),
    }

    return save_baseline(prompt_name, results, version, metadata)


def _compute_summary_from_runs(runs: list) -> dict:
    """실행 결과에서 요약 통계 계산"""
    if not runs:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

    # 피드백에서 점수 추출
    scores = []
    for run in runs:
        if run.feedback_stats:
            for key, stats in run.feedback_stats.items():
                if "avg" in stats:
                    scores.append(stats["avg"])

    total = len(runs)
    # 실패 기준: 평균 점수 0.5 미만
    passed = sum(1 for run in runs if _is_run_passed(run))

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else None,
    }


def _is_run_passed(run) -> bool:
    """실행이 통과했는지 판단"""
    if not run.feedback_stats:
        return True  # 피드백 없으면 통과로 간주

    for key, stats in run.feedback_stats.items():
        if "avg" in stats and stats["avg"] < 0.5:
            return False
    return True


def _extract_case_results(runs: list) -> list[dict]:
    """실행 결과에서 케이스별 결과 추출"""
    case_results = []
    for run in runs:
        case_data = {
            "run_id": str(run.id),
            "inputs": run.inputs,
            "outputs": run.outputs,
            "feedback_stats": run.feedback_stats,
            "passed": _is_run_passed(run),
        }
        case_results.append(case_data)
    return case_results


def list_baselines(prompt_name: str) -> list[dict]:
    """프롬프트의 모든 기준선 목록 조회

    Args:
        prompt_name: 프롬프트 이름

    Returns:
        기준선 정보 목록 [{version, created_at, pass_rate}, ...]
    """
    baseline_dir = BASELINES_DIR / prompt_name
    if not baseline_dir.exists():
        return []

    baselines = []
    for file in baseline_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                baselines.append({
                    "version": data.get("version"),
                    "created_at": data.get("created_at"),
                    "pass_rate": data.get("results", {}).get("summary", {}).get("pass_rate"),
                    "file": str(file),
                })
        except (json.JSONDecodeError, IOError):
            continue

    # 최신순 정렬
    baselines.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return baselines


def delete_baseline(prompt_name: str, version: str) -> bool:
    """기준선 삭제

    Args:
        prompt_name: 프롬프트 이름
        version: 버전 태그

    Returns:
        삭제 성공 여부
    """
    baseline_path = get_baseline_path(prompt_name, version)
    if baseline_path.exists():
        baseline_path.unlink()
        return True
    return False
