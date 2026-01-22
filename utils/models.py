"""모델 인스턴스 관리 모듈.

각 용도별 LLM 인스턴스를 미리 설정하여 제공.
환경변수에서 설정값을 로드하고 인스턴스를 생성.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from configs.config import DEFAULT_MODEL, DEFAULT_TEMPERATURE

load_dotenv()

# =============================================================================
# 환경변수 로드
# =============================================================================

OPENAI_MODEL = os.getenv("DEFAULT_MODEL", DEFAULT_MODEL)
LLM_JUDGE_MODEL = os.getenv("LLM_JUDGE_MODEL", DEFAULT_MODEL)

# =============================================================================
# OpenAI LLM 인스턴스
# =============================================================================

# 프롬프트 실행용 LLM
execution_llm = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=DEFAULT_TEMPERATURE,
)

# LLM Judge 평가용 LLM
judge_llm = ChatOpenAI(
    model=LLM_JUDGE_MODEL,
    temperature=DEFAULT_TEMPERATURE,
)


# =============================================================================
# Vertex AI (Gemini) 설정 - GCP 사용 시 활성화
# =============================================================================

# GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
# GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
# GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "8192"))
# GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))
# GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))

# if GOOGLE_CLOUD_PROJECT:
#     from langchain_google_vertexai import ChatVertexAI
#
#     # Gemini LLM 인스턴스 (평가조건 생성용)
#     template_llm = ChatVertexAI(
#         project=GOOGLE_CLOUD_PROJECT,
#         location=GOOGLE_CLOUD_LOCATION,
#         model_name=GEMINI_MODEL,
#         max_output_tokens=GEMINI_MAX_TOKENS,
#         temperature=GEMINI_TEMPERATURE,
#         thinking_budget=GEMINI_THINKING_BUDGET,
#     )
