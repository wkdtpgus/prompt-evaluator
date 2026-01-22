import json
import os
from typing import Any, Callable

import numpy as np
from langsmith.evaluation import EvaluationResult

from configs.config import (
    DEFAULT_EMBEDDING_PROVIDER,
    OPENAI_EMBEDDING_MODEL,
    VERTEX_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_THRESHOLD,
)


def create_embedding_distance_evaluator(
    threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
    provider: str | None = None
) -> Callable:
    """임베딩 거리 기반 평가자 생성.

    LangSmith의 embedding_distance를 래핑.
    출력과 참조 텍스트 간의 의미적 유사도 측정.

    Args:
        threshold: 통과 기준 유사도 (0.0 ~ 1.0)
        provider: 임베딩 프로바이더 ("openai" 또는 "vertex")
                  None이면 환경변수 EMBEDDING_PROVIDER 사용

    Returns:
        LangSmith evaluate()에서 사용할 수 있는 평가자 함수
    """
    # 프로바이더 결정 (파라미터 > 환경변수 > 기본값)
    use_provider = (provider or os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER)).lower()

    # NOTE: 지연 import - 프로바이더에 따라 선택적 로드 필요
    # vertex/openai 중 하나만 사용하므로 불필요한 의존성 로드 방지
    if use_provider == "vertex":
        from langchain_google_vertexai import VertexAIEmbeddings
        embeddings = VertexAIEmbeddings(model_name=VERTEX_EMBEDDING_MODEL)
    else:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)

    def evaluator(run, example) -> EvaluationResult:
        """LangSmith 평가자 함수."""
        output = run.outputs.get("output", "")
        reference = example.outputs.get("reference", {})

        # reference가 dict면 문자열로 변환
        if isinstance(reference, dict):
            reference_text = json.dumps(reference, ensure_ascii=False)
        else:
            reference_text = str(reference)

        if not output or not reference_text:
            return EvaluationResult(
                key="embedding_distance",
                score=0.0,
                comment="Empty output or reference"
            )

        # 임베딩 계산
        output_embedding = embeddings.embed_query(output)
        reference_embedding = embeddings.embed_query(reference_text)

        # 코사인 유사도 계산
        similarity = np.dot(output_embedding, reference_embedding) / (
            np.linalg.norm(output_embedding) * np.linalg.norm(reference_embedding)
        )

        return EvaluationResult(
            key="embedding_distance",
            score=float(similarity),
            comment=f"Similarity: {similarity:.3f} (threshold: {threshold}, provider: {use_provider})"
        )

    return evaluator


def create_string_distance_evaluator(
    metric: str = "levenshtein",
    threshold: float = 0.7
) -> Callable:
    """문자열 거리 기반 평가자 생성.

    Args:
        metric: "levenshtein", "jaro_winkler", "hamming"
        threshold: 통과 기준 (0.0 ~ 1.0, 높을수록 유사)

    Returns:
        LangSmith evaluate()에서 사용할 수 있는 평가자 함수
    """
    def evaluator(run, example) -> EvaluationResult:
        """LangSmith 평가자 함수."""
        output = run.outputs.get("output", "")
        reference = example.outputs.get("reference", {})

        if isinstance(reference, dict):
            reference_text = json.dumps(reference, ensure_ascii=False)
        else:
            reference_text = str(reference)

        if not output or not reference_text:
            return EvaluationResult(
                key="string_distance",
                score=0.0,
                comment="Empty output or reference"
            )

        # 문자열 거리 계산
        if metric == "levenshtein":
            score = _levenshtein_similarity(output, reference_text)
        elif metric == "jaro_winkler":
            score = _jaro_winkler_similarity(output, reference_text)
        else:
            score = _levenshtein_similarity(output, reference_text)

        return EvaluationResult(
            key="string_distance",
            score=float(score),
            comment=f"{metric} similarity: {score:.3f} (threshold: {threshold})"
        )

    return evaluator


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Levenshtein 거리 기반 유사도 (0.0 ~ 1.0)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # 동적 프로그래밍으로 편집 거리 계산
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    distance = dp[m][n]
    max_len = max(m, n)

    return 1.0 - (distance / max_len) if max_len > 0 else 1.0


def _jaro_winkler_similarity(s1: str, s2: str) -> float:
    """Jaro-Winkler 유사도 (0.0 ~ 1.0)."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

    # Winkler 수정: 공통 접두사 보너스
    prefix = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * 0.1 * (1 - jaro)


def get_langsmith_evaluators(
    evaluator_configs: list[dict],
    threshold: float = DEFAULT_EMBEDDING_THRESHOLD
) -> list[Callable]:
    """설정에 따라 LangSmith 평가자 목록 생성.

    Args:
        evaluator_configs: 평가자 설정 목록
            [{"name": "embedding_distance", "threshold": 0.75, "provider": "vertex"}, ...]
        threshold: 기본 임계값

    Returns:
        평가자 함수 목록
    """
    evaluators = []

    for config in evaluator_configs:
        name = config.get("name", "")
        thresh = config.get("threshold", threshold)

        if name == "embedding_distance":
            provider = config.get("provider")  # None이면 환경변수 사용
            evaluators.append(create_embedding_distance_evaluator(thresh, provider))
        elif name == "string_distance":
            metric = config.get("metric", "levenshtein")
            evaluators.append(create_string_distance_evaluator(metric, thresh))

    return evaluators
