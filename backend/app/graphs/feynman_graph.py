from typing import Literal, Optional

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.models.feynman import FeynmanChatData, FeynmanChatRequest, NextAction
from backend.app.services.kp_provider import (
    DEFAULT_KP_ID,
    KnowledgePoint,
    KnowledgePointProvider,
)
from backend.app.services.session_store import SessionState


RouteName = Literal["kp_missing", "off_topic", "ineffective", "evaluate", "report"]


class FeynmanGraphState(TypedDict, total=False):
    request: FeynmanChatRequest
    session: SessionState
    knowledge_point: Optional[KnowledgePoint]
    route: RouteName
    response: FeynmanChatData
    provider: str
    fallback_used: bool


class FeynmanGraph:
    def __init__(
        self,
        llm_client,
        fallback_client,
        kp_provider: KnowledgePointProvider,
        max_follow_ups: int,
        primary_provider_name: str,
    ) -> None:
        self._llm_client = llm_client
        self._fallback_client = fallback_client
        self._kp_provider = kp_provider
        self._max_follow_ups = max_follow_ups
        self._primary_provider_name = primary_provider_name
        self._graph = self._build_graph()

    async def run(
        self,
        request: FeynmanChatRequest,
        session: SessionState,
    ) -> FeynmanChatData:
        result = await self._graph.ainvoke({"request": request, "session": session})
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
                "evaluate": "evaluate",
                "report": "report",
            },
        )
        for node_name in ["kp_missing", "off_topic", "ineffective", "evaluate", "report"]:
            builder.add_edge(node_name, "persist_session")
        builder.add_edge("persist_session", END)
        return builder.compile()

    def _load_context(self, state: FeynmanGraphState) -> FeynmanGraphState:
        request = state["request"]
        session = state["session"]

        if request.kp_id and session.kp_id and request.kp_id != session.kp_id and session.messages:
            raise ValueError("session is already bound to another kp_id; reset it before switching")

        kp_id = request.kp_id or session.kp_id or DEFAULT_KP_ID
        knowledge_point = self._kp_provider.get(kp_id)
        if knowledge_point is None:
            session.kp_id = None
            session.kp_name = None
            session.material_id = None
            session.chapter_id = None
            return {"knowledge_point": None}

        session.kp_id = knowledge_point.kp_id
        session.kp_name = knowledge_point.name
        session.material_id = knowledge_point.material_id
        session.chapter_id = knowledge_point.chapter_id
        return {"knowledge_point": knowledge_point}

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

    async def _evaluate(self, state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None
        try:
            response = await self._llm_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=session.follow_up_count,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
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
            )
            response = _normalize_contract(response)
            return {"response": response, "provider": "mock", "fallback_used": True}

    async def _report(self, state: FeynmanGraphState) -> FeynmanGraphState:
        session = state["session"]
        request = state["request"]
        knowledge_point = state["knowledge_point"]
        assert knowledge_point is not None
        try:
            response = await self._llm_client.evaluate(
                messages=session.messages,
                user_input=request.user_input.strip(),
                follow_up_count=self._max_follow_ups,
                max_follow_ups=self._max_follow_ups,
                knowledge_point=knowledge_point,
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
