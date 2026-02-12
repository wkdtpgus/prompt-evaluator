"""
Langfuse 클라이언트 유틸리티

Langfuse SDK 클라이언트 및 LangChain 연동을 위한 헬퍼 함수 제공
"""

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

# 싱글톤 클라이언트 인스턴스
_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse:
    """
    Langfuse 클라이언트 인스턴스 반환 (싱글톤)

    환경변수에서 자동으로 설정을 읽음:
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_HOST
    """
    global _client
    if _client is None:
        _client = Langfuse()
    return _client


def get_langfuse_handler(**kwargs) -> CallbackHandler:
    """
    LangChain용 Langfuse 콜백 핸들러 반환

    Args:
        **kwargs: CallbackHandler에 전달할 추가 인자
            - session_id: 세션 그룹화
            - user_id: 사용자 식별
            - tags: 태그 목록
            - metadata: 추가 메타데이터

    Returns:
        CallbackHandler: LangChain 체인에 전달할 콜백 핸들러

    Example:
        handler = get_langfuse_handler(user_id="user_123", tags=["test"])
        chain.invoke({"input": "hello"}, config={"callbacks": [handler]})
    """
    return CallbackHandler(**kwargs)


def flush():
    """모든 대기 중인 이벤트를 Langfuse 서버로 전송"""
    client = get_langfuse_client()
    client.flush()


def shutdown():
    """Langfuse 클라이언트 종료 (프로그램 종료 시 호출)"""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
