import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.api.conversations import get_conversation_service
from backend.app.core.database import get_session
from backend.app.main import app
from backend.app.services.conversation_service import ConversationService


class FakeConversationClient:
    invalid_quote = False
    stream_error = False
    assessment_history = ""
    last_model = ""
    last_history = ""

    async def respond_in_conversation(self, mode, history, user_input, model=None):
        self.last_model = model
        self.last_history = history
        return "这是专家解释。" if mode == "expert" else "你能再解释为什么吗？"

    async def stream_in_conversation(self, mode, history, user_input, model=None):
        self.last_model = model
        self.last_history = history
        yield "这是"
        if self.stream_error:
            raise RuntimeError("provider connection closed")
        yield "流式解释。"

    async def assess_free_explanation(self, history, user_explanations, model=None):
        self.last_model = model
        self.assessment_history = history
        return {
            "topic": "Dijkstra 算法",
            "strengths": ["提到了最短路径"],
            "gaps": ["还未说明非负边权条件"],
            "evidence": [{
                "quote": "不存在的话" if self.invalid_quote else "求单源最短路径",
                "observation": "指出了算法的目标",
            }],
            "next_step": "试着解释为什么要求边权非负。",
        }


class ConversationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        SQLModel.metadata.create_all(self.engine)

        def override_session():
            with Session(self.engine) as db:
                yield db

        self.fake_client = FakeConversationClient()
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_conversation_service] = lambda: ConversationService(self.fake_client)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def _headers(self, username="student10"):
        credentials = {"username": username, "password": "123456abc"}
        self.client.post("/api/v1/auth/register", json=credentials)
        token = self.client.post("/api/v1/auth/login", json=credentials).json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_expert_then_beginner_history_and_owner(self):
        headers = self._headers()
        other = self._headers("student11")
        created = self.client.post("/api/v1/conversations", headers=headers)
        self.assertEqual(created.status_code, 200)
        conversation_id = created.json()["data"]["id"]

        expert = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers,
            json={"content": "什么是 Dijkstra 算法？", "mode": "expert", "model": "deepseek-flash"},
        )
        self.assertEqual(self.fake_client.last_model, "deepseek-flash")
        beginner = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers,
            json={"content": "它用来求单源最短路径", "mode": "beginner"},
        )
        detail = self.client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
        summary = self.client.get("/api/v1/conversations", headers=headers)

        self.assertEqual(expert.status_code, 200)
        self.assertEqual(beginner.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual([item["mode"] for item in detail.json()["data"]["messages"]],
                         ["expert", "expert", "beginner", "beginner"])
        self.assertEqual(detail.json()["data"]["messages"][0]["model"], "deepseek-flash")
        self.assertEqual(summary.json()["data"][0]["id"], conversation_id)
        self.assertEqual(self.client.get(f"/api/v1/conversations/{conversation_id}", headers=other).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/conversations").status_code, 401)

    def test_model_catalog_and_invalid_model_rejected(self):
        catalog = self.client.get("/api/v1/conversations/models")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("deepseek-flash", [item["id"] for item in catalog.json()["data"]["models"]])
        headers = self._headers()
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        invalid = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers,
            json={"content": "你好", "mode": "expert", "model": "not-allowed"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/conversations/{conversation_id}", headers=headers).json()["data"]["messages"], [])

    def test_streamed_answer_uses_selected_model_and_persists_after_completion(self):
        headers = self._headers()
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        response = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream", headers=headers,
            json={"content": "讲讲索引", "mode": "expert", "model": "deepseek-flash"},
        )
        events = [json.loads(line) for line in response.text.splitlines() if line]
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["type"] for item in events], ["delta", "delta", "done"])
        self.assertEqual("".join(item["text"] for item in events[:-1]), "这是流式解释。")
        self.assertEqual(self.fake_client.last_model, "deepseek-flash")
        self.assertEqual(events[-1]["data"]["assistant_message"]["model"], "deepseek-flash")
        saved = self.client.get(f"/api/v1/conversations/{conversation_id}", headers=headers).json()["data"]
        self.assertEqual([item["content"] for item in saved["messages"]], ["讲讲索引", "这是流式解释。"])

    def test_user_edited_learning_profile_influences_free_chat_context(self):
        headers = self._headers()
        self.client.post("/api/v1/user/profile", headers=headers, json={
            "exam_subject": "计算机", "preparation_stage": "基础", "pain_points": ["概念容易混淆"]
        })
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        response = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream", headers=headers,
            json={"content": "解释索引", "mode": "expert", "model": "deepseek-flash"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("备考阶段：基础", self.fake_client.last_history)
        self.assertIn("概念容易混淆", self.fake_client.last_history)

    def test_incomplete_stream_does_not_save_a_partial_answer(self):
        headers = self._headers()
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        self.fake_client.stream_error = True
        response = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages/stream", headers=headers,
            json={"content": "解释索引", "mode": "expert", "model": "deepseek-flash"},
        )
        events = [json.loads(line) for line in response.text.splitlines() if line]
        self.assertEqual([item["type"] for item in events], ["delta", "error"])
        saved = self.client.get(f"/api/v1/conversations/{conversation_id}", headers=headers).json()["data"]
        self.assertEqual(saved["messages"], [])

    def test_assessment_only_quotes_users_beginner_words(self):
        headers = self._headers()
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        endpoint = f"/api/v1/conversations/{conversation_id}"
        self.client.post(f"{endpoint}/messages", headers=headers,
                         json={"content": "专家请告诉我标准答案", "mode": "expert"})
        self.client.post(f"{endpoint}/messages", headers=headers,
                         json={"content": "算法用来求单源最短路径", "mode": "beginner"})
        assessment = self.client.post(f"{endpoint}/assessment", headers=headers,
                                      json={"mode": "beginner"})
        self.assertEqual(assessment.status_code, 200)
        data = assessment.json()["data"]["assessment"]
        self.assertEqual(data["evidence"][0]["quote"], "求单源最短路径")
        self.assertEqual(data["basis"], "无指定教材；根据用户讲解与通用知识评估")
        self.assertNotIn("专家请告诉我标准答案", self.fake_client.assessment_history)

        self.fake_client.invalid_quote = True
        invalid = self.client.post(f"{endpoint}/assessment", headers=headers,
                                   json={"mode": "beginner"})
        self.assertEqual(invalid.status_code, 502)
        self.assertEqual(len(self.client.get(endpoint, headers=headers).json()["data"]["messages"]), 5)

    def test_unconfigured_model_does_not_fake_an_answer(self):
        headers = self._headers()
        conversation_id = self.client.post("/api/v1/conversations", headers=headers).json()["data"]["id"]
        app.dependency_overrides[get_conversation_service] = lambda: ConversationService(None)
        response = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages", headers=headers,
            json={"content": "你好", "mode": "expert"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get(f"/api/v1/conversations/{conversation_id}", headers=headers).json()["data"]["messages"], [])


if __name__ == "__main__":
    unittest.main()
