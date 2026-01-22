"""결과 출력/저장

콘솔 출력, JSON 저장, 마크다운 리포트 생성
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def print_summary(result: dict[str, Any]) -> None:
    """평가 요약 출력"""
    summary = result["summary"]
    prompt_name = result["prompt_name"]
    mode = result["mode"]
    model = result.get("model", "unknown")

    print()
    print("=" * 60)
    print(f"평가 결과: {prompt_name}")
    print("=" * 60)
    print(f"  모드: {mode}")
    print(f"  모델: {model}")
    print(f"  시간: {result['timestamp']}")
    print()
    print(f"  총 케이스: {summary['total']}")
    print(f"  통과: {summary['passed']} ({summary['pass_rate']*100:.1f}%)")
    print(f"  실패: {summary['failed']}")
    avg_score = summary.get('avg_score')
    if avg_score is not None:
        print(f"  평균 점수: {avg_score:.3f}")
    print("=" * 60)


def print_case_details(result: dict[str, Any], verbose: bool = False) -> None:
    """케이스 상세 출력"""
    print()
    print("케이스 상세:")
    print("-" * 60)

    for case in result["cases"]:
        case_id = case["case_id"]
        eval_result = case["evaluation"]
        passed = eval_result["passed"]
        score = eval_result["overall_score"]
        status = "✓ PASS" if passed else "✗ FAIL"

        score_str = f"{score:.3f}" if score is not None else "-"
        print(f"\n[{case_id}] {status} (score: {score_str})")
        print(f"  설명: {case['description']}")
        print(f"  소요: {case['duration_ms']}ms")

        # 실패 사유
        if eval_result.get("fail_reason"):
            print(f"  실패 사유: {eval_result['fail_reason']}")

        # Sanity Checks
        sanity = eval_result.get("sanity_checks", {})
        if sanity.get("checks"):
            sanity_status = "✓" if sanity.get("all_passed") else "✗"
            print(f"  Sanity Checks: {sanity_status}")
            for check, detail in sanity["checks"].items():
                check_status = "✓" if detail["passed"] else "✗"
                print(f"    {check_status} {check}: {detail['details']}")

        # Score Breakdown
        breakdown = eval_result.get("score_breakdown", [])
        if breakdown:
            print(f"  Score Breakdown:")
            for item in breakdown:
                name = item["name"]
                item_score = item["score"]
                weight = item["weight"]
                print(f"    - {name}: {item_score:.3f} (weight: {weight})")

        # LLM Judge 상세 (체크리스트)
        scoring = eval_result.get("scoring", {})
        llm_judge = scoring.get("llm_judge", {})
        if llm_judge.get("criteria"):
            print(f"  LLM Judge 상세:")
            for criterion, detail in llm_judge["criteria"].items():
                if criterion == "overall":
                    continue
                if isinstance(detail, dict) and "checklist" in detail:
                    crit_status = "✓" if detail.get("passed") else "✗"
                    print(f"    {crit_status} {criterion}: {detail['score']:.2f}")
                    for check_item, check_passed in detail.get("checklist", {}).items():
                        item_status = "✓" if check_passed else "✗"
                        print(f"      {item_status} {check_item}")

        if verbose:
            print("  출력:")
            try:
                output_json = json.loads(case["output"])
                print(json.dumps(output_json, ensure_ascii=False, indent=4)[:500])
            except json.JSONDecodeError:
                print(f"    {case['output'][:500]}")

    print()


def print_failed_cases(result: dict[str, Any]) -> None:
    """실패한 케이스만 출력"""
    failed = [c for c in result["cases"] if not c["evaluation"]["passed"]]

    if not failed:
        print("\n모든 케이스 통과!")
        return

    print(f"\n실패한 케이스 ({len(failed)}개):")
    print("-" * 60)

    for case in failed:
        case_id = case["case_id"]
        eval_result = case["evaluation"]
        score = eval_result["overall_score"]
        fail_reason = eval_result.get("fail_reason", "unknown")

        score_str = f"{score:.3f}" if score is not None else "-"
        print(f"\n[{case_id}] score: {score_str}")
        print(f"  설명: {case['description']}")
        print(f"  실패 사유: {fail_reason}")

        # Sanity check 실패 상세
        sanity = eval_result.get("sanity_checks", {})
        if not sanity.get("all_passed"):
            print("  Sanity Check 실패:")
            for check, detail in sanity.get("checks", {}).items():
                if not detail["passed"]:
                    print(f"    ✗ {check}: {detail['details']}")
                    if "missing" in detail:
                        print(f"      누락: {detail['missing']}")
                    if "violations" in detail:
                        print(f"      위반: {detail['violations']}")

        # 점수 미달 시 breakdown 표시
        if "score_below_threshold" in fail_reason:
            print("  Score Breakdown:")
            for item in eval_result.get("score_breakdown", []):
                print(f"    - {item['name']}: {item['score']:.3f}")


def save_results(
    result: dict[str, Any],
    output_dir: str | Path = "results"
) -> Path:
    """결과를 JSON 파일로 저장"""
    output_dir = Path(output_dir) / result['prompt_name']
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{result['mode']}_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {filepath}")
    return filepath


def generate_markdown_report(
    result: dict[str, Any],
    output_dir: str | Path = "results"
) -> Path:
    """마크다운 리포트 생성"""
    output_dir = Path(output_dir) / result['prompt_name']
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = result["summary"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{result['mode']}_{timestamp}.md"
    filepath = output_dir / filename

    avg_score = summary.get('avg_score')
    avg_score_str = f"{avg_score:.3f}" if avg_score is not None else "-"

    lines = [
        f"# 평가 리포트: {result['prompt_name']}",
        "",
        f"- **모드**: {result['mode']}",
        f"- **모델**: {result.get('model', 'unknown')}",
        f"- **시간**: {result['timestamp']}",
        "",
        "## 요약",
        "",
        f"| 항목 | 값 |",
        f"|------|-----|",
        f"| 총 케이스 | {summary['total']} |",
        f"| 통과 | {summary['passed']} ({summary['pass_rate']*100:.1f}%) |",
        f"| 실패 | {summary['failed']} |",
        f"| 평균 점수 | {avg_score_str} |",
        "",
        "## 케이스 결과",
        "",
        "| ID | 설명 | 상태 | 점수 | 실패 사유 | 소요시간 |",
        "|-----|------|------|------|-----------|----------|",
    ]

    for case in result["cases"]:
        eval_result = case["evaluation"]
        status = "✓" if eval_result["passed"] else "✗"
        score = eval_result["overall_score"]
        score_str = f"{score:.2f}" if score is not None else "-"
        fail_reason = eval_result.get("fail_reason", "-") or "-"
        desc = case["description"][:25] + "..." if len(case["description"]) > 25 else case["description"]
        lines.append(
            f"| {case['case_id']} | {desc} | {status} | {score_str} | {fail_reason} | {case['duration_ms']}ms |"
        )

    failed = [c for c in result["cases"] if not c["evaluation"]["passed"]]
    if failed:
        lines.extend(["", "## 실패 케이스 상세", ""])

        for case in failed:
            eval_result = case["evaluation"]
            lines.append(f"### {case['case_id']}")
            lines.append("")
            lines.append(f"**설명**: {case['description']}")
            lines.append(f"**실패 사유**: {eval_result.get('fail_reason', 'unknown')}")
            lines.append("")

            # Sanity Checks
            sanity = eval_result.get("sanity_checks", {})
            if sanity.get("checks"):
                lines.append("**Sanity Checks**:")
                for check, detail in sanity["checks"].items():
                    status = "✓" if detail["passed"] else "✗"
                    lines.append(f"- {status} {check}: {detail['details']}")
                lines.append("")

            # Score Breakdown
            breakdown = eval_result.get("score_breakdown", [])
            if breakdown:
                lines.append("**Score Breakdown**:")
                lines.append("")
                lines.append("| 평가 항목 | 점수 | 가중치 |")
                lines.append("|-----------|------|--------|")
                for item in breakdown:
                    lines.append(f"| {item['name']} | {item['score']:.3f} | {item['weight']} |")
                lines.append("")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"리포트 저장: {filepath}")
    return filepath
