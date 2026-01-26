from typing import Optional, Literal, Dict, List
from pydantic import BaseModel, Field

class SurveyAnswers(BaseModel):
    """서베이 응답 스키마"""
    condition: Optional[Literal[
        "VERY_GOOD",  # 매우 좋음
        "GOOD",       # 좋음
        "NORMAL",     # 양호함
        "TIRED",      # 지침
        "VERY_BAD",   # 매우 나쁨
    ]] = None
    topic: Optional[Literal[
        "PERFORMANCE_FEEDBACK",  # 성과와 피드백
        "GROWTH_CAREER",         # 성장과 커리어
        "WORK_ISSUES",           # 실무 고민 해결
        "TEAM_CULTURE",          # 팀 문화
        "ROLE_RESPONSIBILITY",   # 역할 및 책임
    ]] = None

class UserProfileCardAnswer(BaseModel):
    """유저 프로필 카드 응답 (4개 질문 x 4개 옵션)"""
    communicationStyle: Literal[
        "SUMMARY",     # 핵심 요약형
        "CONTEXT",     # 상세 맥락형
        "DATA",        # 데이터 근거형
        "DISCUSSION",  # 대화 토론형
    ]
    feedbackStyle: Literal[
        "DIRECT",          # 직설적 개선
        "POSITIVE",        # 긍정적 강화
        "SOLUTION",        # 솔루션 제시
        "SELF_REFLECTION", # 자율적 성찰
    ]
    careerOrientation: Literal[
        "SPECIALIST",  # 전문가
        "LEADER",      # 리더
        "GENERALIST",  # 조율자
        "EXPLORER",    # 개척자
    ]
    motivation: Literal[
        "GROWTH",      # 배움과 성장
        "AUTONOMY",    # 권한과 자율성
        "RECOGNITION", # 인정 및 평판
        "IMPACT",      # 의미와 영향력
    ]

class AiCoreSummary(BaseModel):
    """AI 코어 요약 (Pro 버전)"""
    core_content: str
    decisions_made: list[str]
    support_needs_blockers: list[str]

class AiProfileTopic(BaseModel):
    """AI 프로필 토픽"""
    level: Literal["high", "medium", "low"]
    topic: str
    context: str

class AiProfileObservation(BaseModel):
    """AI 프로필 관찰"""
    observation: str
    context: str

class AiProfileAttributes(BaseModel):
    """AI 프로필 속성 (Pro 버전)"""
    topics: list[AiProfileTopic]
    observations: list[AiProfileObservation]

class DynamicContext(BaseModel):
    """동적 컨텍스트 (대화 중 변경 가능한 필드)"""
    survey_answers: Optional[SurveyAnswers] = Field(
        default=None, description="서베이 응답 (첫 호출 시에만)"
    )
    user_profile_card_answer: Optional[UserProfileCardAnswer] = Field(
        default=None, description="프로필 카드 응답"
    )
    prep_content: Optional[str] = Field(
        default=None, description="현재 미팅의 프렙 (프렙 생성 시)"
    )
    member_action_items: Optional[Dict[str, str]] = Field(
        default=None, description="액션아이템 ({타이틀: 완료여부})"
    )

class ChatRequest(BaseModel):
    """채팅 요청 스키마"""
    # --- 필수 필드 ---
    meeting_id: str = Field(..., description="미팅 UUID (one_on_one_meeting.id)")
    member_id: str = Field(..., description="팀원 사용자 ID")
    member_name: str = Field(..., description="팀원 이름")
    message: Optional[str] = Field(
        default=None,
        description="사용자 메시지 (첫 호출/재개 시 null)"
    )
    language: Literal["ko-KR", "en-US", "vi-VN"] = Field(
        default="ko-KR",
        description="출력 언어"
    )

    # --- 고정 필드 (세션 내 변경 없음) ---
    description: Optional[str] = Field(
        default=None, description="역할(role) 설명"
    )
    previous_prep_content: Optional[str] = Field(
        default=None, description="이전 미팅의 프렙 유저 수정본"
    )
    ai_core_summary: Optional[AiCoreSummary] = Field(
        default=None, description="이전 미팅 AI 요약 (Pro)"
    )
    ai_profile_attributes: Optional[AiProfileAttributes] = Field(
        default=None, description="AI 생성 프로필 속성 (Pro)"
    )

    # --- 동적 필드 (대화 중 변경 가능) ---
    context: Optional[DynamicContext] = Field(
        default=None,
        description="동적 컨텍스트 (survey_answers, user_profile_card_answer, prep_content, member_action_items)"
    )

class PrepSummaryInput(BaseModel):
    """Input schema for generating prep summary."""

    summary: str = Field(
        description="Prep summary text. Use \\n for line breaks and • for bullet points."
    )


# ===== Prep Generation API Schemas =====

class PrepGenerateContext(BaseModel):
    """프렙 생성을 위한 컨텍스트"""
    survey_answers: Optional[SurveyAnswers] = Field(
        default=None,
        description="서베이 응답 (condition, topic)"
    )
    user_profile_card_answer: Optional[UserProfileCardAnswer] = Field(
        default=None,
        description="유저 프로필 카드 응답 (4개 질문)"
    )


class PrepGenerateRequest(BaseModel):
    """프렙 생성 요청 스키마"""
    meeting_id: str = Field(..., description="미팅 UUID (one_on_one_meeting.id)")
    member_name: str = Field(..., description="팀원 이름")
    language: Literal["ko-KR", "en-US", "vi-VN"] = Field(
        default="ko-KR",
        description="출력 언어"
    )
    chat_summary_state: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="대화 이력. 미제공 시 빈 이력으로 처리"
    )
    context: Optional[PrepGenerateContext] = Field(
        default=None,
        description="추가 컨텍스트 (survey_answers, user_profile_card_answer)"
    )


class PrepGenerateResponse(BaseModel):
    """프렙 생성 응답 및 LLM 출력 통합 스키마"""
    prepContentRaw: str = Field(description="프렙 요약 텍스트 (\\n으로 줄바꿈, • 불릿 사용)")