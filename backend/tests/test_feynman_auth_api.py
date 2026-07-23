import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.database import get_session
from backend.app.main import app
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.session_store import InMemorySessionStore


class FeynmanAuthApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        self.service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )
        self.service_patch = patch(
            "backend.app.api.routes.get_feynman_service",
            return_value=self.service,
        )
        self.service_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.service_patch.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def _login_headers(self) -> dict[str, str]:
        credentials = {"username": "student10", "password": "123456abc"}
        self.client.post("/api/v1/auth/register", json=credentials)
        response = self.client.post("/api/v1/auth/login", json=credentials)
        token = response.json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    def test_invalid_token_blocks_greeting_but_guest_is_allowed(self):
        guest_response = self.client.get("/api/v1/feynman/greeting")
        invalid_response = self.client.get(
            "/api/v1/feynman/greeting",
            headers={"Authorization": "Bearer invalid-token"},
        )

        self.assertEqual(guest_response.status_code, 200)
        self.assertEqual(invalid_response.status_code, 401)

    def test_session_detail_restores_owner_history(self):
        headers = self._login_headers()
        chat_response = self.client.post(
            "/api/v1/feynman/chat",
            headers=headers,
            json={
                "session_id": "owned-session",
                "kp_id": "kp-demo",
                "user_input": "Dijkstra 用于求单源最短路径",
            },
        )

        owner_response = self.client.get(
            "/api/v1/feynman/sessions/owned-session",
            headers=headers,
        )
        list_response = self.client.get(
            "/api/v1/feynman/sessions",
            headers=headers,
        )
        guest_response = self.client.get(
            "/api/v1/feynman/sessions/owned-session"
        )

        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(owner_response.status_code, 200)
        detail = owner_response.json()["data"]
        self.assertEqual(detail["session_id"], "owned-session")
        self.assertEqual(len(detail["chat_history"]), 2)
        self.assertIsNone(detail["report_data"])
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json()["data"][0]["session_id"],
            "owned-session",
        )
        self.assertEqual(guest_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
