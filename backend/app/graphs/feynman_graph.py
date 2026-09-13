from typing import Literal, Optional

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.models.feynman import FeynmanChatData, FeynmanChatRequest, NextAction
from backend.app.models.rag import RetrievedChunk
from backend.app.models.review_context import ReviewContext
from backend.app.services.kp_provider import (
    DEFAULT_KP_ID,
    KnowledgePoint,
    KnowledgePointProvider,
)
from backend.app.services.rag_retriever import RAGRetriever
from backend.app.services.review_context_service import DefaultReviewContextProvider, ReviewContextProvider, safe_load_review_context
from backend.app.services.session_store import SessionState
from backend.app.models.user_profile import UserProfileResponse

RouteName = Literal["kp_missing", "off_topic", "ineffective", "evaluate", "report"]

# 流动的数据
class FeynmanGraphState(TypedDict, total=False):
    request: FeynmanChatRequest # 用户的聊天请求数据，包含用户刚输入的聊天内容
    session: SessionState # 当前会话的记忆库，存着历史聊天记录和各类计数（比如这是第几次追问）。
    knowledge_point: Optional[KnowledgePoint]
    route: RouteName # 定下一步去哪个节点的“路标”（比如判定为跑题 off_topic，或是正常评估
    response: FeynmanChatData # 最终打包好、准备返回给前端的回复数据（包含动作和文本）
    provider: str # 记录这次回答是真实的 LLM 生成的，还是规则引擎生成的。
    fallback_used: bool # 记录主模型是否因为超时或报错，从而启用了备用模型。
    grounding_chunks: list[RetrievedChunk] # 用于支持回答的检索到的文本块
    user_profile: Optional[UserProfileResponse]
    review_context: Optional[ReviewContext]

