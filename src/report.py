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
    print(f"  평균 점수: {summary['avg_score']:.3f}")
    print("=" * 60)


def print_case_details(result: dict[str, Any], verbose: bool = False) -> None:
    """케이스 상세 출력"""
    print()
    print("케이스 상세:")
    print("-" * 60)

    for case in result["cases"]:
        case_id = case["case_id"]
        passed = case["evaluation"]["passed"]
        score = case["evaluation"]["overall_score"]
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\n[{case_id}] {status} (score: {score:.3f})")
        print(f"  설명: {case['description']}")
        print(f"  소요: {case['duration_ms']}ms")

        eval_result = case["evaluation"]

        if "rule_based" in eval_result:
            print("  Rule-based:")
            for check, result_detail in eval_result["rule_based"].items():
                check_status = "✓" if result_detail["passed"] else "✗"
                print(f"    {check_status} {check}: {result_detail['details']}")

        if "string_distance" in eval_result:
            sd = eval_result["string_distance"]
            sd_status = "✓" if sd["passed"] else "✗"
            print(f"  String Distance: {sd_status} {sd['details']}")

        if "llm_judge" in eval_result and not eval_result["llm_judge"].get("error"):
            print("  LLM Judge:")
            for criterion, result_detail in eval_result["llm_judge"].items():
                if isinstance(result_detail, dict) and "score" in result_detail:
                    crit_status = "✓" if result_detail["passed"] else "✗"
                    print(f"    {crit_status} {criterion}: {result_detail['score']:.2f}")

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
        score = case["evaluation"]["overall_score"]
        print(f"\n[{case_id}] score: {score:.3f}")
        print(f"  설명: {case['description']}")

        eval_result = case["evaluation"]
        if "rule_based" in eval_result:
            for check, detail in eval_result["rule_based"].items():
                if not detail["passed"]:
                    print(f"  ✗ {check}: {detail['details']}")
                    if "missing" in detail:
                        print(f"    누락: {detail['missing']}")
                    if "violations" in detail:
                        print(f"    위반: {detail['violations']}")


def save_results(
    result: dict[str, Any],
    output_dir: str | Path = "results"
) -> Path:
    """결과를 JSON 파일로 저장"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{result['prompt_name']}_{result['mode']}_{timestamp}.json"
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
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = result["summary"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{result['prompt_name']}_{result['mode']}_{timestamp}.md"
    filepath = output_dir / filename

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
        f"| 평균 점수 | {summary['avg_score']:.3f} |",
        "",
        "## 케이스 결과",
        "",
        "| ID | 설명 | 상태 | 점수 | 소요시간 |",
        "|-----|------|------|------|----------|",
    ]

    for case in result["cases"]:
        status = "✓" if case["evaluation"]["passed"] else "✗"
        score = case["evaluation"]["overall_score"]
        desc = case["description"][:30] + "..." if len(case["description"]) > 30 else case["description"]
        lines.append(
            f"| {case['case_id']} | {desc} | {status} | {score:.2f} | {case['duration_ms']}ms |"
        )

    failed = [c for c in result["cases"] if not c["evaluation"]["passed"]]
    if failed:
        lines.extend(["", "## 실패 케이스 상세", ""])

        for case in failed:
            lines.append(f"### {case['case_id']}")
            lines.append(f"")
            lines.append(f"**설명**: {case['description']}")
            lines.append(f"")

            eval_result = case["evaluation"]
            if "rule_based" in eval_result:
                lines.append("**Rule-based 검사**:")
                for check, detail in eval_result["rule_based"].items():
                    status = "✓" if detail["passed"] else "✗"
                    lines.append(f"- {status} {check}: {detail['details']}")
            lines.append("")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"리포트 저장: {filepath}")
    return filepath
