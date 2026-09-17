import logging
from functools import lru_cache
from typing import Callable, Optional

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
from backend.app.services.diagnostic_report_service import (
    DiagnosticReportFinalizer,
    NullReportFinalizer,
    ReportFinalizer,
)
from backend.app.services.kp_provider import DEFAULT_KP_ID, KnowledgePointProvider, kp_provider
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.rag_retriever import RAGRetriever, get_rag_retriever
from backend.app.services.session_store import (
    SQLSessionStore,
    SessionState,
    SessionStore,
)
from backend.app.services.review_context_service import DefaultReviewContextProvider

logger = logging.getLogger(__name__)


class ReviewPersistenceError(Exception):
    """Review result was generated but its atomic database write failed."""


def build_study_greeting(kp_name: str) -> str:
    if any(word in kp_name for word in ("区别", "对比", "比较")):
        return (
            f"我们来学习「{kp_name}」。先说说你会怎样比较它们，"
            "最关键的差异是什么？不确定的地方也可以直接讲出来。"
        )
    return (
        f"我们来学习「{kp_name}」。你目前怎么理解它？"
        "先讲你最确定的一点，我会根据你的讲解继续追问。"
    )


class FeynmanService:
    def __init__(
        self,
        store: SessionStore,
        llm_client,
        fallback_client=None,
        knowledge_point_provider: Optional[KnowledgePointProvider] = None,
        rag_retriever: Optional[RAGRetriever] = None,
        report_finalizer: Optional[ReportFinalizer] = None,
        profile_provider=None,
        review_context_provider=None,
    ) -> None:
        self._store = store
        self._llm_client = llm_client
        self._fallback_client = fallback_client or MockLLMClient()
        self._kp_provider = knowledge_point_provider or kp_provider
        self._report_finalizer = report_finalizer or NullReportFinalizer()
        self._settings = get_settings()
        primary_provider_name = "deepseek" if isinstance(llm_client, DeepSeekClient) else "mock"
        self._graph = FeynmanGraph(
            llm_client=self._llm_client,
            fallback_client=self._fallback_client,
            kp_provider=self._kp_provider,
            max_follow_ups=self._settings.max_follow_ups,
            primary_provider_name=primary_provider_name,
            rag_retriever=rag_retriever or get_rag_retriever(),
            profile_provider=profile_provider,
            review_context_provider=review_context_provider,
        )

    async def chat(
        self,
        request: FeynmanChatRequest,
        user_id: str = GUEST_USER_ID,
        on_reply_delta: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> FeynmanChatData:
        print(f"📝 user_input: {request.user_input.strip()[:120]}")
        if not request.user_input.strip() and not request.finish_requested:
            raise ValueError("user_input cannot be empty")

        session = self._store.get_or_create(request.session_id, user_id)
        if session.ended and session.final_response is not None:
            report = self._finalize_report_safely(session, session.final_response)
            self._attach_report_metadata(session.final_response, report)
            return session.final_response
        # Graph 的 load_context 节点统一加载画像，避免在两层重复查库。
        response = await self._graph.run(
            request=request, session=session,
            on_reply_delta=on_reply_delta, on_status=on_status,
        )
        response.provider = session.last_provider
        response.fallback_used = session.fallback_used
        self._keep_known_related_knowledge_points(response, session.material_id)
        if on_status:
            on_status("saving", "正在保存本轮讲解与诊断…")
        self._store.save(session)
        report = self._finalize_report_safely(session, response)
        self._attach_report_metadata(response, report)
        if report is not None:
            session.final_response = response
            self._store.save(session)
        return response

    def _keep_known_related_knowledge_points(
        self, response: FeynmanChatData, material_id: Optional[str],
    ) -> None:
        if response.review_plan is None:
            return
        verified = []
        for item in response.review_plan.related_kps:
            try:
                point = self._kp_provider.get(item.kp_id)
            except Exception:
                point = None
            if point is not None and point.name == item.kp_name and point.material_id == material_id:
                verified.append(item)
        response.review_plan.related_kps = verified

    def _finalize_report_safely(
        self,
        session: SessionState,
        response: FeynmanChatData,
    ):
        try:
            return self._report_finalizer.finalize(session, response)
        except Exception:
            logger.exception(
                "diagnostic report persistence failed for session %s",
                session.session_id,
            )
            if (
                isinstance(self._report_finalizer, DiagnosticReportFinalizer)
                and self._report_finalizer.is_review_session(session)
            ):
                raise ReviewPersistenceError("复习结果暂未保存，请重试")
        return None

    def _attach_report_metadata(self, response, report) -> None:
        if report is None:
            return
        response.report_id = report.id
        metadata_reader = getattr(self._report_finalizer, "review_list_metadata", None)
        if callable(metadata_reader):
            added, source = metadata_reader(report)
            response.review_list_added = added
            response.review_list_source = source

    def greeting(self, kp_id: Optional[str] = None, session_id: Optional[str] = None, user_id: str = GUEST_USER_ID) -> GreetingData:
        knowledge_point = self._kp_provider.get(kp_id or DEFAULT_KP_ID)
        if knowledge_point is None:
            raise ValueError("knowledge point not found")
        is_review = False
        review_focus = []
        reply_text = build_study_greeting(knowledge_point.name)

        # 如果传入了 session_id 且不是游客，尝试加载复习上下文
        if session_id and user_id != GUEST_USER_ID:
            from backend.app.services.review_context_service import safe_load_review_context
            # 从图实例中获取配置好的 provider
            provider = getattr(self._graph, "_review_context_provider", None)
            review_context = safe_load_review_context(provider, session_id, user_id)

            # 拼接greeting文本，提示用户进入复习模式
            if review_context and review_context.kp_id == knowledge_point.kp_id:
                is_review = True
                review_focus = review_context.review_focus
                focus_str = "、".join(review_focus)
                reply_text = (
                    f"欢迎进入专项复习！上次我们在「{focus_str}」等维度上发现了一些需要强化的漏洞。 "
                    f"这次请再次向我讲解一下{knowledge_point.name}，我们来看看这些地方掌握得怎么样了。"
                )

        return GreetingData(
                reply_text=reply_text,
                kp_id=knowledge_point.kp_id,
                kp_name=knowledge_point.name,
                is_review=is_review,
                review_focus=review_focus,
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
        report_finalizer=DiagnosticReportFinalizer(engine),
        profile_provider=_load_profile_from_db,
        review_context_provider=DefaultReviewContextProvider(engine),
    )


def _load_profile_from_db(user_id: str):
    """从数据库加载用户学情画像，供 graph 的 _load_context 节点调用。"""
    from sqlmodel import Session

    from backend.app.services.user_profile_service import UserProfileService

    with Session(engine) as db:
        return UserProfileService.get_profile_by_user_id(db, user_id)
