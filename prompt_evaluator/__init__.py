"""prompt-evaluator: LLM 프롬프트 정량 평가 엔진"""

__version__ = "0.1.0"


def __getattr__(name):
    """Lazy import - 실제 사용 시점에만 무거운 모듈 로드."""
    _exports = {
        "EvalContext": ("prompt_evaluator.context", "EvalContext"),
        "get_context": ("prompt_evaluator.context", "get_context"),
        "set_context": ("prompt_evaluator.context", "set_context"),
        "run_experiment": ("prompt_evaluator.pipelines.pipeline", "run_experiment"),
        "execute_prompt": ("prompt_evaluator.pipelines.pipeline", "execute_prompt"),
        "load_evaluation_set": (
            "prompt_evaluator.loaders.dataset_loader",
            "load_evaluation_set",
        ),
        "list_evaluation_sets": (
            "prompt_evaluator.loaders.dataset_loader",
            "list_evaluation_sets",
        ),
        "load_prompt_file": (
            "prompt_evaluator.loaders.prompt_loader",
            "load_prompt_file",
        ),
        "find_prompt_file": (
            "prompt_evaluator.loaders.prompt_loader",
            "find_prompt_file",
        ),
        "keyword_inclusion": (
            "prompt_evaluator.evaluators.rule_based",
            "keyword_inclusion",
        ),
        "forbidden_word_check": (
            "prompt_evaluator.evaluators.rule_based",
            "forbidden_word_check",
        ),
        "run_checklist_evaluation": (
            "prompt_evaluator.evaluators.llm_judge",
            "run_checklist_evaluation",
        ),
    }

    if name in _exports:
        module_path, attr = _exports[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr)

    raise AttributeError(f"module 'prompt_evaluator' has no attribute {name!r}")
