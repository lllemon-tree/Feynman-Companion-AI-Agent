import json
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.models.auth import User  # noqa: F401 - registers FK target
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.services.diagnostic_report_service import get_report_detail, list_reports
from backend.app.services.review_list_service import add_report_to_review_list


class ReportReviewEnrollmentTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _report(
        report_id: str,
        scores: tuple[int, int, int, int],
    ) -> DiagnosticReport:
        names = ("理解深度", "表达完整性", "逻辑连贯性", "结构化能力")
        dimensions = [
            {
                "name": name,
                "score": score,
                "analysis": f"{name}得分为{score}",
                "suggestion": f"复习{name}",
                "covered_points": [],
                "gaps": [],
                "evidence": [],
            }
            for name, score in zip(names, scores)
        ]
        return DiagnosticReport(
            id=report_id,
            user_id="user-a",
            session_id=f"session-{report_id}",
            kp_id="kp-card",
            kp_name="封装",
            material_id="mat-card",
            material_name="Java教材",
            dimensions=json.dumps(dimensions, ensure_ascii=False),
            total_score=sum(scores),
        )

    def test_enrolls_every_unmastered_dimension_as_open_gap(self):
        with Session(self.engine) as db:
            report = self._report("rpt-low", (5, 6, 8, 8))
            db.add(report)
            db.commit()

            result = add_report_to_review_list(db, "user-a", report.id, "manual")
            gaps = db.exec(select(KnowledgeGap).order_by(KnowledgeGap.dimension)).all()

        self.assertEqual(result.dimensions, ["理解深度", "表达完整性"])
        self.assertEqual([gap.dimension for gap in gaps], ["理解深度", "表达完整性"])
        self.assertTrue(all(gap.status == "open" for gap in gaps))

    def test_uses_lowest_dimension_when_all_dimensions_are_mastered(self):
        with Session(self.engine) as db:
            report = self._report("rpt-mastered", (9, 7, 8, 10))
            db.add(report)
            db.commit()

            result = add_report_to_review_list(db, "user-a", report.id, "manual")
            gaps = db.exec(select(KnowledgeGap)).all()

        self.assertEqual(result.dimensions, ["表达完整性"])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].dimension, "表达完整性")
        self.assertEqual(gaps[0].score, 7)

    def test_reopens_existing_gap_without_creating_duplicates(self):
        with Session(self.engine) as db:
            report = self._report("rpt-reopen", (9, 7, 8, 10))
            db.add(report)
            db.add(KnowledgeGap(
                id="gap-existing",
                user_id="user-a",
                kp_id="kp-card",
                kp_name="封装",
                material_id="mat-card",
                material_name="Java教材",
                dimension="表达完整性",
                score=9,
                severity=1,
                status="resolved",
                gap_description="旧分析",
                resolved_at="2026-09-01T00:00:00",
                resolution_source="assessment",
            ))
            db.commit()

            add_report_to_review_list(db, "user-a", report.id, "manual")
            add_report_to_review_list(db, "user-a", report.id, "manual")
            gaps = db.exec(select(KnowledgeGap)).all()

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].id, "gap-existing")
        self.assertEqual(gaps[0].status, "open")
        self.assertEqual(gaps[0].score, 7)
        self.assertEqual(gaps[0].gap_description, "表达完整性得分为7")
        self.assertIsNone(gaps[0].resolved_at)
        self.assertIsNone(gaps[0].resolution_source)

    def test_report_detail_uses_active_gaps_for_added_state(self):
        with Session(self.engine) as db:
            report = self._report("rpt-detail", (9, 7, 8, 10))
            db.add(report)
            db.add(KnowledgeGap(
                id="gap-detail",
                user_id="user-a",
                kp_id="kp-card",
                kp_name="封装",
                dimension="表达完整性",
                score=7,
                severity=1,
                status="open",
            ))
            db.commit()

            detail = get_report_detail(db, "user-a", report.id)

        self.assertIsNotNone(detail)
        self.assertTrue(detail.review_list_added)
        self.assertIsNone(detail.review_list_source)

    def test_report_list_can_return_latest_report_for_one_knowledge_point(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            older = self._report("rpt-older", (4, 5, 6, 7))
            older.created_at = now - timedelta(days=2)
            latest = self._report("rpt-latest", (6, 7, 8, 9))
            latest.created_at = now - timedelta(days=1)
            other = self._report("rpt-other", (8, 8, 8, 8))
            other.kp_id = "kp-other"
            other.created_at = now
            db.add_all([older, latest, other])
            db.commit()

            result = list_reports(db, "user-a", 1, 1, kp_id="kp-card")

        self.assertEqual(result.total, 2)
        self.assertEqual([item.report_id for item in result.items], ["rpt-latest"])


if __name__ == "__main__":
    unittest.main()
