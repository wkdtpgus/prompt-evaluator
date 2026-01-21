"""평가 템플릿 프리셋

프롬프트 유형별로 미리 정의된 평가 설정.
새 프롬프트를 평가할 때 템플릿을 선택하면 기본 설정이 자동 생성됨.
"""

import json
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# 템플릿 프리셋 정의
# ============================================================

TEMPLATE_PRESETS = {
    "json_output": {
        "name": "JSON 출력 프롬프트",
        "description": "구조화된 JSON을 출력하는 프롬프트 (분석, 추출, 분류 등)",
        "evaluators": [
            {"type": "rule_based", "checks": ["format_validity", "keyword_inclusion"]},
            {"type": "langsmith_builtin", "name": "embedding_distance", "threshold": 0.70},
        ],
        "thresholds": {"pass_rate": 0.85, "min_score": 0.70},
        "output_schema": {
            "type": "object",
            "required": [],  # 사용자가 지정
        },
    },

    "text_generation": {
        "name": "텍스트 생성 프롬프트",
        "description": "자연어 텍스트를 생성하는 프롬프트 (요약, 작문, 번역 등)",
        "evaluators": [
            {"type": "rule_based", "checks": ["keyword_inclusion", "length_compliance"]},
            {"type": "langsmith_builtin", "name": "embedding_distance", "threshold": 0.75},
            {"type": "llm_judge", "criteria": ["helpfulness", "coherence"], "enabled": True},
        ],
        "thresholds": {"pass_rate": 0.80, "min_score": 0.70},
    },

    "classification": {
        "name": "분류 프롬프트",
        "description": "입력을 카테고리로 분류하는 프롬프트",
        "evaluators": [
            {"type": "rule_based", "checks": ["exact_match", "format_validity"]},
        ],
        "thresholds": {"pass_rate": 0.90, "min_score": 0.90},
        "output_schema": {
            "type": "object",
            "required": ["category"],
            "properties": {
                "category": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
    },

    "extraction": {
        "name": "정보 추출 프롬프트",
        "description": "텍스트에서 특정 정보를 추출하는 프롬프트",
        "evaluators": [
            {"type": "rule_based", "checks": ["format_validity", "keyword_inclusion"]},
            {"type": "langsmith_builtin", "name": "embedding_distance", "threshold": 0.80},
        ],
        "thresholds": {"pass_rate": 0.85, "min_score": 0.75},
    },

    "chatbot": {
        "name": "챗봇/대화 프롬프트",
        "description": "대화형 응답을 생성하는 프롬프트",
        "evaluators": [
            {"type": "rule_based", "checks": ["forbidden_word_check", "length_compliance"]},
            {"type": "llm_judge", "criteria": ["helpfulness", "relevance"], "enabled": True},
        ],
        "thresholds": {"pass_rate": 0.80, "min_score": 0.70},
    },

    "analysis": {
        "name": "분석 프롬프트",
        "description": "데이터나 상황을 분석하고 인사이트를 제공하는 프롬프트 (1on1 prep 등)",
        "evaluators": [
            {"type": "rule_based", "checks": ["format_validity", "keyword_inclusion", "forbidden_word_check"]},
            {"type": "langsmith_builtin", "name": "embedding_distance", "threshold": 0.70},
            {"type": "llm_judge", "criteria": ["helpfulness", "relevance"], "enabled": True},
        ],
        "thresholds": {"pass_rate": 0.85, "min_score": 0.70},
    },

    "strict": {
        "name": "엄격한 평가",
        "description": "높은 정확도가 필요한 프롬프트 (의료, 법률, 금융 등)",
        "evaluators": [
            {"type": "rule_based", "checks": ["format_validity", "keyword_inclusion", "forbidden_word_check", "exact_match"]},
            {"type": "langsmith_builtin", "name": "embedding_distance", "threshold": 0.85},
            {"type": "llm_judge", "criteria": ["helpfulness", "relevance", "coherence"], "enabled": True},
        ],
        "thresholds": {"pass_rate": 0.95, "min_score": 0.85},
    },

    "minimal": {
        "name": "최소 평가",
        "description": "빠른 검증용 (개발 초기)",
        "evaluators": [
            {"type": "rule_based", "checks": ["format_validity"]},
        ],
        "thresholds": {"pass_rate": 0.70, "min_score": 0.50},
    },
}


def list_templates() -> list[dict]:
    """사용 가능한 템플릿 목록 반환."""
    return [
        {"id": tid, "name": t["name"], "description": t["description"]}
        for tid, t in TEMPLATE_PRESETS.items()
    ]


def get_template(template_id: str) -> dict:
    """템플릿 ID로 프리셋 가져오기."""
    if template_id not in TEMPLATE_PRESETS:
        raise ValueError(f"Unknown template: {template_id}. Available: {list(TEMPLATE_PRESETS.keys())}")
    return TEMPLATE_PRESETS[template_id].copy()


def create_evaluation_set(
    prompt_name: str,
    template_id: str,
    prompt_content: str,
    test_cases: list[dict],
    expected: dict,
    prompts_dir: str | Path = "prompts",
    datasets_dir: str | Path = "datasets",
    custom_config: dict | None = None,
) -> dict:
    """템플릿 기반으로 평가 세트 생성.

    Args:
        prompt_name: 평가 세트 이름 (예: "my_analyzer")
        template_id: 템플릿 ID (예: "json_output", "analysis")
        prompt_content: 프롬프트 텍스트
        test_cases: 테스트 케이스 목록
        expected: 기대 결과 (case_id -> {keywords, forbidden, reference})
        prompts_dir: prompts 폴더 경로
        datasets_dir: datasets 폴더 경로
        custom_config: 템플릿 설정 오버라이드

    Returns:
        생성된 파일 경로들
    """
    prompts_dir = Path(prompts_dir)
    datasets_dir = Path(datasets_dir)

    # 템플릿 가져오기
    template = get_template(template_id)

    # 커스텀 설정 병합
    if custom_config:
        if "thresholds" in custom_config:
            template["thresholds"].update(custom_config["thresholds"])
        if "evaluators" in custom_config:
            template["evaluators"] = custom_config["evaluators"]

    # 디렉토리 생성
    prompts_dir.mkdir(parents=True, exist_ok=True)
    data_dir = datasets_dir / f"{prompt_name}_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. 프롬프트 파일 저장
    prompt_file = prompts_dir / f"{prompt_name}_prompt.txt"
    prompt_file.write_text(prompt_content, encoding="utf-8")

    # 2. test_cases.json 저장
    test_cases_file = data_dir / "test_cases.json"
    with open(test_cases_file, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)

    # 3. expected.json 저장
    expected_file = data_dir / "expected.json"
    with open(expected_file, "w", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=2)

    # 4. eval_config.yaml 저장
    eval_config = {
        "evaluators": template["evaluators"],
        "thresholds": template["thresholds"],
        "run_mode": "standard",
    }
    if "output_schema" in template:
        eval_config["output_schema"] = template["output_schema"]

    config_file = data_dir / "eval_config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(eval_config, f, allow_unicode=True, default_flow_style=False)

    print(f"✅ 평가 세트 생성 완료: {prompt_name}")
    print(f"   템플릿: {template['name']}")
    print(f"   프롬프트: {prompt_file}")
    print(f"   데이터: {data_dir}/")

    return {
        "prompt_file": str(prompt_file),
        "data_dir": str(data_dir),
        "test_cases_file": str(test_cases_file),
        "expected_file": str(expected_file),
        "config_file": str(config_file),
    }
