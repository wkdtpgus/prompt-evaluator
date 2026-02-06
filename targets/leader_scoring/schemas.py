"""Meeting Generator 스키마 정의

STT 및 미팅 분석 파이프라인에서 사용되는 모든 스키마를 정의합니다.
"""
from typing import List, Optional, Dict, TypedDict, Literal, Annotated
from pydantic import BaseModel, Field


# ==================== Premium Scoring Schemas ====================

class ScoringCriteria(BaseModel):
    """30개 평가 항목 개별 스코어"""
    criteria_code: str = Field(description="평가 항목 코드 (예: LISTENING_01, CLARITY_02)")
    score: int = Field(description="점수 (0 또는 1)")
    rationale: str = Field(description="점수 판단 근거")


class ScoringResult(BaseModel):
    """스코어링 결과 (LLM 출력용)"""
    scores: List[ScoringCriteria] = Field(description="30개 평가 항목 스코어")


class PartialScoringResult(BaseModel):
    """배치 처리용 부분 스코어링 결과 (10개 항목)

    병렬 스코어링에서 각 배치가 10개 항목만 평가할 때 사용합니다.
    3개의 PartialScoringResult를 병합하여 최종 ScoringResult를 생성합니다.
    """
    scores: List[ScoringCriteria] = Field(description="10개 평가 항목 스코어")
    batch_id: Optional[int] = Field(default=None, description="배치 식별자 (1, 2, 3) - LLM이 생략할 수 있음")


class SpeakerMappingResult(BaseModel):
    """화자 매핑 결과 (LLM 출력용)"""
    speaker_mapping: List[str] = Field(description="화자 매핑 정보 - [leader_name, member_name] 순서")


class QAItem(BaseModel):
    """Q&A 항목"""
    question_index: int = Field(description="질문 인덱스 (1부터 시작)")
    question: Optional[str] = Field(default=None, description="질문 텍스트 (질문이 제공되지 않아 LLM이 추출한 경우에만 포함)")
    answer: str = Field(description="대화록에서 추출한 답변")



