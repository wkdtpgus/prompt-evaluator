"""모델 인스턴스 관리 모듈.

각 용도별 LLM 인스턴스를 미리 설정하여 제공.
"""

from langchain_openai import ChatOpenAI

from configs.config import (
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
# LLM 인스턴스
# =============================================================================

# 프롬프트 실행용 LLM: Gemini (GCP 설정 시) / OpenAI (fallback)
if GOOGLE_CLOUD_PROJECT:
    from langchain_google_vertexai import ChatVertexAI

    execution_llm = ChatVertexAI(
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION,
        model_name=GEMINI_MODEL,
        max_output_tokens=GEMINI_MAX_TOKENS,
        temperature=GEMINI_TEMPERATURE,
        thinking_budget=GEMINI_THINKING_BUDGET,
    )
else:
    execution_llm = ChatOpenAI(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
    )

# LLM Judge 평가용 LLM (항상 OpenAI)
judge_llm = ChatOpenAI(
    model=DEFAULT_LLM_JUDGE_MODEL,
    temperature=DEFAULT_TEMPERATURE,
)
