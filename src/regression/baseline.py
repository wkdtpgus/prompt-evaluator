"""기준선(Baseline) 관리 모듈

프롬프트 버전별 평가 결과를 기준선으로 저장하고 로드합니다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langsmith import Client


BASELINES_DIR = Path("results/baselines")
RESULTS_DIR = Path("results/experiments")


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


# ============================================================
# 실험 결과 로컬 저장/로드 (Langfuse 등)
# ============================================================


def save_experiment_result(
    prompt_name: str,
    experiment_result: dict,
    experiment_name: Optional[str] = None,
) -> Path:
    """실험 결과를 로컬에 저장

    Args:
        prompt_name: 프롬프트 이름
        experiment_result: 실험 결과 딕셔너리
        experiment_name: 실험 이름 (None이면 결과에서 추출)

    Returns:
        저장된 파일 경로
    """
    exp_name = experiment_name or experiment_result.get("experiment_name", "unknown")

    result_dir = RESULTS_DIR / prompt_name
    result_dir.mkdir(parents=True, exist_ok=True)

    # 개별 실험 결과 저장
    result_path = result_dir / f"{exp_name}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(experiment_result, f, ensure_ascii=False, indent=2)

    # latest.json도 동시 저장
    latest_path = result_dir / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(experiment_result, f, ensure_ascii=False, indent=2)

    return result_path


def load_latest_experiment(prompt_name: str) -> dict | None:
    """최신 실험 결과 로드

    Args:
        prompt_name: 프롬프트 이름

    Returns:
        실험 결과 딕셔너리 또는 None
    """
    latest_path = RESULTS_DIR / prompt_name / "latest.json"
    if not latest_path.exists():
        return None

    with open(latest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_experiment_result(prompt_name: str, experiment_name: str) -> dict | None:
    """특정 실험 결과 로드

    Args:
        prompt_name: 프롬프트 이름
        experiment_name: 실험 이름

    Returns:
        실험 결과 딕셔너리 또는 None
    """
    result_path = RESULTS_DIR / prompt_name / f"{experiment_name}.json"
    if not result_path.exists():
        return None

    with open(result_path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_experiment_to_baseline(experiment_result: dict) -> dict:
    """로컬 실험 결과를 baseline 비교 형식으로 정규화

    Langfuse 실험 결과 형식 → baseline compare_results() 호환 형식 변환

    Args:
        experiment_result: 실험 결과 (run_experiment의 반환값)

    Returns:
        baseline 호환 딕셔너리 {"version", "results": {"summary", "cases"}}
    """
    summary = experiment_result.get("summary", {})
    results = experiment_result.get("results", [])

    cases = []
    for r in results:
        scores = r.get("scores", {})
        # scores → feedback_stats 형식 변환
        feedback_stats = {}
        for name, value in scores.items():
            feedback_stats[name] = {"avg": value}

        cases.append({
            "case_id": r.get("case_id", ""),
            "inputs": {},
            "outputs": {"output": r.get("output", "")},
            "feedback_stats": feedback_stats,
            "passed": r.get("passed", False),
        })

    return {
        "version": "current",
        "results": {
            "summary": summary,
            "cases": cases,
        },
    }


def set_baseline_from_local(
    prompt_name: str,
    experiment_file: Optional[str] = None,
    version: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """로컬 실험 결과에서 baseline 생성

    Args:
        prompt_name: 프롬프트 이름
        experiment_file: 실험 결과 파일명 (None이면 latest.json)
        version: 버전 태그 (None이면 .metadata.yaml의 current_version)
        metadata: 추가 메타데이터

    Returns:
        저장된 baseline 파일 경로

    Raises:
        FileNotFoundError: 실험 결과 파일이 없는 경우
    """
    if experiment_file:
        experiment = load_experiment_result(prompt_name, experiment_file)
    else:
        experiment = load_latest_experiment(prompt_name)

    if experiment is None:
        raise FileNotFoundError(
            f"실험 결과를 찾을 수 없습니다: {prompt_name} "
            f"({'latest' if not experiment_file else experiment_file})"
        )

    # baseline 형식으로 변환
    normalized = normalize_experiment_to_baseline(experiment)

    return save_baseline(
        prompt_name,
        experiment_results=normalized["results"],
        version=version,
        metadata=metadata,
    )
