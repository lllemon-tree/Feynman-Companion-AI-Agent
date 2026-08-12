import json
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.database import get_session
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.auth import User
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.services.knowledge_gap_service import KnowledgeGapService


DIMENSION_NAMES = ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]


class Week7SrsAndStatsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all(
                [
                    User(id="user-a", username="week7-a", password_hash="!"),
                    User(id="user-b", username="week7-b", password_hash="!"),
                    User(id="user-c", username="week7-c", password_hash="!"),
                ]
            )
            db.commit()

        def override_session():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.user_a_headers = self._headers("user-a", "week7-a")
        self.user_b_headers = self._headers("user-b", "week7-b")
        self.user_c_headers = self._headers("user-c", "week7-c")

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_srs_interval_schedule_matches_prd(self) -> None:
        reviewed_at = datetime(2026, 8, 7, 9, 30)
        expected_days = [1, 3, 7, 14, 30, 30]

        for review_count, days in enumerate(expected_days, start=1):
            next_review_at = KnowledgeGapService.calculate_next_review_at(
                review_count,
                reviewed_at,
            )
            self.assertEqual(next_review_at - reviewed_at, timedelta(days=days))

    def test_start_review_increments_count_and_returns_next_review_time(self) -> None:
        self._add_gap(id="gap-srs", user_id="user-a", status="open")

        first = self.client.patch(
            "/api/v1/gaps/gap-srs",
            headers=self.user_a_headers,
            json={"status": "reviewing"},
        )
        second = self.client.patch(
            "/api/v1/gaps/gap-srs",
            headers=self.user_a_headers,
            json={"status": "reviewing"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_data = first.json()["data"]
        second_data = second.json()["data"]
        self.assertEqual(first_data["review_count"], 1)
        self.assertEqual(second_data["review_count"], 2)
        self.assertEqual(
            datetime.fromisoformat(first_data["next_review_at"])
            - datetime.fromisoformat(first_data["last_reviewed_at"]),
            timedelta(days=1),
        )
        self.assertEqual(
            datetime.fromisoformat(second_data["next_review_at"])
            - datetime.fromisoformat(second_data["last_reviewed_at"]),
            timedelta(days=3),
        )

    def test_review_due_is_user_scoped_filtered_and_severity_sorted(self) -> None:
        now = datetime.now()
        due_at = (now - timedelta(hours=1)).isoformat()
        future_at = (now + timedelta(days=2)).isoformat()
        self._add_gap(
            id="gap-due-low",
            user_id="user-a",
            status="reviewing",
            severity=3,
            next_review_at=due_at,
        )
        self._add_gap(
            id="gap-due-high",
            user_id="user-a",
            status="reviewing",
            severity=5,
            next_review_at=due_at,
        )
        self._add_gap(
            id="gap-future",
            user_id="user-a",
            status="reviewing",
            next_review_at=future_at,
        )
        self._add_gap(
            id="gap-open",
            user_id="user-a",
            status="open",
            next_review_at=due_at,
        )
        self._add_gap(
            id="gap-other-user",
            user_id="user-b",
            status="reviewing",
            severity=5,
            next_review_at=due_at,
        )

        response = self.client.get(
            "/api/v1/gaps/review-due",
            headers=self.user_a_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 2)
        self.assertEqual(
            [item["gap_id"] for item in data["items"]],
            ["gap-due-high", "gap-due-low"],
        )
        self.assertTrue(all(item["status"] == "reviewing" for item in data["items"]))

    def test_user_stats_aggregates_reports_and_isolates_users(self) -> None:
        self._add_report(
            id="report-a1",
            user_id="user-a",
            session_id="session-a1",
            kp_id="kp-1",
            scores=[4, 5, 6, 7],
            total_score=20,
            created_at=datetime(2026, 8, 1, 10, tzinfo=timezone.utc),
        )
        self._add_report(
            id="report-a2",
            user_id="user-a",
            session_id="session-a2",
            kp_id="kp-2",
            scores=[6, 7, 8, 9],
            total_score=28,
            created_at=datetime(2026, 8, 2, 10, tzinfo=timezone.utc),
        )
        self._add_report(
            id="report-a3",
            user_id="user-a",
            session_id="session-a3",
            kp_id="kp-2",
            scores=[8, 9, 10, 10],
            total_score=36,
            created_at=datetime(2026, 8, 2, 16, tzinfo=timezone.utc),
        )
        self._add_report(
            id="report-b1",
            user_id="user-b",
            session_id="session-b1",
            kp_id="kp-other",
            scores=[10, 10, 10, 10],
            total_score=40,
            created_at=datetime(2026, 8, 3, 10, tzinfo=timezone.utc),
        )

        response = self.client.get(
            "/api/v1/user/stats",
            headers=self.user_a_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_kps_learned"], 2)
        self.assertEqual(data["total_sessions"], 3)
        self.assertEqual(data["avg_total_score"], 28.0)
        self.assertEqual(
            data["dimension_avg"],
            {
                "理解深度": 6.0,
                "表达完整性": 7.0,
                "逻辑连贯性": 8.0,
                "结构化能力": 8.7,
            },
        )
        self.assertEqual(data["weakest_dimension"], "理解深度")
        self.assertEqual(
            data["recent_trend"],
            [
                {"date": "2026-08-01", "total_score": 20.0},
                {"date": "2026-08-02", "total_score": 32.0},
            ],
        )

    def test_user_stats_without_reports_returns_zero_contract(self) -> None:
        response = self.client.get(
            "/api/v1/user/stats",
            headers=self.user_c_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_kps_learned"], 0)
        self.assertEqual(data["total_sessions"], 0)
        self.assertEqual(data["avg_total_score"], 0.0)
        self.assertEqual(data["weakest_dimension"], None)
        self.assertEqual(data["recent_trend"], [])
        self.assertTrue(all(score == 0.0 for score in data["dimension_avg"].values()))

    def test_week7_endpoints_require_login(self) -> None:
        self.assertEqual(
            self.client.get("/api/v1/gaps/review-due").status_code,
            401,
        )
        self.assertEqual(
            self.client.get("/api/v1/user/stats").status_code,
            401,
        )

    def _add_gap(
        self,
        *,
        id: str,
        user_id: str,
        status: str,
        severity: int = 4,
        next_review_at: str | None = None,
    ) -> None:
        with Session(self.engine) as db:
            db.add(
                KnowledgeGap(
                    id=id,
                    user_id=user_id,
                    kp_id=f"kp-{id}",
                    kp_name=f"知识点 {id}",
                    dimension="理解深度",
                    gap_description=f"{id} 的薄弱点",
                    severity=severity,
                    score=4,
                    status=status,
                    next_review_at=next_review_at,
                )
            )
            db.commit()

    def _add_report(
        self,
        *,
        id: str,
        user_id: str,
        session_id: str,
        kp_id: str,
        scores: list[int],
        total_score: int,
        created_at: datetime,
    ) -> None:
        dimensions = [
            {
                "name": name,
                "score": score,
                "analysis": f"{name}分析",
                "suggestion": f"{name}建议",
            }
            for name, score in zip(DIMENSION_NAMES, scores)
        ]
        with Session(self.engine) as db:
            db.add(
                DiagnosticReport(
                    id=id,
                    user_id=user_id,
                    session_id=session_id,
                    kp_id=kp_id,
                    kp_name=f"知识点 {kp_id}",
                    dimensions=json.dumps(dimensions, ensure_ascii=False),
                    total_score=total_score,
                    created_at=created_at,
                )
            )
            db.commit()

    @staticmethod
    def _headers(user_id: str, username: str) -> dict[str, str]:
        token = create_access_token(user_id, username)
        return {"Authorization": f"Bearer {token}"}


if __name__ == "__main__":
    unittest.main()
