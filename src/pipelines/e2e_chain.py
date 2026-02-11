"""E2E 파이프라인 평가

2-phase chain 파이프라인의 정보 보존을 블랙박스로 검증합니다.
chat_history → Phase 1(analyze) → Phase 2(questions) → 최종 출력만 평가

세 가지 모드:
1. 로컬 모드: run_e2e_pipeline() - 빠른 개발/테스트
2. Langfuse 모드: run_e2e_langfuse_experiment() - Langfuse 트레이싱
3. LangSmith 모드: run_e2e_langsmith_experiment() - LangSmith 트레이싱

개별 노드 품질은 기존 단독 테스트가 담당:
- prep_output_analyze: question_context 품질
- prep_output_questions: questions + guide 품질
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from langsmith import traceable
from langsmith.evaluation import evaluate

# Langfuse imports (lazy)
try:
    from utils.langfuse_client import (
        get_langfuse_client,
        get_langfuse_handler,
        flush as langfuse_flush,
    )
    from utils.dataset_sync import upload_from_files, get_dataset

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

from src.loaders.prompt_loader import find_prompt_file, load_prompt_file
from src.pipelines.pipeline import execute_prompt, run_evaluation, RunMode
from src.evaluators.adapters import (
    create_langfuse_evaluator,
    create_langsmith_evaluator,
)
from utils.models import execution_llm


def chat_history_to_qa_pairs(chat_history: list[dict]) -> list[dict]:
    """chat_history를 qa_pairs 형식으로 변환

    Production API의 chat_history [{role, content}]를
    Phase 1 프롬프트의 qa_pairs [{bot_question, member_response}]로 변환.

    assistant → bot_question, user → member_response 쌍으로 매칭.
    """
    qa_pairs = []
    i = 0
    while i < len(chat_history):
        msg = chat_history[i]
        if msg["role"] == "assistant" and i + 1 < len(chat_history):
            next_msg = chat_history[i + 1]
            if next_msg["role"] == "user":
                qa_pairs.append(
                    {
                        "bot_question": msg["content"],
                        "member_response": next_msg["content"],
                    }
                )
                i += 2
                continue
        i += 1
    return qa_pairs


def load_phase_templates(
    chain_config: dict,
    targets_dir: Path = Path("targets"),
) -> tuple[str, str]:
    """Phase 1, Phase 2 템플릿 직접 로드

    config.yaml의 chain 설정에서 phase1/phase2 타겟명을 읽어
    각각의 프롬프트 변수를 prompt_loader로 직접 선택합니다.
    (_extract_template 우회)

    Returns:
        (phase1_template, phase2_template)
    """
    phase1_name = chain_config["phase1"]
    phase2_name = chain_config["phase2"]

    # Phase 1: ANALYZE_SYSTEM_PROMPT + ANALYZE_USER_PROMPT
    phase1_file = find_prompt_file(phase1_name, targets_dir)
    phase1_prompts = load_prompt_file(phase1_file)
    phase1_template = (
        phase1_prompts["ANALYZE_SYSTEM_PROMPT"]
        + "\n\n"
        + phase1_prompts["ANALYZE_USER_PROMPT"]
    )

    # Phase 2: SYSTEM_PROMPT + USER_PROMPT
    phase2_file = find_prompt_file(phase2_name, targets_dir)
    phase2_prompts = load_prompt_file(phase2_file)
    phase2_template = (
        phase2_prompts["SYSTEM_PROMPT"] + "\n\n" + phase2_prompts["USER_PROMPT"]
    )

    return phase1_template, phase2_template


def _extract_json(text: str) -> dict:
    """LLM 출력에서 JSON 추출"""
    # 1. ```json ... ``` 블록
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    # 2. ``` ... ``` 블록
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    # 3. 순수 JSON
    return json.loads(text.strip())


@traceable(name="e2e_evaluate_case")
def evaluate_e2e_case(
    phase1_template: str,
    phase2_template: str,
    test_case: dict,
    expected: dict,
    mode: RunMode = "full",
    eval_config: dict | None = None,
) -> dict[str, Any]:
    """단일 E2E 케이스 평가

    1. chat_history → qa_pairs 변환
    2. Phase 1 실행 → question_context JSON 파싱
    3. Phase 2 실행 → 최종 출력
    4. 정보 보존 평가 (원본 입력 vs 최종 출력)
    """
    start = time.time()

    case_id = test_case.get("id", "unknown")
    inputs = test_case.get("inputs", {})

    # 1. chat_history → qa_pairs 변환
    chat_history = inputs.get("chat_history", [])
    qa_pairs = chat_history_to_qa_pairs(chat_history)

    # 2. Phase 1 실행
    phase1_inputs = {
        "qa_pairs_json": qa_pairs,
        "survey_answers_json": inputs.get("survey_answers", {}),
        "language": inputs.get("language", "ko-KR"),
    }
    phase1_output = execute_prompt(phase1_template, phase1_inputs)

    # 3. Phase 1 JSON 파싱
    try:
        phase1_json = _extract_json(phase1_output)
        question_context = phase1_json.get("question_context", [])
    except (json.JSONDecodeError, ValueError) as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "case_id": case_id,
            "description": test_case.get("description", ""),
            "phase1_output": phase1_output,
            "output": "",
            "evaluation": {
                "sanity_checks": {"checks": {}, "all_passed": False},
                "scoring": {},
                "score_breakdown": [],
                "overall_score": 0.0,
                "min_score": None,
                "passed": False,
                "fail_reason": f"phase1_json_parse_error: {e}",
            },
            "duration_ms": duration_ms,
        }

    # 4. Phase 2 실행
    phase2_inputs = {
        "question_context_json": question_context,
        "profile_card_json": inputs.get("profile_card", {}),
        "member_name": inputs.get("member_name", ""),
        "language": inputs.get("language", "ko-KR"),
    }
    phase2_output = execute_prompt(phase2_template, phase2_inputs)

    # 5. 정보 보존 평가
    # inputs로 원본 대화 전달 → eval 프롬프트의 {input}에 삽입됨
    eval_inputs = {
        "chat_history": chat_history,
        "survey_answers": inputs.get("survey_answers", {}),
        "member_name": inputs.get("member_name", ""),
    }

    evaluation = run_evaluation(
        output=phase2_output,
        expected=expected,
        inputs=eval_inputs,
        mode=mode,
        eval_config=eval_config,
    )

    duration_ms = int((time.time() - start) * 1000)

    return {
        "case_id": case_id,
        "description": test_case.get("description", ""),
        "phase1_output": phase1_output,
        "output": phase2_output,
        "evaluation": evaluation,
        "duration_ms": duration_ms,
    }


def run_e2e_pipeline(
    prompt_name: str = "prep_output",
    mode: RunMode = "full",
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    """E2E 파이프라인 평가 실행

    Args:
        prompt_name: E2E 타겟 이름 (chain config 포함)
        mode: 실행 모드 (quick/full)
        case_ids: 특정 케이스만 실행 (None이면 전체)

    Returns:
        run_pipeline()과 동일한 형식의 결과
    """
    targets_dir = Path("targets")
    datasets_dir = Path("datasets")

    # 1. Config 로드
    config_file = targets_dir / prompt_name / "config.yaml"
    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    chain_config = eval_config.get("chain", {})
    if not chain_config:
        raise ValueError(f"chain 설정이 없습니다: {config_file}")

    # 2. Phase 1/2 템플릿 로드
    phase1_template, phase2_template = load_phase_templates(chain_config, targets_dir)

    # 3. 테스트 데이터 로드
    data_dir = datasets_dir / prompt_name
    with open(data_dir / "test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected_all = json.load(f)

    # 4. 케이스 필터링
    if case_ids:
        test_cases = [tc for tc in test_cases if tc.get("id") in case_ids]

    # 5. 각 케이스 실행
    print(f"\n{'=' * 60}")
    print(f"E2E Pipeline: {prompt_name}")
    print(f"  Phase 1: {chain_config['phase1']}")
    print(f"  Phase 2: {chain_config['phase2']}")
    print(f"  Mode: {mode}")
    print(f"  Cases: {len(test_cases)}")
    print(f"{'=' * 60}")

    results = []
    for test_case in test_cases:
        case_id = test_case.get("id", "unknown")
        expected = expected_all.get(case_id, {})

        desc = test_case.get("description", "")[:50]
        print(f"  [{case_id}] {desc}...", end=" ")

        result = evaluate_e2e_case(
            phase1_template=phase1_template,
            phase2_template=phase2_template,
            test_case=test_case,
            expected=expected,
            mode=mode,
            eval_config=eval_config,
        )

        status = "PASS" if result["evaluation"]["passed"] else "FAIL"
        score = result["evaluation"]["overall_score"]
        score_str = f"{score:.2f}" if score is not None else "-"
        print(f"{status} ({score_str}) [{result['duration_ms']}ms]")

        results.append(result)

    # 6. 요약
    total = len(results)
    passed = sum(1 for r in results if r["evaluation"]["passed"])
    scores = [
        r["evaluation"]["overall_score"]
        for r in results
        if r["evaluation"]["overall_score"] is not None
    ]

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "avg_score": sum(scores) / len(scores) if scores else None,
    }

    print(f"\n{'=' * 60}")
    print(f"Result: {passed}/{total} passed ({summary['pass_rate']:.1%})")
    if summary["avg_score"] is not None:
        print(f"Avg Score: {summary['avg_score']:.3f}")
    print(f"{'=' * 60}")

    return {
        "prompt_name": prompt_name,
        "pipeline_type": "chain",
        "mode": mode,
        "model": execution_llm.model_name,
        "timestamp": datetime.now().isoformat(),
        "cases": results,
        "summary": summary,
    }


# ============================================================
# Langfuse Experiment 모드
# ============================================================


def _run_e2e_chain(
    phase1_template: str,
    phase2_template: str,
    inputs: dict,
    callbacks: list | None = None,
) -> dict[str, str]:
    """E2E 체인 실행 (Phase 1 → Phase 2)

    Args:
        callbacks: LangChain 콜백 핸들러 목록 (Langfuse 트레이싱 등)

    Returns:
        {"output": phase2_output, "phase1_output": phase1_output}
    """
    # 1. chat_history → qa_pairs
    chat_history = inputs.get("chat_history", [])
    qa_pairs = chat_history_to_qa_pairs(chat_history)

    # 2. Phase 1
    phase1_inputs = {
        "qa_pairs_json": qa_pairs,
        "survey_answers_json": inputs.get("survey_answers", {}),
        "language": inputs.get("language", "ko-KR"),
    }
    phase1_output = execute_prompt(phase1_template, phase1_inputs, callbacks=callbacks)

    # 3. Phase 1 JSON 파싱
    try:
        phase1_json = _extract_json(phase1_output)
        question_context = phase1_json.get("question_context", [])
    except (json.JSONDecodeError, ValueError):
        return {
            "output": "",
            "phase1_output": phase1_output,
            "error": "phase1_json_parse_error",
        }

    # 4. Phase 2
    phase2_inputs = {
        "question_context_json": question_context,
        "profile_card_json": inputs.get("profile_card", {}),
        "member_name": inputs.get("member_name", ""),
        "language": inputs.get("language", "ko-KR"),
    }
    phase2_output = execute_prompt(phase2_template, phase2_inputs, callbacks=callbacks)

    return {"output": phase2_output, "phase1_output": phase1_output}


def run_e2e_langfuse_experiment(
    prompt_name: str = "prep_output",
    mode: RunMode = "full",
    experiment_prefix: str | None = None,
) -> dict[str, Any]:
    """Langfuse 기반 E2E 실험 실행

    Args:
        prompt_name: E2E 타겟 이름
        mode: 실행 모드 (quick/full)
        experiment_prefix: 실험 이름 접두사

    Returns:
        실험 결과 딕셔너리
    """
    if not LANGFUSE_AVAILABLE:
        raise ImportError("Langfuse SDK가 설치되지 않았습니다.")

    langfuse = get_langfuse_client()
    targets_dir = Path("targets")
    datasets_dir = Path("datasets")

    # 1. Config 로드
    config_file = targets_dir / prompt_name / "config.yaml"
    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    chain_config = eval_config.get("chain", {})
    if not chain_config:
        raise ValueError(f"chain 설정이 없습니다: {config_file}")

    # 2. Phase 1/2 템플릿 로드
    phase1_template, phase2_template = load_phase_templates(chain_config, targets_dir)

    # 3. 데이터셋 로드 (없으면 자동 업로드)
    data_dir = datasets_dir / prompt_name
    expected_all = {}
    with open(data_dir / "expected.json", "r", encoding="utf-8") as f:
        expected_all = json.load(f)

    try:
        dataset = get_dataset(prompt_name)
    except Exception:
        print(f"  Langfuse 데이터셋 '{prompt_name}' 없음 → 자동 업로드")
        upload_from_files(
            dataset_name=prompt_name,
            test_cases_path=data_dir / "test_cases.json",
            expected_path=data_dir / "expected.json",
            description=f"E2E chain pipeline: {prompt_name}",
        )
        dataset = get_dataset(prompt_name)

    # 4. 실험 이름
    if experiment_prefix is None:
        experiment_prefix = f"{prompt_name}-e2e-{mode}"
    experiment_name = f"{experiment_prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"\nLangfuse E2E Experiment: {experiment_name}")
    print(f"  Phase 1: {chain_config['phase1']}")
    print(f"  Phase 2: {chain_config['phase2']}")
    print(f"  Mode: {mode}")
    print(f"  Items: {len(dataset.items)}")
    print()

    # 5. LLM Judge 설정
    criteria = []
    for evaluator in eval_config.get("evaluators", []):
        if evaluator.get("type") == "llm_judge":
            criteria = evaluator.get("criteria", [])
            break

    use_llm_judge = mode == "full" and criteria
    if use_llm_judge:
        print(f"  LLM Judge: {criteria}")

    # 6. Task 함수 (E2E 체인 실행 + Langfuse 트레이싱)
    def task(item):
        handler = get_langfuse_handler()
        return _run_e2e_chain(
            phase1_template, phase2_template, item.input, callbacks=[handler]
        )

    # 7. Evaluator 함수
    evaluators = []

    if use_llm_judge:
        for criterion in criteria:
            evaluators.append(create_langfuse_evaluator(criterion))

    # 8. 실험 실행
    print("  실행 중...")
    experiment_result = langfuse.run_experiment(
        name=experiment_name,
        data=dataset.items,
        task=task,
        evaluators=evaluators,
        metadata={
            "mode": mode,
            "model": execution_llm.model_name,
            "pipeline_type": "chain",
            "phase1": chain_config["phase1"],
            "phase2": chain_config["phase2"],
        },
    )

    # 9. 결과 출력
    results = []
    for item_result in experiment_result.item_results:
        item = item_result.item
        case_id = (
            item.metadata.get("case_id", "")
            if hasattr(item, "metadata") and item.metadata
            else ""
        )

        scores = {}
        for evaluation in item_result.evaluations:
            if isinstance(evaluation, dict):
                scores[evaluation.get("name", "unknown")] = evaluation.get("value", 0.0)
            else:
                scores[evaluation.name] = evaluation.value

        llm_scores = {k: v for k, v in scores.items() if k.startswith("llm_judge_")}
        overall_score = (
            sum(llm_scores.values()) / len(llm_scores) if llm_scores else None
        )
        passed = overall_score is not None and overall_score >= 0.65

        status = "PASS" if passed else "FAIL"
        score_str = f"{overall_score:.2f}" if overall_score is not None else "-"
        print(f"  [{case_id}] {status} ({score_str})")

        output_text = ""
        if item_result.output:
            if isinstance(item_result.output, dict):
                output_text = item_result.output.get("output", "")
            else:
                output_text = str(item_result.output)

        results.append(
            {
                "case_id": case_id,
                "output": output_text,
                "scores": scores,
                "overall_score": overall_score,
                "passed": passed,
                "trace_id": item_result.trace_id,
            }
        )

    # 10. 요약
    total = len(results)
    passed_count = sum(1 for r in results if r.get("passed", False))
    all_scores = [
        r["overall_score"] for r in results if r.get("overall_score") is not None
    ]

    summary = {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": passed_count / total if total > 0 else 0.0,
        "avg_score": sum(all_scores) / len(all_scores) if all_scores else None,
    }

    print("\nLangfuse E2E Experiment 완료!")
    print(f"  결과: {passed_count}/{total} 통과 ({summary['pass_rate']:.1%})")
    if summary["avg_score"]:
        print(f"  평균 점수: {summary['avg_score']:.3f}")

    langfuse_flush()

    return {
        "experiment_name": experiment_name,
        "prompt_name": prompt_name,
        "pipeline_type": "chain",
        "mode": mode,
        "model": execution_llm.model_name,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": summary,
    }


# ============================================================
# LangSmith Experiment 모드
# ============================================================


def run_e2e_langsmith_experiment(
    prompt_name: str = "prep_output",
    mode: RunMode = "full",
    experiment_prefix: str | None = None,
) -> str:
    """LangSmith 기반 E2E 실험 실행

    Args:
        prompt_name: E2E 타겟 이름
        mode: 실행 모드 (quick/full)
        experiment_prefix: 실험 이름 접두사

    Returns:
        실험 URL
    """
    from utils.dataset_sync import upload_dataset

    targets_dir = Path("targets")

    # 1. Config 로드
    config_file = targets_dir / prompt_name / "config.yaml"
    with open(config_file, "r", encoding="utf-8") as f:
        eval_config = yaml.safe_load(f)

    chain_config = eval_config.get("chain", {})
    if not chain_config:
        raise ValueError(f"chain 설정이 없습니다: {config_file}")

    # 2. 데이터셋 업로드
    ds_result = upload_dataset(prompt_name, backend="langsmith")
    dataset_name = ds_result.get("langsmith_name", f"prompt-eval-{prompt_name}")

    # 3. Phase 1/2 템플릿 로드
    phase1_template, phase2_template = load_phase_templates(chain_config, targets_dir)

    # 4. Target 함수 (E2E 체인 실행)
    def target(inputs: dict) -> dict:
        return _run_e2e_chain(phase1_template, phase2_template, inputs)

    # 5. LLM Judge 평가자
    evaluators = []
    criteria = []

    for ev in eval_config.get("evaluators", []):
        if ev.get("type") == "llm_judge":
            criteria = ev.get("criteria", [])
            break

    if mode == "full" and criteria:
        print(f"  LLM Judge 평가자 추가: {criteria}")
        for criterion in criteria:
            evaluators.append(create_langsmith_evaluator(criterion))

    # 6. 실험 이름
    if experiment_prefix is None:
        experiment_prefix = f"{prompt_name}-e2e-{mode}"

    # 7. evaluate() 실행
    print(f"\nLangSmith E2E Experiment: {experiment_prefix}")
    print(f"  Dataset: {dataset_name}")
    print(f"  Mode: {mode}")
    print(f"  Model: {execution_llm.model_name}")
    print()

    results = evaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
    )

    experiment_url = "https://smith.langchain.com/datasets"
    print("\nLangSmith E2E Experiment 완료!")
    print(f"  결과 확인: {experiment_url}")

    return experiment_url
