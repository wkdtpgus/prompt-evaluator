"""중앙 설정 관리 모듈."""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# 모델 기본값
# =============================================================================

DEFAULT_MODEL = "gpt-5"
DEFAULT_LLM_JUDGE_MODEL = "gpt-5"
DEFAULT_EMBEDDING_PROVIDER = "openai"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
VERTEX_EMBEDDING_MODEL = "text-embedding-004"

# Gemini
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MAX_TOKENS = 20000
GEMINI_TEMPERATURE = 0
GEMINI_THINKING_BUDGET = 0

# GCP
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# =============================================================================
# 평가 임계값
# =============================================================================

DEFAULT_MIN_SCORE = 0.70
DEFAULT_EMBEDDING_THRESHOLD = 0.75
DEFAULT_STRING_SIMILARITY_THRESHOLD = 0.30

# =============================================================================
# 길이 제한
# =============================================================================

DEFAULT_MIN_LENGTH = 10
DEFAULT_MAX_LENGTH = 5000

# =============================================================================
# LLM 호출 설정
# =============================================================================

DEFAULT_TEMPERATURE = 0
