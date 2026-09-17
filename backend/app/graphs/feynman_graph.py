import re
from typing import Callable, Literal, Optional

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
from backend.app.services.report_quality import sanitize_report_against_user_text
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
    on_reply_delta: Optional[Callable[[str], None]]
    on_status: Optional[Callable[[str, str], None]]

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
        on_reply_delta: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> FeynmanChatData:
        result = await self._graph.ainvoke({
            "request": request, "session": session, "user_profile": profile,
            "on_reply_delta": on_reply_delta,
            "on_status": on_status,
        })
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
        elif state["request"].finish_requested:
            has_explanation = any(
                message.role == "user" and message.content.strip()
                for message in session.messages
            )
            route = "report" if has_explanation else "ineffective"
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
                    f"先把话题拉回「{knowledge_point.name}」吧。"
                    "你觉得它主要解决什么问题？用一句自己的话说说就行。"
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
        if state.get("on_status"):
            state["on_status"]("retrieving", "正在检索相关教材内容…")
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None

        rag_chunks: list[RetrievedChunk] = []
        try:
            latest_user_input = request.user_input.strip() or next(
                (
                    message.content for message in reversed(state["session"].messages)
                    if message.role == "user" and message.content.strip()
                ),
                knowledge_point.name,
            )
            raw_chunks = await self._rag_retriever.retrieve(
                query=latest_user_input,
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
        if state.get("on_status"):
            state["on_status"]("generating", "正在结合你的讲解组织追问…")
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        profile = state.get("user_profile")
        review_context = state.get("review_context")
        assert knowledge_point is not None
        try:
            evaluator = self._llm_client.evaluate
            extra_kwargs = {}
            if state.get("on_reply_delta") and hasattr(self._llm_client, "evaluate_stream"):
                evaluator = self._llm_client.evaluate_stream
                extra_kwargs["on_reply_delta"] = state["on_reply_delta"]
            response = await evaluator(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=session.follow_up_count,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
                **extra_kwargs,
            )
            response = _normalize_contract(response)
            response = _ensure_initial_understanding_check(
                response=response,
                session=session,
                user_input=request.user_input.strip(),
                knowledge_point=knowledge_point,
            )
            return {
                "response": response,
                "provider": self._primary_provider_name,
                "fallback_used": False,
            }
        except Exception:
            if state.get("on_status"):
                state["on_status"]("fallback", "主模型暂不可用，正在尝试备用回复…")
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
            response = _ensure_initial_understanding_check(
                response=response,
                session=session,
                user_input=request.user_input.strip(),
                knowledge_point=knowledge_point,
            )
            return {"response": response, "provider": "mock", "fallback_used": True}

    async def _report(self, state: FeynmanGraphState) -> FeynmanGraphState:
        if state.get("on_status"):
            state["on_status"]("generating", "正在逐维分析你的讲解并生成诊断…")
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        profile = state.get("user_profile")
        review_context = state.get("review_context")
        assert knowledge_point is not None
        try:
            evaluator = self._llm_client.evaluate
            extra_kwargs = {}
            if state.get("on_reply_delta") and hasattr(self._llm_client, "evaluate_stream"):
                evaluator = self._llm_client.evaluate_stream
                extra_kwargs["on_reply_delta"] = state["on_reply_delta"]
            response = await evaluator(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=self._max_follow_ups,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
                grounding_chunks=state.get("grounding_chunks", []),
                profile=profile,
                review_context=review_context,
                **extra_kwargs,
            )
            response = _normalize_contract(response)
            if response.next_action != NextAction.GENERATE_REPORT:
                raise ValueError("report route must return generate_report")
            return {
                "response": response,
                "provider": self._primary_provider_name,
                "fallback_used": False,
            }
        except Exception:
            if state.get("on_status"):
                state["on_status"]("fallback", "主模型暂不可用，正在尝试备用诊断…")
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
            if response.next_action != NextAction.GENERATE_REPORT:
                raise ValueError("fallback report route must return generate_report")
            return {"response": response, "provider": "mock", "fallback_used": True}

    @staticmethod
    def _persist_session(state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        route = state["route"]
        response = _normalize_contract(state["response"])

        # 模型引用的“用户原话”必须真的出现在历史用户输入中；无证据时宁可留空。
        if response.final_report is not None:
            user_texts = [
                message.content for message in session.messages if message.role == "user"
            ] + [request.user_input.strip()]
            for dimension in response.final_report.dimensions:
                dimension.evidence = [
                    item for item in dimension.evidence
                    if any(item.quote in user_text for user_text in user_texts)
                ]
            response = sanitize_report_against_user_text(response, user_texts)
        if response.review_plan is not None:
            known_pages = {chunk.page_no for chunk in state.get("grounding_chunks", [])}
            for item in response.review_plan.reread_guide:
                page_numbers = set()
                for start, end in re.findall(
                    r"(\d+)\s*(?:[-—~～至到]\s*(\d+)\s*)?页", item.page_hint
                ):
                    first, last = int(start), int(end or start)
                    if last < first or last - first > 20:
                        page_numbers.clear()
                        break
                    page_numbers.update(range(first, last + 1))
                if not page_numbers or not page_numbers.issubset(known_pages):
                    item.page_hint = ""
                else:
                    item.page_hint = "、".join(f"第{page}页" for page in sorted(page_numbers))

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

    if user_input:
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
        data.review_plan = None
    if data.next_action == NextAction.GENERATE_REPORT:
        if data.card_preview is None or data.final_report is None:
            raise ValueError("generate_report requires card_preview and final_report")
        # 报告已经生成时，聊天气泡不能再抛出一个新问题。模型偶尔会同时
        # 返回 generate_report 和追问文案，这会让用户误以为还必须继续作答。
        if "？" in data.reply_text or "?" in data.reply_text:
            focus = data.card_preview.summary.rstrip("。；;！!")
            data.reply_text = (
                "这轮讲解可以收束了。诊断报告已经生成，"
                f"下面会说明你已经覆盖的内容，以及仍可补强的重点：{focus}。"
            )
    return data


def _ensure_initial_understanding_check(
    response: FeynmanChatData,
    session: SessionState,
    user_input: str,
    knowledge_point: KnowledgePoint,
) -> FeynmanChatData:
    """Keep a textbook diagnosis from ending after an unverified first explanation.

    A correct definition is useful evidence, but the teaching flow should normally
    observe one application or causal explanation before producing a scored report.
    The model prompt makes that pedagogical choice; this guard prevents an occasional
    premature ``generate_report`` from skipping the interaction entirely.
    """
    if response.next_action != NextAction.GENERATE_REPORT:
        return response
    if session.follow_up_count > 0 or _requests_immediate_report(user_input):
        return response
    return FeynmanChatData(
        next_action=NextAction.FOLLOW_UP,
        reply_text=(
            f"你已经把「{knowledge_point.name}」的定义、基本做法和作用讲清楚了。"
            "为了确认你不只是记住了概念，再补一个最小例子："
            "它在这个例子里具体怎样工作，又避免了什么问题？"
        ),
    )


def _requests_immediate_report(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    requests = (
        "直接生成报告",
        "立即生成报告",
        "现在生成报告",
        "直接出报告",
        "结束并评分",
        "不用追问",
        "不要追问",
    )
    return any(request in compact for request in requests)
