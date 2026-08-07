import unittest

from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, func, select
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.core.database import get_session
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.auth import User
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.feynman import (
    CardPreview,
    DimensionReport,
    FinalReport,
    FeynmanChatData,
    NextAction,
    PriorityItem,
    ReviewPlan,
    ReviewPlanItem,
)
from backend.app.services.diagnostic_report_service import (
    DiagnosticReportFinalizer,
    get_report_detail,
    list_reports,
    severity_for_score,
)
from backend.app.services.session_store import SessionState


def _create_gap_table(engine) -> None:
    metadata = MetaData()
    Table(
        "knowledge_gap",
        metadata,
        Column("id", String, primary_key=True),
        Column("user_id", String, nullable=False),
        Column("kp_id", String, nullable=False),
        Column("kp_name", String, nullable=False),
        Column("material_id", String),
        Column("material_name", String),
        Column("dimension", String, nullable=False),
        Column("gap_description", Text),
        Column("severity", Integer, nullable=False),
        Column("score", Integer, nullable=False),
        Column("status", String, nullable=False),
        Column("source_session_id", String),
        Column("review_count", Integer, nullable=False),
        Column("last_reviewed_at", DateTime),
        Column("next_review_at", DateTime),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    metadata.create_all(engine)


def _final_response(scores=(3, 5, 6, 8)) -> FeynmanChatData:
    names = ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]
    dimensions = [
        DimensionReport(
            name=name,
            score=score,
            analysis=f"{name}分析",
            suggestion=f"{name}建议",
        )
        for name, score in zip(names, scores)
    ]
    return FeynmanChatData(
        next_action=NextAction.GENERATE_REPORT,
        reply_text="本轮讲解结束。",
        card_preview=CardPreview(
            total_score=sum(scores),
            summary="核心理解仍需补强",
        ),
        final_report=FinalReport(
            dimensions=dimensions,
            overall_comment="请继续补足关键条件与因果链。",
        ),
    )


class FailingGapWriter:
    def sync(self, engine, context, dimensions):
        raise RuntimeError("simulated gap persistence failure")


class DiagnosticReportServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        _create_gap_table(self.engine)
        self.finalizer = DiagnosticReportFinalizer(self.engine)

    def test_finalizer_persists_report_and_low_score_gaps_idempotently(self):
        state = SessionState(
            session_id="session-report-1",
            user_id="user-a",
            kp_id="kp-dijkstra",
            kp_name="Dijkstra 算法",
            material_id=None,
            ended=True,
        )

        first = self.finalizer.finalize(state, _final_response())
        second = self.finalizer.finalize(state, _final_response())

        self.assertIsNotNone(first)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.total_score, 22)
        self.assertEqual(first.gaps_identified, 3)
        with Session(self.engine) as db:
            report_count = db.exec(
                select(func.count()).select_from(DiagnosticReport)
            ).scalar_one()
            gap_table = Table(
                "knowledge_gap",
                MetaData(),
                autoload_with=self.engine,
            )
            gaps = db.execute(
                select(gap_table).order_by(gap_table.c.score)
            ).mappings().all()

        self.assertEqual(report_count, 1)
        self.assertEqual(len(gaps), 3)
        self.assertEqual([gap["severity"] for gap in gaps], [5, 4, 3])
        self.assertTrue(all(gap["status"] == "open" for gap in gaps))

    def test_guest_and_non_report_responses_are_not_persisted(self):
        guest = SessionState(
            session_id="guest-session",
            user_id="guest",
            kp_id="kp-demo",
            kp_name="Dijkstra 算法",
        )
        response = _final_response()
        self.assertIsNone(self.finalizer.finalize(guest, response))

        response.next_action = NextAction.FOLLOW_UP
        member = SessionState(
            session_id="member-session",
            user_id="user-a",
            kp_id="kp-demo",
            kp_name="Dijkstra 算法",
        )
        self.assertIsNone(self.finalizer.finalize(member, response))
        with Session(self.engine) as db:
            count = db.exec(
                select(func.count()).select_from(DiagnosticReport)
            ).scalar_one()
        self.assertEqual(count, 0)

    def test_gap_failure_does_not_prevent_report_persistence(self):
        finalizer = DiagnosticReportFinalizer(
            self.engine,
            gap_writer=FailingGapWriter(),
        )
        report = finalizer.finalize(
            SessionState(
                session_id="gap-failure-session",
                user_id="user-a",
                kp_id="kp-demo",
                kp_name="Dijkstra 算法",
            ),
            _final_response(),
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.gaps_identified, 0)
        with Session(self.engine) as db:
            persisted = db.get(DiagnosticReport, report.id)
        self.assertIsNotNone(persisted)

    def test_list_and_detail_are_paginated_and_user_scoped(self):
        for index, user_id in enumerate(["user-a", "user-a", "user-b"]):
            state = SessionState(
                session_id=f"session-{index}",
                user_id=user_id,
                kp_id=f"kp-{index}",
                kp_name=f"知识点 {index}",
            )
            self.finalizer.finalize(state, _final_response((7, 7, 7, 7)))

        with Session(self.engine) as db:
            page = list_reports(db, "user-a", page=1, page_size=1)
            self.assertEqual(page.total, 2)
            self.assertEqual(len(page.items), 1)
            self.assertEqual(len(page.items[0].dimensions), 4)

            detail = get_report_detail(
                db,
                "user-a",
                page.items[0].report_id,
            )
            self.assertIsNotNone(detail)
            self.assertEqual(len(detail.dimensions_full), 4)
            self.assertIsNone(
                get_report_detail(db, "user-b", page.items[0].report_id)
            )

    def test_severity_mapping_matches_prd(self):
        self.assertEqual(severity_for_score(0), 5)
        self.assertEqual(severity_for_score(3), 5)
        self.assertEqual(severity_for_score(4), 4)
        self.assertEqual(severity_for_score(5), 4)
        self.assertEqual(severity_for_score(6), 3)

    def test_review_plan_is_persisted_and_loaded_back(self):
        # 构造一个带复习计划的报告响应
        response = _final_response()
        response.review_plan = ReviewPlan(
            reread_guide=[
                ReviewPlanItem(
                    priority=1,
                    material_name="数据结构教材",
                    page_hint="第3章 第30页",
                    focus="贪心策略正确性证明",
                    reason="理解深度得分偏低",
                )
            ],
            related_kps=[],
            priority_order=[
                PriorityItem(
                    rank=1,
                    dimension="理解深度",
                    kp_name="Dijkstra 算法",
                    suggestion="优先补证明",
                )
            ],
        )
        state = SessionState(
            session_id="session-review-plan",
            user_id="user-a",
            kp_id="kp-dijkstra",
            kp_name="Dijkstra 算法",
            ended=True,
        )

        report = self.finalizer.finalize(state, response)
        self.assertIsNotNone(report)

        with Session(self.engine) as db:
            detail = get_report_detail(db, "user-a", report.id)

        # 落库后再读出来，review_plan 应完整还原
        self.assertIsNotNone(detail.review_plan)
        self.assertEqual(len(detail.review_plan.reread_guide), 1)
        self.assertEqual(detail.review_plan.reread_guide[0].focus, "贪心策略正确性证明")
        self.assertEqual(len(detail.review_plan.priority_order), 1)

    def test_report_without_review_plan_returns_none(self):
        state = SessionState(
            session_id="session-no-plan",
            user_id="user-a",
            kp_id="kp-dijkstra",
            kp_name="Dijkstra 算法",
            ended=True,
        )
        report = self.finalizer.finalize(state, _final_response())
        self.assertIsNotNone(report)

        with Session(self.engine) as db:
            detail = get_report_detail(db, "user-a", report.id)

        self.assertIsNone(detail.review_plan)


class DiagnosticReportApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(
                User(
                    id="user-report-api",
                    username="report_api",
                    password_hash="!",
                )
            )
            db.add(
                User(
                    id="user-report-other",
                    username="report_other",
                    password_hash="!",
                )
            )
            db.commit()

        def override_session():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.token = create_access_token("user-report-api", "report_api")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.report = DiagnosticReportFinalizer(self.engine).finalize(
            SessionState(
                session_id="api-session",
                user_id="user-report-api",
                kp_id="kp-api",
                kp_name="API 测试知识点",
            ),
            _final_response(),
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_report_endpoints_require_login(self):
        response = self.client.get("/api/v1/reports")
        self.assertEqual(response.status_code, 401)

    def test_report_list_and_detail_contract(self):
        list_response = self.client.get(
            "/api/v1/reports",
            headers=self.headers,
            params={"page": 1, "page_size": 20},
        )
        self.assertEqual(list_response.status_code, 200)
        body = list_response.json()
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(len(body["data"]["items"][0]["dimensions"]), 4)

        detail_response = self.client.get(
            f"/api/v1/reports/{self.report.id}",
            headers=self.headers,
        )
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["data"]
        self.assertEqual(detail["session_id"], "api-session")
        self.assertEqual(len(detail["dimensions_full"]), 4)

    def test_report_detail_does_not_leak_across_users(self):
        other_token = create_access_token("user-report-other", "report_other")
        response = self.client.get(
            f"/api/v1/reports/{self.report.id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
