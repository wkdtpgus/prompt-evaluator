"""Prep Output Generator 스키마 정의

Prep 기반 질문 추천 및 미팅 가이드 생성에 사용되는 스키마를 정의합니다.
"""
from typing import List, Dict, Literal, TypedDict, Optional
from pydantic import BaseModel, Field


# ==================== API Schemas ====================

class ProfileCardInput(BaseModel):
    """멤버 프로필 카드 (프렙에서 수집한 성향 데이터) - 후순위 참고용"""
    career_orientation: Optional[Literal["SPECIALIST", "LEADER", "GENERALIST", "EXPLORER"]] = Field(
        default=None, alias="careerOrientation", description="커리어 지향성"
    )
    communication_style: Optional[Literal["SUMMARY", "CONTEXT", "DATA", "DISCUSSION"]] = Field(
        default=None, alias="communicationStyle", description="커뮤니케이션 스타일"
    )
    feedback_style: Optional[Literal["DIRECT", "POSITIVE", "SOLUTION", "SELF_REFLECTION"]] = Field(
        default=None, alias="feedbackStyle", description="피드백 스타일"
    )
    motivation: Optional[Literal["GROWTH", "AUTONOMY", "RECOGNITION", "IMPACT"]] = Field(
        default=None, description="동기부여 요인"
    )

    model_config = {"populate_by_name": True}


class PrepOutputInput(BaseModel):
    """Prep Output 생성 요청

    챗봇 대화 기록과 서베이 응답을 기반으로 추천 질문 및 미팅 가이드 생성
    """
    chat_history: List[Dict] = Field(
        default=[],
        description="챗봇 대화 기록 [{role: 'ai'|'human', content: str}, ...]"
    )
    survey_answers: Optional[Dict] = Field(
        default=None,
        description="서베이 응답 {condition?: WorkCondition, topic?: MeetingTopic}"
    )
    language: Literal["ko-KR", "en-US", "vi-VN"] = Field(
        default="ko-KR",
        description="출력 언어"
    )
    member_name: str = Field(default="멤버", description="멤버 이름")
    profile_card: Optional[ProfileCardInput] = Field(
        default=None, description="멤버 프로필 카드 (후순위 참고용 성향 데이터)"
    )


class QuestionContext(BaseModel):
    """질문별 맥락 정보"""
    question_theme: str = Field(description="챗봇이 물어본 주제")
    bot_question: Optional[str] = Field(default=None, description="챗봇 질문 원문 (서베이만 있을 경우 null)")
    response_quality: Literal["detailed", "brief", "avoided", "survey_only"] = Field(
        description="응답 품질 - detailed: 상세, brief: 짧음, avoided: 회피, survey_only: 서베이만"
    )
    member_response: Optional[str] = Field(default=None, description="멤버 응답 원문 (서베이만 있을 경우 null)")
    coaching_hint: str = Field(description="코칭/접근 힌트 - 항상 값이 있음")


class MeetingGuide(BaseModel):
    """미팅 가이드 구조화된 응답"""
    key_insight: str = Field(description="멤버의 현재 상태와 핵심 관심사")
    approach: str = Field(description="미팅에서 할 것과 조심할 것")
    tip: str = Field(description="실제 대화 운영 팁")


class PrepOutputResponse(BaseModel):
    """Prep Output 응답"""
    recommended_questions: Dict[str, str] = Field(
        description="추천 질문 {번호: 질문}"
    )
    meeting_guide: MeetingGuide = Field(
        description="미팅 가이드 (key_insight, approach, tip)"
    )
    question_context: List[QuestionContext] = Field(
        default=[],
        description="질문별 맥락 정보 (분석 결과)"
    )


# ==================== Pipeline State ====================

class PrepOutputState(TypedDict):
    """Prep Output 파이프라인 상태 (LangGraph 내부용)"""
    # Input
    chat_history: List[Dict]
    survey_answers: Optional[Dict]
    language: str
    member_name: str
    profile_card: Optional[Dict]  # 후순위 참고용

    # 분석 결과 (analyze_prep에서 저장)
    question_context: List[Dict]  # QuestionContext as dict

    # Output
    recommended_questions: Dict[str, str]
    meeting_guide: Dict[str, str]  # {key_insight, approach, tip}

    # Status
    errors: List[str]
    status: str