class FeynmanGraph:
    def __init__(
        self,
        llm_client,
        fallback_client,
        kp_provider: KnowledgePointProvider,
        max_follow_ups: int,
        primary_provider_name: str,
        rag_retriever: RAGRetriever,
        profile_provider=None,
        review_context_provider: Optional[ReviewContextProvider] = None,
    ) -> None:
        self._llm_client = llm_client
        self._fallback_client = fallback_client
        self._kp_provider = kp_provider
        self._max_follow_ups = max_follow_ups
        self._primary_provider_name = primary_provider_name
        self._rag_retriever = rag_retriever
        self._profile_provider = profile_provider
        self._graph = self._build_graph()
        self._review_context_provider = review_context_provider or DefaultReviewContextProvider()

    async def run(
        self,
        request: FeynmanChatRequest,
        session: SessionState,
        profile: Optional[UserProfileResponse] = None,
    ) -> FeynmanChatData:
        result = await self._graph.ainvoke({"request": request, "session": session, "user_profile": profile})
        return result["response"]

    def draw_mermaid(self) -> str:
        return self._graph.get_graph().draw_mermaid()

    def _build_graph(self):
        builder = StateGraph(FeynmanGraphState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("route_input", self._route_input)
        builder.add_node("kp_missing", self._handle_kp_missing)
        builder.add_node("off_topic", self._handle_off_topic)
        builder.add_node("ineffective", self._handle_ineffective)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("evaluate", self._evaluate)
        builder.add_node("report", self._report)
        builder.add_node("persist_session", self._persist_session)

        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "route_input")
        builder.add_conditional_edges(
            "route_input",
            self._select_route,
            {
                "kp_missing": "kp_missing",
                "off_topic": "off_topic",
                "ineffective": "ineffective",
                "evaluate": "retrieve",
                "report": "retrieve",
            },
        )
        builder.add_conditional_edges(
            "retrieve",
            self._select_route,
            {
                "evaluate": "evaluate",
                "report": "report",
            },
        )
        for node_name in ["kp_missing", "off_topic", "ineffective", "evaluate", "report"]:
            builder.add_edge(node_name, "persist_session")
        builder.add_edge("persist_session", END)
        return builder.compile()

    # 传参用户request和当前session，调用provider工具，return knowledge_point和user_profile 到 state里面
    def _load_context(self, state: FeynmanGraphState) -> FeynmanGraphState:
        # 1. 从 state 里拿到当前的 session_id 和 user_id
        request = state["request"]
        session = state["session"]

        # 开场先加载用户画像（游客或无 provider 时返回 None，安全降级为默认 Prompt）
        profile = None
        if self._profile_provider is not None:
            try:
                profile = self._profile_provider(session.user_id)
            except Exception:
                profile = None
        # 如果 request 里传了 kp_id，且和 session 里原来的 kp_id 不同，且 session 已经有聊天记录了，就报错
        # 这是为了防止用户在中途切换知识点时，原来的聊天记录和新的知识点不匹配，导致模型生成的回答不合理。
        if request.kp_id and session.kp_id and request.kp_id != session.kp_id and session.messages:
            raise ValueError("session is already bound to another kp_id; reset it before switching")

        # 2. 从 request 或 session 里获取知识点 ID，优先级：request > session > 默认值
        kp_id = request.kp_id or session.kp_id or DEFAULT_KP_ID
        # 3. 调用知识点提供者，获取知识点对象
        knowledge_point = self._kp_provider.get(kp_id)

        # 如果知识点不存在，清空 session 里的知识点信息，并返回 None
        if knowledge_point is None:
            session.kp_id = None
            session.kp_name = None
            session.material_id = None
            session.chapter_id = None
            return {"knowledge_point": None, "user_profile": profile}
        # 如果知识点存在，更新 session 里的知识点信息，并返回 knowledge_point 和 user_profile
        session.kp_id = knowledge_point.kp_id
        session.kp_name = knowledge_point.name
        session.material_id = knowledge_point.material_id
        session.chapter_id = knowledge_point.chapter_id

        # 4. 调用复习上下文提供者，获取复习上下文对象
        review_context = safe_load_review_context(
            provider=self._review_context_provider,
            session_id=session.session_id,
            user_id=session.user_id,
        )
        if review_context is not None and review_context.kp_id != kp_id:
            raise ValueError("review session is bound to another kp_id")
        # 5. 将复习上下文对象存入 state，供后续节点使用
        state["review_context"] = review_context
        return {"knowledge_point": knowledge_point, "user_profile": profile, "review_context": review_context}

    def _route_input(self, state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        user_input = state["request"].user_input.strip()
        knowledge_point = state.get("knowledge_point")

        if knowledge_point is None:
            route: RouteName = "kp_missing"
        elif _is_off_topic(user_input, knowledge_point):
            route = "off_topic"
        elif _is_ineffective_answer(user_input):
            route = "ineffective"
        elif session.follow_up_count >= self._max_follow_ups:
            route = "report"
        else:
            # 正常路径：返回 evaluate，graph 会先经过 retrieve 节点再进入 evaluate
            route = "evaluate"
        return {"route": route}

    @staticmethod
    def _select_route(state: FeynmanGraphState) -> RouteName:
        return state["route"]

    @staticmethod
    def _handle_kp_missing(state: FeynmanGraphState) -> FeynmanGraphState:
        return {
            "response": FeynmanChatData(
                next_action=NextAction.GUIDE_TOPIC,
                reply_text="该知识点不存在或已被删除，请重新选择知识点再开始讲解。",
            ),
            "provider": "rule",
            "fallback_used": False,
        }

    @staticmethod
    def _handle_off_topic(state: FeynmanGraphState) -> FeynmanGraphState:
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None
        return {
            "response": FeynmanChatData(
                next_action=NextAction.GUIDE_TOPIC,
                reply_text=(
                    f"这个问题先放一放，我们这轮只围绕{knowledge_point.name}。"
                    "你可以先讲讲它解决什么问题。"
                ),
            ),
            "provider": "rule",
            "fallback_used": False,
        }

    @staticmethod
    def _handle_ineffective(state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None
        if session.invalid_answer_count + 1 >= 2:
            reply = (
                f"先别硬背{knowledge_point.name}的完整答案。你可以围绕三个方向重新组织："
                "适用前提、核心过程、为什么成立。现在试着用自己的话讲一遍。"
            )
        else:
            reply = f"可以先从最简单的问题说起：{knowledge_point.name}主要解决什么问题？"
        return {
            "response": FeynmanChatData(next_action=NextAction.FOLLOW_UP, reply_text=reply),
            "provider": "rule",
            "fallback_used": False,
        }
    # 语义搜索
    async def _retrieve(self, state: FeynmanGraphState) -> FeynmanGraphState:
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None

        rag_chunks: list[RetrievedChunk] = []
        try:
            raw_chunks = await self._rag_retriever.retrieve(
                query=request.user_input.strip(),
                material_id=knowledge_point.material_id,
                top_k=3,
            )
            rag_chunks = [
                chunk
                if isinstance(chunk, RetrievedChunk)
                else RetrievedChunk.model_validate(chunk)
                for chunk in raw_chunks
            ]
        except Exception as e:
            print(f"⚠️ RAG retrieve failed: {type(e).__name__}: {e}")
            rag_chunks = []

        merged: list[RetrievedChunk] = []
        seen_ids: set[str] = set()
        for chunk in [*knowledge_point.source_chunks, *rag_chunks]:
            if chunk.chunk_id in seen_ids:
                continue
            seen_ids.add(chunk.chunk_id)
            merged.append(chunk)
        src_ids = [c.chunk_id for c in knowledge_point.source_chunks]
        rag_ids = [c.chunk_id for c in rag_chunks]
        print(f"📖 page grounding ({len(src_ids)}): {src_ids}")
        print(f"🔍 RAG retrieval  ({len(rag_ids)}): {rag_ids}")
        return {"grounding_chunks": merged}

    async def _evaluate(self, state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        profile = state.get("user_profile")
        review_context = state.get("review_context")
        assert knowledge_point is not None
        try:
            response = await self._llm_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=session.follow_up_count,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
            )
            response = _normalize_contract(response)
            return {
                "response": response,
                "provider": self._primary_provider_name,
                "fallback_used": False,
            }
        except Exception:
            response = await self._fallback_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=session.follow_up_count,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
            )
            response = _normalize_contract(response)
            return {"response": response, "provider": "mock", "fallback_used": True}

    async def _report(self, state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        profile = state.get("user_profile")
        review_context = state.get("review_context")
        assert knowledge_point is not None
        try:
            response = await self._llm_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=self._max_follow_ups,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
            )
            response = _normalize_contract(response)
            return {
                "response": response,
                "provider": self._primary_provider_name,
                "fallback_used": False,
            }
        except Exception:
            response = await self._fallback_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=self._max_follow_ups,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
            )
            response = _normalize_contract(response)
            return {"response": response, "provider": "mock", "fallback_used": True}

    @staticmethod
    def _persist_session(state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        route = state["route"]
        response = _normalize_contract(state["response"])

        if route == "off_topic":
            session.off_topic_count += 1
        elif route == "ineffective":
            session.invalid_answer_count += 1

        if route == "evaluate" and response.next_action == NextAction.FOLLOW_UP:
            session.follow_up_count += 1
        elif response.next_action == NextAction.GENERATE_REPORT:
            session.ended = True
            session.final_response = response

        session.last_provider = state["provider"]
        session.fallback_used = state["fallback_used"]
        _append_turn(session, request.user_input.strip(), response.reply_text)
        return {"response": response}


def _append_turn(session: SessionState, user_input: str, assistant_reply: str) -> None:
    from backend.app.models.feynman import ChatMessage

    session.messages.append(ChatMessage(role="user", content=user_input))
    session.messages.append(ChatMessage(role="assistant", content=assistant_reply))


def _is_off_topic(text: str, knowledge_point: KnowledgePoint) -> bool:
    normalized = text.lower()
    off_topic_words = ["天气", "吃饭", "电影", "游戏", "新闻", "股票", "旅游"]
    kp_name = knowledge_point.name.lower().replace(" ", "")
    compact_text = normalized.replace(" ", "")
    topic_names = [kp_name, kp_name.replace("算法", "")]
    mentions_topic = any(name and name in compact_text for name in topic_names)
    return any(word in normalized for word in off_topic_words) and not mentions_topic


def _is_ineffective_answer(text: str) -> bool:
    normalized = text.strip().lower()
    ineffective = ["不知道", "不会", "不懂", "不清楚", "讲不出来", "不知道怎么讲", "no idea"]
    return normalized in ineffective or len(normalized) <= 2


def _normalize_contract(data: FeynmanChatData) -> FeynmanChatData:
    if data.next_action in {NextAction.FOLLOW_UP, NextAction.GUIDE_TOPIC}:
        data.card_preview = None
        data.final_report = None
    if data.next_action == NextAction.GENERATE_REPORT:
        if data.card_preview is None or data.final_report is None:
            raise ValueError("generate_report requires card_preview and final_report")
    return data
