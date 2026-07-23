import unittest

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.feynman import FeynmanChatRequest, NextAction, ResetSessionRequest
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.session_store import InMemorySessionStore


class FailingLLMClient:
    async def evaluate(self, **kwargs):
        raise RuntimeError("simulated provider failure")


class RecordingLLMClient:
    def __init__(self):
        self.calls = 0
        self._delegate = MockLLMClient()

    async def evaluate(self, **kwargs):
        self.calls += 1
        return await self._delegate.evaluate(**kwargs)


class FeynmanServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )

    async def test_off_topic_does_not_generate_report(self):
        response = await self.service.chat(
            FeynmanChatRequest(session_id="s1", user_input="今天天气怎么样")
        )
        self.assertEqual(response.next_action, NextAction.GUIDE_TOPIC)
        self.assertIsNone(response.card_preview)
        self.assertIsNone(response.final_report)
        debug = self.service.inspect_session("s1")
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.off_topic_count, 1)

    async def test_follow_up_then_report_after_max_rounds(self):
        first = await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="Dijkstra 是求图最短路径的算法")
        )
        self.assertEqual(first.next_action, NextAction.FOLLOW_UP)

        await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="它每次选未访问里距离最小的节点")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="然后对相邻节点做松弛更新")
        )
        final = await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="非负权保证后续不会绕出更短路径")
        )
        self.assertEqual(final.next_action, NextAction.GENERATE_REPORT)
        self.assertIsNotNone(final.card_preview)
        self.assertIsNotNone(final.final_report)

    async def test_ineffective_answer_returns_hint_without_report(self):
        response = await self.service.chat(
            FeynmanChatRequest(session_id="s3", user_input="不会")
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertIsNone(response.card_preview)
        self.assertIsNone(response.final_report)
        debug = self.service.inspect_session("s3")
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.invalid_answer_count, 1)

    async def test_final_report_is_sticky_until_reset(self):
        session_id = "s4"
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="Dijkstra 是求图最短路径的算法")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="它每次选未访问里距离最小的节点")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="然后对相邻节点做松弛更新")
        )
        final = await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="非负权保证后续不会绕出更短路径")
        )
        again = await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="我想继续补充一些内容")
        )
        self.assertEqual(final, again)

    async def test_reset_clears_session_state(self):
        session_id = "s5"
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="Dijkstra 是求图最短路径的算法")
        )
        before = self.service.inspect_session(session_id)
        self.assertTrue(before.exists)
        self.assertGreater(before.follow_up_count, 0)

        reset = self.service.reset(ResetSessionRequest(session_id=session_id))
        after = self.service.inspect_session(session_id)

        self.assertTrue(reset.reset)
        self.assertTrue(after.exists)
        self.assertEqual(after.follow_up_count, 0)
        self.assertEqual(after.message_count, 0)
        self.assertFalse(after.ended)

    async def test_inspect_missing_session(self):
        debug = self.service.inspect_session("missing-session")
        self.assertFalse(debug.exists)
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.message_count, 0)

    async def test_chat_binds_session_to_dynamic_knowledge_point(self):
        await self.service.chat(
            FeynmanChatRequest(
                session_id="dynamic-kp",
                kp_id="kp-demo2",
                user_input="Floyd 是一个求全源最短路径的动态规划算法",
            )
        )
        debug = self.service.inspect_session("dynamic-kp")
        self.assertEqual(debug.kp_id, "kp-demo2")
        self.assertEqual(debug.kp_name, "Floyd 算法")
        self.assertEqual(debug.material_id, "mat-demo")
        self.assertEqual(debug.chapter_id, "ch-demo")

    async def test_dynamic_kp_generates_generic_report_without_dijkstra_details(self):
        session_id = "floyd-report"
        answers = [
            "Floyd 用动态规划计算任意两点间最短路径",
            "状态表示只允许前 k 个点作为中间点",
            "转移时比较原距离和经过 k 的两段距离之和",
            "它可以处理负权边，但不能存在负权环",
        ]
        response = None
        for answer in answers:
            response = await self.service.chat(
                FeynmanChatRequest(
                    session_id=session_id,
                    kp_id="kp-demo2",
                    user_input=answer,
                )
            )
        self.assertIsNotNone(response)
        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        self.assertIn("Floyd", response.final_report.overall_comment)
        self.assertNotIn("Dijkstra", response.final_report.overall_comment)

    async def test_missing_knowledge_point_returns_guide_topic_and_clears_binding(self):
        response = await self.service.chat(
            FeynmanChatRequest(
                session_id="missing-kp",
                kp_id="kp-deleted",
                user_input="这是我的讲解",
            )
        )
        self.assertEqual(response.next_action, NextAction.GUIDE_TOPIC)
        self.assertIn("重新选择知识点", response.reply_text)
        self.assertIsNone(self.service.inspect_session("missing-kp").kp_id)

    async def test_switching_kp_requires_session_reset(self):
        session_id = "switch-kp"
        await self.service.chat(
            FeynmanChatRequest(
                session_id=session_id,
                kp_id="kp-demo",
                user_input="Dijkstra 是求最短路径的算法",
            )
        )
        with self.assertRaisesRegex(ValueError, "reset"):
            await self.service.chat(
                FeynmanChatRequest(
                    session_id=session_id,
                    kp_id="kp-demo2",
                    user_input="Floyd 是动态规划算法",
                )
            )

    async def test_llm_failure_falls_back_to_mock(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=FailingLLMClient(),
            fallback_client=MockLLMClient(),
        )
        response = await service.chat(
            FeynmanChatRequest(
                session_id="fallback",
                kp_id="kp-demo",
                user_input="Dijkstra 用来求图上的最短路径",
            )
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        debug = service.inspect_session("fallback")
        self.assertEqual(debug.last_provider, "mock")
        self.assertTrue(debug.fallback_used)

    async def test_graph_contains_expected_runtime_nodes(self):
        graph = self.service.draw_graph_mermaid()
        for node_name in [
            "load_context",
            "route_input",
            "kp_missing",
            "off_topic",
            "ineffective",
            "evaluate",
            "report",
            "persist_session",
        ]:
            self.assertIn(node_name, graph)

    async def test_forced_report_uses_primary_client_before_fallback(self):
        primary = RecordingLLMClient()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=primary,
            fallback_client=MockLLMClient(),
        )
        session_id = "primary-report"
        for answer in [
            "Dijkstra 用于求最短路径",
            "它选择当前距离最小的未访问节点",
            "然后松弛相邻边",
            "非负权保证已确定距离不会再变短",
        ]:
            response = await service.chat(
                FeynmanChatRequest(session_id=session_id, user_input=answer)
            )

        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        self.assertEqual(primary.calls, 4)


class FeynmanApiTest(unittest.TestCase):
    def test_greeting_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 200)
        self.assertIn("reply_text", body["data"])
        self.assertEqual(body["data"]["kp_id"], "kp-demo")
        self.assertEqual(body["data"]["kp_name"], "Dijkstra 算法")

    def test_dynamic_greeting_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting", params={"kp_id": "kp-demo2"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["kp_id"], "kp-demo2")
        self.assertIn("Floyd", body["data"]["reply_text"])

    def test_missing_greeting_kp_returns_404(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting", params={"kp_id": "kp-missing"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
