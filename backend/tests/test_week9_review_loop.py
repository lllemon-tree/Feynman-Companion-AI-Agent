"""Week 9 review contract: idempotency, atomicity and user isolation."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, func, select

from backend.app.core.database import get_session
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.auth import User
from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.feynman import CardPreview, DimensionReport, FinalReport, FeynmanChatData, NextAction
from backend.app.models.knowledge import LearnSession
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.models.review_attempt import ReviewAttempt
from backend.app.services.diagnostic_report_service import DiagnosticReportFinalizer
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.kp_provider import KnowledgePoint
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.prompt_builder import build_system_prompt
from backend.app.services.rag_retriever import NullRAGRetriever
from backend.app.services.review_context_service import DefaultReviewContextProvider, safe_load_review_context
from backend.app.services.session_store import SQLSessionStore, SessionState


NAMES = ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]


def _response(scores):
    dimensions = [
        DimensionReport(name=name, score=score, analysis=f"{name}分析", suggestion=f"{name}建议")
        for name, score in zip(NAMES, scores)
    ]
    return FeynmanChatData(
        next_action=NextAction.GENERATE_REPORT,
        reply_text="本轮结束",
        card_preview=CardPreview(total_score=sum(scores), summary="本次结果"),
        final_report=FinalReport(dimensions=dimensions, overall_comment="本次诊断摘要"),
    )


class Week9ReviewLoopTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                User(id="review-user", username="review_user", password_hash="!"),
                User(id="other-user", username="review_other", password_hash="!"),
                DiagnosticReport(
                    id="baseline-1", user_id="review-user", session_id="previous-session",
                    kp_id="kp-review", kp_name="复习知识点",
                    dimensions=json.dumps([
                        {"name": name, "score": score, "analysis": "旧分析", "suggestion": "旧建议"}
                        for name, score in zip(NAMES, [4, 5, 8, 9])
                    ], ensure_ascii=False),
                    total_score=26, overall_comment="上次论证不够充分",
                ),
                KnowledgeGap(
                    id="gap-depth", user_id="review-user", kp_id="kp-review",
                    kp_name="复习知识点", dimension="理解深度", score=4,
                    severity=4, status="open", gap_description="上次没讲清原理",
                ),
                KnowledgeGap(
                    id="gap-expression", user_id="review-user", kp_id="kp-review",
                    kp_name="复习知识点", dimension="表达完整性", score=5,
                    severity=4, status="open", gap_description="上次缺少条件",
                ),
            ])
            db.commit()

        def override_session():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.headers = {"Authorization": f"Bearer {create_access_token('review-user', 'review_user')}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token('other-user', 'review_other')}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def _start(self):
        return self.client.post(
            "/api/v1/reviews/start", headers=self.headers,
            json={"kp_id": "kp-review", "source": "gap"},
        )

    def _state(self, start_data):
        return SessionState(
            session_id=start_data["session_id"], user_id="review-user",
            kp_id="kp-review", kp_name="复习知识点", ended=True,
        )

    def test_start_resume_409_and_isolation(self):
        self.assertEqual(self.client.post("/api/v1/reviews/start", json={"kp_id": "kp-review"}).status_code, 401)
        self.assertEqual(self.client.post(
            "/api/v1/reviews/start", headers=self.other_headers,
            json={"kp_id": "kp-review", "source": "gap"},
        ).status_code, 409)
        first = self._start()
        self.assertEqual(first.status_code, 200)
        data = first.json()["data"]
        self.assertFalse(data["resumed"])
        self.assertEqual(data["baseline_report_id"], "baseline-1")
        self.assertEqual(len(data["target_gaps"]), 2)
        second = self._start().json()["data"]
        self.assertTrue(second["resumed"])
        self.assertEqual(data["review_id"], second["review_id"])
        self.assertEqual(data["session_id"], second["session_id"])
        with Session(self.engine) as db:
            self.assertEqual(db.exec(select(func.count()).select_from(ReviewAttempt)).one(), 1)
            for gap_id in ("gap-depth", "gap-expression"):
                gap = db.get(KnowledgeGap, gap_id)
                self.assertEqual(gap.status, "reviewing")
                self.assertEqual(gap.review_count, 0)
                self.assertIsNone(gap.last_reviewed_at)

        self.assertEqual(self.client.get(
            f"/api/v1/reviews/{data['review_id']}", headers=self.other_headers,
        ).status_code, 404)
        active = self.client.get(
            f"/api/v1/reviews/{data['review_id']}", headers=self.headers,
        ).json()["data"]
        self.assertEqual(active["action"], "continue")
        self.assertEqual(active["dimension_changes"], [])

    def test_start_creates_restorable_learning_session(self):
        data = self._start().json()["data"]

        with Session(self.engine) as db:
            learning_session = db.get(LearnSession, data["session_id"])

        self.assertIsNotNone(learning_session)
        self.assertEqual(learning_session.user_id, "review-user")
        self.assertEqual(learning_session.kp_id, "kp-review")
        self.assertEqual(learning_session.kp_name, "复习知识点")

    def test_completion_is_atomic_idempotent_and_compares_baseline(self):
        data = self._start().json()["data"]
        state = self._state(data)
        finalizer = DiagnosticReportFinalizer(self.engine)
        first = finalizer.finalize(state, _response([8, 6, 5, 9]))
        second = finalizer.finalize(state, _response([8, 6, 5, 9]))
        self.assertEqual(first.id, second.id)

        result = self.client.get(
            f"/api/v1/reviews/{data['review_id']}", headers=self.headers,
        ).json()["data"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result_report_id"], first.id)
        changes = {item["dimension"]: item for item in result["dimension_changes"]}
        self.assertEqual(changes["理解深度"]["delta"], 4)
        self.assertEqual(changes["理解深度"]["result"], "mastered")
        self.assertEqual(changes["表达完整性"]["result"], "continue")
        self.assertEqual(changes["逻辑连贯性"]["result"], "unchanged")

        with Session(self.engine) as db:
            self.assertEqual(db.exec(select(func.count()).select_from(DiagnosticReport)).one(), 2)
            attempt = db.get(ReviewAttempt, data["review_id"])
            self.assertEqual(attempt.status, "completed")
            self.assertEqual(db.get(DiagnosticReport, "baseline-1").total_score, 26)
            mastered = db.get(KnowledgeGap, "gap-depth")
            continued = db.get(KnowledgeGap, "gap-expression")
            self.assertEqual(mastered.review_count, 1)
            self.assertEqual(mastered.status, "resolved")
            self.assertEqual(mastered.resolution_source, "assessment")
            self.assertIsNone(mastered.next_review_at)
            self.assertEqual(continued.review_count, 1)
            self.assertEqual(continued.status, "reviewing")
            self.assertEqual(
                datetime.fromisoformat(continued.next_review_at) - datetime.fromisoformat(continued.last_reviewed_at),
                timedelta(days=1),
            )
            new_gap = db.exec(select(KnowledgeGap).where(KnowledgeGap.dimension == "逻辑连贯性")).one()
            self.assertEqual(new_gap.status, "open")
            self.assertEqual(new_gap.review_count, 0)
            continued.review_count = 9
            continued.status = "resolved"
            db.add(continued)
            db.commit()
        historical = self.client.get(
            f"/api/v1/reviews/{data['review_id']}", headers=self.headers,
        ).json()["data"]
        old_expression = next(
            item for item in historical["dimension_changes"] if item["dimension"] == "表达完整性"
        )
        self.assertEqual(old_expression["review_count"], 1)
        self.assertEqual(old_expression["gap_status"], "reviewing")
        stats = self.client.get("/api/v1/reviews/stats", headers=self.headers).json()["data"]
        self.assertEqual(stats["items"][0]["completed_reviews"], 1)
        self.assertEqual(stats["items"][0]["assessment_resolved"], 1)
        self.assertIsNotNone(stats["items"][0]["avg_dimension_delta"])
        self.assertEqual(self.client.get(
            "/api/v1/reviews/stats", headers=self.other_headers,
        ).json()["data"]["total"], 0)

    def test_provider_prompt_patch_and_rollback(self):
        data = self._start().json()["data"]
        provider = DefaultReviewContextProvider(self.engine)
        context = safe_load_review_context(provider, data["session_id"], "review-user")
        self.assertIsNotNone(context)
        self.assertEqual(context.target_gap.previous_scores["理解深度"], 4)
        self.assertIsNone(safe_load_review_context(provider, data["session_id"], "other-user"))
        prompt = build_system_prompt("复习知识点", {}, review_context=context)
        self.assertIn("理解深度 4 分", prompt)
        self.assertIn("上次论证不够充分", prompt)
        self.assertNotIn("上次四维得分", build_system_prompt("复习知识点", {}))

        self.assertEqual(self.client.patch(
            "/api/v1/gaps/gap-depth", headers=self.headers, json={"status": "reviewing"},
        ).status_code, 400)
        self.assertEqual(self.client.patch(
            "/api/v1/gaps/gap-depth", headers=self.headers, json={"status": "resolved"},
        ).status_code, 409)

        with patch("backend.app.services.review_service.severity_for_score", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                DiagnosticReportFinalizer(self.engine).finalize(self._state(data), _response([8, 6, 8, 9]))
        with Session(self.engine) as db:
            self.assertEqual(db.exec(select(func.count()).select_from(DiagnosticReport)).one(), 1)
            self.assertEqual(db.get(ReviewAttempt, data["review_id"]).status, "active")
            self.assertEqual(db.get(KnowledgeGap, "gap-depth").review_count, 0)

        retried = DiagnosticReportFinalizer(self.engine).finalize(self._state(data), _response([8, 6, 8, 9]))
        self.assertIsNotNone(retried)

    def test_due_item_switches_from_start_to_continue(self):
        with Session(self.engine) as db:
            gap = db.get(KnowledgeGap, "gap-depth")
            gap.next_review_at = (datetime.now() - timedelta(days=1)).isoformat()
            db.add(gap)
            db.commit()
        before = self.client.get("/api/v1/gaps/review-due", headers=self.headers).json()["data"]["items"]
        self.assertEqual(before[0]["action"], "start")
        self.assertIsNone(before[0]["active_review_id"])
        data = self._start().json()["data"]
        after = self.client.get("/api/v1/gaps/review-due", headers=self.headers).json()["data"]["items"]
        self.assertEqual(after[0]["action"], "continue")
        self.assertEqual(after[0]["active_review_id"], data["review_id"])

    def test_manual_resolve_and_reopen_on_later_low_report(self):
        manual = self.client.patch(
            "/api/v1/gaps/gap-depth", headers=self.headers, json={"status": "resolved"},
        )
        self.assertEqual(manual.status_code, 200)
        self.assertEqual(manual.json()["data"]["resolution_source"], "manual")
        state = SessionState(
            session_id="later-normal-session", user_id="review-user",
            kp_id="kp-review", kp_name="复习知识点", ended=True,
        )
        DiagnosticReportFinalizer(self.engine).finalize(state, _response([5, 8, 8, 9]))
        with Session(self.engine) as db:
            gap = db.get(KnowledgeGap, "gap-depth")
            self.assertEqual(gap.status, "open")
            self.assertIsNone(gap.resolution_source)
            self.assertEqual(db.exec(select(func.count()).select_from(KnowledgeGap).where(
                KnowledgeGap.user_id == "review-user", KnowledgeGap.dimension == "理解深度",
            )).one(), 1)

    def test_real_http_greeting_chat_report_and_review_result(self):
        class ReviewKpProvider:
            def get(self, kp_id):
                if kp_id != "kp-review":
                    return None
                return KnowledgePoint(
                    kp_id=kp_id, name="复习知识点", summary="复习测试",
                    rubric={}, material_id="mat-test", chapter_id="ch-test",
                )

        service = FeynmanService(
            store=SQLSessionStore(self.engine),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
            knowledge_point_provider=ReviewKpProvider(),
            rag_retriever=NullRAGRetriever(),
            report_finalizer=DiagnosticReportFinalizer(self.engine),
            review_context_provider=DefaultReviewContextProvider(self.engine),
        )
        service_patcher = patch("backend.app.api.routes.get_feynman_service", return_value=service)
        service_patcher.start()
        self.addCleanup(service_patcher.stop)
        data = self._start().json()["data"]
        greeting = self.client.get(
            "/api/v1/feynman/greeting",
            params={"kp_id": "kp-review", "session_id": data["session_id"]},
            headers=self.headers,
        )
        self.assertEqual(greeting.status_code, 200)
        self.assertTrue(greeting.json()["data"]["is_review"])
        self.assertIn("理解深度", greeting.json()["data"]["review_focus"])

        for index in range(3):
            response = self.client.post(
                "/api/v1/feynman/chat", headers=self.headers,
                json={
                    "session_id": data["session_id"],
                    "kp_id": "kp-review",
                    "user_input": f"这是第 {index + 1} 次解释，我认为有前提和过程。",
                },
            )
            self.assertEqual(response.status_code, 200)
            if index == 0:
                self.assertIn("理解深度", response.json()["data"]["reply_text"])
        final_request = {
            "session_id": data["session_id"],
            "kp_id": "kp-review",
            "user_input": "这是第 4 次解释，我认为有前提和过程。",
        }
        with patch("backend.app.services.review_service.severity_for_score", side_effect=RuntimeError("write failed")):
            failed = self.client.post(
                "/api/v1/feynman/chat", headers=self.headers, json=final_request,
            )
        self.assertEqual(failed.status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(db.get(ReviewAttempt, data["review_id"]).status, "active")
            self.assertEqual(db.exec(select(func.count()).select_from(DiagnosticReport)).one(), 1)
        response = self.client.post(
            "/api/v1/feynman/chat", headers=self.headers, json=final_request,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["next_action"], "generate_report")
        result = self.client.get(
            f"/api/v1/reviews/{data['review_id']}", headers=self.headers,
        ).json()["data"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["dimension_changes"]), 4)

        repeated = self.client.post(
            "/api/v1/feynman/chat", headers=self.headers,
            json={"session_id": data["session_id"], "kp_id": "kp-review", "user_input": "重复提交"},
        )
        self.assertEqual(repeated.status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.get(KnowledgeGap, "gap-depth").review_count, 1)
            self.assertEqual(db.exec(select(func.count()).select_from(DiagnosticReport)).one(), 2)


if __name__ == "__main__":
    unittest.main()


def test_week9_inline_migration_preserves_legacy_rows():
    from backend.app.core import database

    legacy_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE diagnostic_report (id VARCHAR PRIMARY KEY, user_id VARCHAR, "
            "session_id VARCHAR, kp_id VARCHAR, kp_name VARCHAR, dimensions TEXT, "
            "total_score INTEGER, gaps_identified INTEGER, created_at DATETIME)"
        ))
        connection.execute(text(
            "CREATE TABLE knowledge_gap (id VARCHAR PRIMARY KEY, user_id VARCHAR, "
            "kp_id VARCHAR, kp_name VARCHAR, dimension VARCHAR, score INTEGER, "
            "status VARCHAR, review_count INTEGER, created_at VARCHAR, updated_at VARCHAR)"
        ))
        connection.execute(text(
            "INSERT INTO diagnostic_report (id, user_id, session_id, kp_id, kp_name, dimensions, "
            "total_score, gaps_identified, created_at) VALUES "
            "('legacy-report', 'legacy-user', 'legacy-session', 'legacy-kp', '旧知识点', '[]', 0, 0, '2026-08-01')"
        ))
        connection.execute(text(
            "INSERT INTO knowledge_gap (id, user_id, kp_id, kp_name, dimension, score, "
            "status, review_count, created_at, updated_at) VALUES "
            "('legacy-gap', 'legacy-user', 'legacy-kp', '旧知识点', '理解深度', 4, 'open', 0, '2026-08-01', '2026-08-01')"
        ))
    with patch.object(database, "engine", legacy_engine):
        database.create_db_and_tables()
        database.create_db_and_tables()
    report_columns = {item["name"] for item in inspect(legacy_engine).get_columns("diagnostic_report")}
    gap_columns = {item["name"] for item in inspect(legacy_engine).get_columns("knowledge_gap")}
    assert {"review_plan", "review_attempt_id"} <= report_columns
    assert {"resolved_at", "resolution_source"} <= gap_columns
    assert inspect(legacy_engine).has_table("review_attempt")
    with legacy_engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM diagnostic_report")).scalar_one() == "legacy-report"
        assert connection.execute(text("SELECT id FROM knowledge_gap")).scalar_one() == "legacy-gap"
