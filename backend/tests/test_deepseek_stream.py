"""The selected model must reach the provider; reasoning tokens stay off the UI."""

import json
import unittest
from unittest.mock import patch

import httpx

from backend.app.core.config import Settings
from backend.app.services.deepseek_client import DeepSeekClient
from backend.app.services.kp_provider import KnowledgePoint


class DeepSeekStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_knowledge_card_uses_flash_model_without_thinking(self):
        captured = {}

        def respond(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps({
                    "coverage_level": "partial",
                    "coverage_notice": "教材部分覆盖",
                    "estimated_minutes": 3,
                    "sections": [],
                })}}],
            })

        transport = httpx.MockTransport(respond)
        original_client = httpx.AsyncClient
        settings = Settings(
            llm_provider="deepseek",
            deepseek_api_key="unit-test-only",
            deepseek_model="deepseek-v4-flash",
            knowledge_card_model="deepseek-v4-flash",
        )
        point = KnowledgePoint(
            kp_id="kp-card",
            name="封装",
            summary="隐藏实现细节",
            rubric={},
            material_id="mat-card",
            chapter_id="ch-card",
        )
        with patch(
            "backend.app.services.deepseek_client.httpx.AsyncClient",
            side_effect=lambda **kwargs: original_client(transport=transport, **kwargs),
        ):
            await DeepSeekClient(settings).generate_knowledge_card(point)

        self.assertEqual(captured["model"], "deepseek-v4-flash")
        self.assertEqual(captured["thinking"], {"type": "disabled"})
        self.assertEqual(captured["response_format"], {"type": "json_object"})

    async def test_textbook_json_stream_exposes_only_reply_text(self):
        captured = {}
        deltas = []
        output = json.dumps({
            "reply_text": "你说到了非负权。那为什么选中的点以后不会更短？\n试着想一个反例。",
            "next_action": "follow_up",
            "card_preview": None,
            "final_report": None,
            "review_plan": None,
        }, ensure_ascii=True)

        def respond(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            chunks = [output[:18], output[18:32], output[32:45], output[45:68], output[68:]]
            body = "".join(
                f"data: {json.dumps({'choices': [{'delta': {'content': chunk}}]})}\n\n"
                for chunk in chunks
            ) + "data: [DONE]\n\n"
            return httpx.Response(200, text=body)

        transport = httpx.MockTransport(respond)
        original_client = httpx.AsyncClient
        settings = Settings(llm_provider="deepseek", deepseek_api_key="unit-test-only")
        with patch(
            "backend.app.services.deepseek_client.httpx.AsyncClient",
            side_effect=lambda **kwargs: original_client(transport=transport, **kwargs),
        ):
            result = await DeepSeekClient(settings)._request_json_streaming(
                "return JSON", "explanation", deltas.append,
            )

        self.assertTrue(captured["stream"])
        self.assertEqual(captured["thinking"], {"type": "disabled"})
        self.assertEqual(captured["response_format"], {"type": "json_object"})
        self.assertEqual("".join(deltas), result["reply_text"])
        self.assertNotIn("next_action", "".join(deltas))

    async def test_selected_model_and_stream_deltas(self):
        captured = {}

        def respond(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            body = (
                'data: {"choices":[{"delta":{"reasoning_content":"hidden"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"，世界"}}]}\n\n'
                'data: [DONE]\n\n'
            )
            return httpx.Response(200, text=body)

        transport = httpx.MockTransport(respond)
        original_client = httpx.AsyncClient
        settings = Settings(llm_provider="deepseek", deepseek_api_key="unit-test-only")
        with patch(
            "backend.app.services.deepseek_client.httpx.AsyncClient",
            side_effect=lambda **kwargs: original_client(transport=transport, **kwargs),
        ):
            chunks = [part async for part in DeepSeekClient(settings).stream_in_conversation(
                "expert", "（新对话）", "你好", "deepseek-flash"
            )]

        self.assertEqual(captured["model"], "deepseek-flash")
        self.assertTrue(captured["stream"])
        self.assertEqual(captured["thinking"], {"type": "disabled"})
        self.assertIn("贯彻费曼学习法", captured["messages"][0]["content"])
        self.assertIn("不要为了互动而连续反问", captured["messages"][0]["content"])
        self.assertEqual(chunks, ["你好", "，世界"])


if __name__ == "__main__":
    unittest.main()
