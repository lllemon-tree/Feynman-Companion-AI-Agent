import unittest

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.database import get_session
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.auth import User
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.models.user_profile import UserProfile


class Week6ProfileAndGapApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all(
                [
                    User(id="user-a", username="week6-a", password_hash="!"),
                    UserProfile(user_id="user-a"),
                    User(id="user-b", username="week6-b", password_hash="!"),
                    UserProfile(user_id="user-b"),
                    KnowledgeGap(
                        id="gap-a",
                        user_id="user-a",
                        kp_id="kp-a",
                        kp_name="知识点 A",
                        dimension="理解深度",
                        score=4,
                        severity=4,
                    ),
                ]
            )
            session.commit()

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.user_a_headers = {
            "Authorization": (
                f"Bearer {create_access_token('user-a', 'week6-a')}"
            )
        }
        self.user_b_headers = {
            "Authorization": (
                f"Bearer {create_access_token('user-b', 'week6-b')}"
            )
        }

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_profile_get_post_and_patch_are_user_scoped(self) -> None:
        empty = self.client.get(
            "/api/v1/user/profile",
            headers=self.user_a_headers,
        )
        saved = self.client.post(
            "/api/v1/user/profile",
            headers=self.user_a_headers,
            json={
                "exam_subject": "计算机",
                "preparation_stage": "基础",
                "pain_points": ["知识碎片化"],
            },
        )
        updated = self.client.patch(
            "/api/v1/user/profile",
            headers=self.user_a_headers,
            json={"preparation_stage": "强化"},
        )
        other_user = self.client.get(
            "/api/v1/user/profile",
            headers=self.user_b_headers,
        )

        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json()["data"]["exam_subject"])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["data"]["exam_subject"], "计算机")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["data"]["preparation_stage"], "强化")
        self.assertIsNone(other_user.json()["data"]["exam_subject"])

    def test_gap_status_is_validated_and_user_scoped(self) -> None:
        invalid = self.client.patch(
            "/api/v1/gaps/gap-a",
            headers=self.user_a_headers,
            json={"status": "not-a-real-status"},
        )
        other_user = self.client.patch(
            "/api/v1/gaps/gap-a",
            headers=self.user_b_headers,
            json={"status": "resolved"},
        )
        valid = self.client.patch(
            "/api/v1/gaps/gap-a",
            headers=self.user_a_headers,
            json={"status": "reviewing"},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(other_user.status_code, 404)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["data"]["status"], "reviewing")

    def test_gap_list_query_parameters_are_validated(self) -> None:
        bad_status = self.client.get(
            "/api/v1/gaps?status=unknown",
            headers=self.user_a_headers,
        )
        bad_page = self.client.get(
            "/api/v1/gaps?page=0",
            headers=self.user_a_headers,
        )
        bad_page_size = self.client.get(
            "/api/v1/gaps?page_size=101",
            headers=self.user_a_headers,
        )

        self.assertEqual(bad_status.status_code, 400)
        self.assertEqual(bad_page.status_code, 400)
        self.assertEqual(bad_page_size.status_code, 400)


if __name__ == "__main__":
    unittest.main()
