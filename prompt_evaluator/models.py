"""모델 인스턴스 관리 모듈.

각 용도별 LLM 인스턴스를 lazy하게 생성하여 제공.
CLI의 init 등 LLM이 필요 없는 명령어에서 API 키 에러를 방지.
"""

from prompt_evaluator.config import (
    DEFAULT_MODEL,
    DEFAULT_LLM_JUDGE_MODEL,
    DEFAULT_TEMPERATURE,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
    GEMINI_THINKING_BUDGET,
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_CLOUD_LOCATION,
)

# =============================================================================
# LLM 인스턴스 (lazy initialization)
# =============================================================================

_execution_llm = None
_judge_llm = None


def get_execution_llm():
    """프롬프트 실행용 LLM 인스턴스 반환."""
    global _execution_llm
    if _execution_llm is None:
        if GOOGLE_CLOUD_PROJECT:
            from langchain_google_vertexai import ChatVertexAI

            _execution_llm = ChatVertexAI(
                project=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
                model_name=GEMINI_MODEL,
                max_output_tokens=GEMINI_MAX_TOKENS,
                temperature=GEMINI_TEMPERATURE,
                thinking_budget=GEMINI_THINKING_BUDGET,
            )
        else:
            from langchain_openai import ChatOpenAI

            _execution_llm = ChatOpenAI(
                model=DEFAULT_MODEL,
                temperature=DEFAULT_TEMPERATURE,
            )
    return _execution_llm


def get_judge_llm():
    """LLM Judge 평가용 LLM 인스턴스 반환."""
    global _judge_llm
    if _judge_llm is None:
        if GOOGLE_CLOUD_PROJECT:
            from langchain_google_vertexai import ChatVertexAI

            _judge_llm = ChatVertexAI(
                project=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
                model_name=DEFAULT_LLM_JUDGE_MODEL,
                temperature=DEFAULT_TEMPERATURE,
            )
        else:
            from langchain_openai import ChatOpenAI

            _judge_llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=DEFAULT_TEMPERATURE,
            )
    return _judge_llm
