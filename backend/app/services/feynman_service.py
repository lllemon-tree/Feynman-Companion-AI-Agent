from functools import lru_cache
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.core.database import engine
from backend.app.graphs.feynman_graph import FeynmanGraph
from backend.app.models.auth import GUEST_USER_ID
from backend.app.models.feynman import (
    FeynmanChatData,
    FeynmanChatRequest,
    GreetingData,
    ResetSessionData,
    ResetSessionRequest,
    SessionDetailData,
    SessionDebugData,
    SessionSummaryData,
)
from backend.app.services.deepseek_client import DeepSeekClient
from backend.app.services.kp_provider import DEFAULT_KP_ID, KnowledgePointProvider, kp_provider
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.rag_retriever import RAGRetriever, get_rag_retriever
from backend.app.services.session_store import (
    SQLSessionStore,
    SessionStore,
)


class FeynmanService:
    def __init__(
        self,
        store: SessionStore,
        llm_client,
        fallback_client=None,
        knowledge_point_provider: Optional[KnowledgePointProvider] = None,
        rag_retriever: Optional[RAGRetriever] = None,
    ) -> None:
        self._store = store
        self._llm_client = llm_client
        self._fallback_client = fallback_client or MockLLMClient()
        self._kp_provider = knowledge_point_provider or kp_provider
        self._settings = get_settings()
        primary_provider_name = "deepseek" if isinstance(llm_client, DeepSeekClient) else "mock"
        self._graph = FeynmanGraph(
            llm_client=self._llm_client,
            fallback_client=self._fallback_client,
            kp_provider=self._kp_provider,
            max_follow_ups=self._settings.max_follow_ups,
            primary_provider_name=primary_provider_name,
            rag_retriever=rag_retriever or get_rag_retriever(),
        )

    async def chat(
        self,
        request: FeynmanChatRequest,
        user_id: str = GUEST_USER_ID,
    ) -> FeynmanChatData:
        if not request.user_input.strip():
            raise ValueError("user_input cannot be empty")

        session = self._store.get_or_create(request.session_id, user_id)
        if session.ended and session.final_response is not None:
            return session.final_response
        response = await self._graph.run(request=request, session=session)
        self._store.save(session)
        return response

    def greeting(self, kp_id: Optional[str] = None) -> GreetingData:
        knowledge_point = self._kp_provider.get(kp_id or DEFAULT_KP_ID)
        if knowledge_point is None:
            raise ValueError("knowledge point not found")
        return GreetingData(
            reply_text=(
                f"请你向我讲解一下{knowledge_point.name}的核心原理，"
                "讲得越详细越好。"
            ),
            kp_id=knowledge_point.kp_id,
            kp_name=knowledge_point.name,
        )

    def reset(
        self,
        request: ResetSessionRequest,
        user_id: str = GUEST_USER_ID,
    ) -> ResetSessionData:
        self._store.reset(request.session_id, user_id)
        return ResetSessionData(session_id=request.session_id, reset=True)

    def inspect_session(
        self,
        session_id: str,
        user_id: str = GUEST_USER_ID,
    ) -> SessionDebugData:
        session = self._store.get(session_id, user_id)
        if session is None:
            return SessionDebugData(session_id=session_id, exists=False)

        return SessionDebugData(
            session_id=session.session_id,
            exists=True,
            follow_up_count=session.follow_up_count,
            invalid_answer_count=session.invalid_answer_count,
            off_topic_count=session.off_topic_count,
            ended=session.ended,
            message_count=len(session.messages),
            last_provider=session.last_provider,
            fallback_used=session.fallback_used,
            kp_id=session.kp_id,
            kp_name=session.kp_name,
            material_id=session.material_id,
            chapter_id=session.chapter_id,
            recent_messages=session.messages[-6:],
        )

    def get_session_detail(
        self,
        session_id: str,
        user_id: str = GUEST_USER_ID,
    ) -> Optional[SessionDetailData]:
        session = self._store.get(session_id, user_id)
        if session is None:
            return None
        return SessionDetailData(
            session_id=session.session_id,
            kp_id=session.kp_id,
            kp_name=session.kp_name,
            material_id=session.material_id,
            chapter_id=session.chapter_id,
            chat_history=session.messages,
            report_data=session.final_response,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
        )

    def list_sessions(
        self,
        user_id: str = GUEST_USER_ID,
    ) -> list[SessionSummaryData]:
        return [
            SessionSummaryData(
                session_id=item.session_id,
                kp_name=item.kp_name,
                material_title=item.material_title,
                created_at=item.created_at.isoformat(),
            )
            for item in self._store.list_by_user(user_id)
        ]

    def draw_graph_mermaid(self) -> str:
        return self._graph.draw_mermaid()


@lru_cache
def get_feynman_service() -> FeynmanService:
    settings = get_settings()
    if settings.llm_provider == "deepseek" and settings.deepseek_configured:
        llm_client = DeepSeekClient(settings)
    else:
        llm_client = MockLLMClient()
    return FeynmanService(
        store=SQLSessionStore(engine),
        llm_client=llm_client,
        fallback_client=MockLLMClient(),
    )
