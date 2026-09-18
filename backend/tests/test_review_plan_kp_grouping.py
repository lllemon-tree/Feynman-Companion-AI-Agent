import unittest
from datetime import datetime, timedelta

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.models.auth import User
from backend.app.models.knowledge import LearnSession
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.services.knowledge_gap_service import KnowledgeGapService
from backend.app.services.review_service import start_review


class ReviewPlanKnowledgePointGroupingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(User(id="user-a", username="review-plan-user", password_hash="!"))
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def _gap(
        self,
        gap_id: str,
        kp_id: str,
        dimension: str,
        score: int,
        status: str = "open",
    ) -> KnowledgeGap:
        return KnowledgeGap(
            id=gap_id,
            user_id="user-a",
            kp_id=kp_id,
            kp_name=f"知识点 {kp_id}",
            dimension=dimension,
            score=score,
            severity=5 if score <= 3 else 3,
            status=status,
            gap_description=f"{dimension}待加强",
            next_review_at=(datetime.now() - timedelta(hours=1)).isoformat(),
        )

    def test_stats_count_unique_knowledge_points_per_status(self) -> None:
        with Session(self.engine) as db:
            db.add_all([
                self._gap("gap-a-depth", "kp-a", "理解深度", 3),
                self._gap("gap-a-expression", "kp-a", "表达完整性", 5),
                self._gap("gap-b-depth", "kp-b", "理解深度", 4),
                self._gap("gap-a-resolved", "kp-a", "结构化能力", 8, "resolved"),
            ])
            db.commit()

            stats = KnowledgeGapService.get_gap_stats(db, "user-a")

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_status"], {"open": 2, "reviewing": 0, "resolved": 1})

    def test_due_list_has_one_card_per_knowledge_point_with_lowest_score_focus(self) -> None:
        with Session(self.engine) as db:
            db.add_all([
                self._gap("gap-a-depth", "kp-a", "理解深度", 3),
                self._gap("gap-a-expression", "kp-a", "表达完整性", 5),
                self._gap("gap-b-depth", "kp-b", "理解深度", 4),
            ])
            db.commit()

            result = KnowledgeGapService.get_review_due_gaps(db, "user-a")

        self.assertEqual(result["total"], 2)
        self.assertEqual([item["kp_id"] for item in result["items"]], ["kp-a", "kp-b"])
        self.assertEqual(result["items"][0]["dimension"], "理解深度")
        self.assertEqual(result["items"][0]["score"], 3)
        self.assertEqual(result["items"][0]["dimension_count"], 2)

    def test_start_review_creates_a_restorable_learning_session(self) -> None:
        with Session(self.engine) as db:
            db.add(self._gap("gap-a-depth", "kp-a", "理解深度", 3))
            db.commit()

            started = start_review(db, "user-a", "kp-a", "gap")
            learning_session = db.get(LearnSession, started["session_id"])

        self.assertIsNotNone(learning_session)
        self.assertEqual(learning_session.user_id, "user-a")
        self.assertEqual(learning_session.kp_id, "kp-a")
        self.assertEqual(learning_session.kp_name, "知识点 kp-a")


if __name__ == "__main__":
    unittest.main()
