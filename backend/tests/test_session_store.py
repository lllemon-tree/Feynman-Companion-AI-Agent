import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from backend.app.models.feynman import ChatMessage, FeynmanChatRequest
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.session_store import (
    SQLSessionStore,
    SessionAccessDeniedError,
)


class SQLSessionStoreTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    async def test_conversation_survives_service_recreation(self):
        first_service = FeynmanService(
            store=SQLSessionStore(self.engine),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )
        await first_service.chat(
            FeynmanChatRequest(
                session_id="persisted-session",
                user_input="Dijkstra 用来求带权图中的最短路径",
            ),
            user_id="user-a",
        )

        second_service = FeynmanService(
            store=SQLSessionStore(self.engine),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )
        debug = second_service.inspect_session("persisted-session", user_id="user-a")

        self.assertTrue(debug.exists)
        self.assertEqual(debug.follow_up_count, 1)
        self.assertEqual(debug.message_count, 2)
        self.assertEqual(debug.recent_messages[0].role, "user")
        summaries = second_service.list_sessions(user_id="user-a")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].session_id, "persisted-session")

    def test_session_is_bound_to_owner(self):
        store = SQLSessionStore(self.engine)
        state = store.get_or_create("private-session", user_id="user-a")
        state.messages.append(ChatMessage(role="user", content="我的讲解"))
        store.save(state)

        with self.assertRaises(SessionAccessDeniedError):
            store.get("private-session", user_id="user-b")

    def test_reset_removes_persisted_session(self):
        store = SQLSessionStore(self.engine)
        state = store.get_or_create("reset-session", user_id="user-a")
        store.save(state)

        self.assertTrue(store.reset("reset-session", user_id="user-a"))
        self.assertIsNone(store.get("reset-session", user_id="user-a"))
