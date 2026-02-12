"""버전별 결과 비교 모듈

기준선과 새 결과를 비교하여 회귀 여부를 판단합니다.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RegressionReport:
    """회귀 테스트 결과 리포트"""

    prompt_name: str
    baseline_version: str
    current_version: str

    # 요약 통계
    baseline_pass_rate: float
    current_pass_rate: float
    pass_rate_delta: float  # current - baseline (음수면 성능 저하)

    baseline_avg_score: Optional[float]
    current_avg_score: Optional[float]
    avg_score_delta: Optional[float]

    # 회귀 판단
    has_regression: bool
    regression_threshold: float = 0.05  # 5% 이상 저하 시 회귀로 판단

    # 상세 비교
    case_regressions: list[dict] = field(default_factory=list)  # 개별 케이스 회귀
    new_failures: list[str] = field(default_factory=list)  # 새로 실패한 케이스
    fixed_cases: list[str] = field(default_factory=list)  # 새로 통과한 케이스

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "prompt_name": self.prompt_name,
            "baseline_version": self.baseline_version,
            "current_version": self.current_version,
            "baseline_pass_rate": self.baseline_pass_rate,
            "current_pass_rate": self.current_pass_rate,
            "pass_rate_delta": self.pass_rate_delta,
            "baseline_avg_score": self.baseline_avg_score,
            "current_avg_score": self.current_avg_score,
            "avg_score_delta": self.avg_score_delta,
            "has_regression": self.has_regression,
            "regression_threshold": self.regression_threshold,
            "case_regressions": self.case_regressions,
            "new_failures": self.new_failures,
            "fixed_cases": self.fixed_cases,
        }


def compare_results(
    baseline: dict,
    current: dict,
    threshold: float = 0.05,
) -> RegressionReport:
    """기준선과 현재 결과 비교

    Args:
        baseline: 기준선 데이터 (load_baseline 결과)
        current: 현재 실험 결과
        threshold: 회귀 판단 임계값 (기본 5%)

    Returns:
        RegressionReport 객체
    """
    prompt_name = baseline.get("prompt_name", "unknown")
    baseline_version = baseline.get("version", "unknown")
    current_version = current.get("version", "current")

    # 요약 통계 추출
    baseline_summary = baseline.get("results", {}).get("summary", {})
    current_summary = current.get("results", {}).get("summary", {})

    baseline_pass_rate = baseline_summary.get("pass_rate", 0.0)
    current_pass_rate = current_summary.get("pass_rate", 0.0)
    pass_rate_delta = current_pass_rate - baseline_pass_rate

    baseline_avg_score = baseline_summary.get("avg_score")
    current_avg_score = current_summary.get("avg_score")
    avg_score_delta = None
    if baseline_avg_score is not None and current_avg_score is not None:
        avg_score_delta = current_avg_score - baseline_avg_score

    # 회귀 판단 (pass_rate이 threshold 이상 하락 시)
    has_regression = pass_rate_delta < -threshold

    # 케이스별 비교
    baseline_cases = {
        _get_case_key(c): c
        for c in baseline.get("results", {}).get("cases", [])
    }
    current_cases = {
        _get_case_key(c): c
        for c in current.get("results", {}).get("cases", [])
    }

    case_regressions = []
    new_failures = []
    fixed_cases = []

    # 기준선에 있던 케이스들 비교
    for key, baseline_case in baseline_cases.items():
        current_case = current_cases.get(key)
        if current_case is None:
            continue

        baseline_passed = baseline_case.get("passed", True)
        current_passed = current_case.get("passed", True)

        if baseline_passed and not current_passed:
            # 원래 통과했는데 이제 실패 = 회귀
            new_failures.append(key)
            case_regressions.append({
                "case_key": key,
                "type": "new_failure",
                "baseline_passed": True,
                "current_passed": False,
            })
        elif not baseline_passed and current_passed:
            # 원래 실패했는데 이제 통과 = 개선
            fixed_cases.append(key)

    return RegressionReport(
        prompt_name=prompt_name,
        baseline_version=baseline_version,
        current_version=current_version,
        baseline_pass_rate=baseline_pass_rate,
        current_pass_rate=current_pass_rate,
        pass_rate_delta=pass_rate_delta,
        baseline_avg_score=baseline_avg_score,
        current_avg_score=current_avg_score,
        avg_score_delta=avg_score_delta,
        has_regression=has_regression,
        regression_threshold=threshold,
        case_regressions=case_regressions,
        new_failures=new_failures,
        fixed_cases=fixed_cases,
    )


def _get_case_key(case: dict) -> str:
    """케이스 식별 키 생성

    run_id, case_id, 또는 inputs 해시를 사용
    """
    if "case_id" in case:
        return case["case_id"]
    if "run_id" in case:
        return case["run_id"]
    if "inputs" in case:
        # inputs를 문자열로 변환하여 키로 사용
        import json
        return json.dumps(case["inputs"], sort_keys=True)
    return str(id(case))


def format_regression_report(report: RegressionReport) -> str:
    """회귀 리포트를 읽기 쉬운 문자열로 포맷

    Args:
        report: RegressionReport 객체

    Returns:
        포맷된 문자열
    """
    lines = []
    lines.append(f"회귀 테스트 리포트: {report.prompt_name}")
    lines.append("=" * 60)
    lines.append(f"비교: {report.baseline_version} → {report.current_version}")
    lines.append("")

    # 요약
    lines.append("[요약]")
    delta_symbol = "↑" if report.pass_rate_delta >= 0 else "↓"
    lines.append(
        f"  Pass Rate: {report.baseline_pass_rate:.1%} → {report.current_pass_rate:.1%} "
        f"({delta_symbol}{abs(report.pass_rate_delta):.1%})"
    )

    if report.baseline_avg_score is not None and report.current_avg_score is not None:
        score_delta_symbol = "↑" if report.avg_score_delta >= 0 else "↓"
        lines.append(
            f"  Avg Score: {report.baseline_avg_score:.3f} → {report.current_avg_score:.3f} "
            f"({score_delta_symbol}{abs(report.avg_score_delta):.3f})"
        )

    lines.append("")

    # 회귀 판단
    if report.has_regression:
        lines.append("⚠️  회귀 감지됨!")
        lines.append(f"  (임계값: {report.regression_threshold:.0%} 이상 성능 저하)")
    else:
        lines.append("✅ 회귀 없음")

    # 케이스별 변경
    if report.new_failures:
        lines.append("")
        lines.append(f"[새로 실패한 케이스] ({len(report.new_failures)}개)")
        for case in report.new_failures[:5]:
            lines.append(f"  • {case}")
        if len(report.new_failures) > 5:
            lines.append(f"  ... 외 {len(report.new_failures) - 5}개")

    if report.fixed_cases:
        lines.append("")
        lines.append(f"[개선된 케이스] ({len(report.fixed_cases)}개)")
        for case in report.fixed_cases[:5]:
            lines.append(f"  • {case}")
        if len(report.fixed_cases) > 5:
            lines.append(f"  ... 외 {len(report.fixed_cases) - 5}개")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
