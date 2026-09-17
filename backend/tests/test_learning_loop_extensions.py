import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.feynman import FeynmanChatRequest, NextAction
from backend.app.models.knowledge import Chapter, Chunk, KP, Material
from backend.app.models.learning import (
    FavoriteCardCreateRequest,
    FavoriteCardUpdateRequest,
    FavoriteCollectionCreateRequest,
    KnowledgeCard,
    KnowledgeCardFavorite,
    KnowledgeReviewItem,
)
from backend.app.services.card_favorite_service import (
    add_favorite,
    create_collection,
    delete_collection,
    list_favorites,
    remove_favorite,
    update_favorite,
)
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.knowledge_card_service import (
    enhance_knowledge_card,
    get_or_create_knowledge_card,
)
from backend.app.services.material_service import get_material_tree_from_db
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.review_list_service import (
    add_report_to_review_list,
    maybe_auto_add_report,
)
from backend.app.services.session_store import InMemorySessionStore


class LearningLoopExtensionsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(Material(
                id="mat-card", subject="计算机", name="Java教材",
                filename="java.pdf", raw_path="uploads/java.pdf", status="done",
                progress=1, user_id="user-a",
            ))
            db.add(Chapter(
                id="ch-card", material_id="mat-card", title="面向对象",
                page_start=1, page_end=10, user_id="user-a",
            ))
            db.add(Chunk(
                id="chunk-card", material_id="mat-card", chapter_id="ch-card",
                page_no=5, seq=1,
                text="封装隐藏对象内部实现，通过公开方法约束外部访问，提高安全性和可维护性。",
                user_id="user-a",
            ))
            db.add(KP(
                id="kp-card", chapter_id="ch-card", name="封装",
                summary="隐藏实现细节并通过接口约束访问",
                rubric=json.dumps({
                    "concept_prerequisite": "对象包含状态与行为",
                    "core_mechanism": "限制直接访问，通过公开方法操作内部状态",
                    "principle_proof": "统一入口可以校验数据并隔离实现变化",
                    "common_misunderstandings": ["封装不等于机械添加Getter和Setter"],
                }, ensure_ascii=False),
                page_start=5, page_end=5, status="done", user_id="user-a",
            ))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def _report(self, report_id: str, total_score: int) -> DiagnosticReport:
        return DiagnosticReport(
            id=report_id, user_id="user-a", session_id=f"session-{report_id}",
            kp_id="kp-card", kp_name="封装", material_id="mat-card",
            material_name="Java教材", dimensions="[]", total_score=total_score,
        )

    def test_card_is_cached_and_model_supplements_are_not_required(self):
        settings = SimpleNamespace(llm_provider="mock", deepseek_configured=False)
        with Session(self.engine) as db, patch(
            "backend.app.services.knowledge_card_service.get_settings",
            return_value=settings,
        ):
            first = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))
            second = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))
            count = len(db.exec(select(KnowledgeCard)).all())

        self.assertEqual(first.card_id, second.card_id)
        self.assertEqual(count, 1)
        self.assertEqual(first.learning_status, "unlearned")
        self.assertEqual(first.generation_status, "ready")
        supplements = [item for item in first.sections if item.source_type == "model_supplement"]
        self.assertTrue(supplements)
        self.assertTrue(all(not item.required_for_evaluation for item in supplements))

    def test_successful_report_changes_tree_status_to_learned(self):
        with Session(self.engine) as db:
            before = get_material_tree_from_db(db, "计算机", "user-a")
            db.add(self._report("rpt-learned", 31))
            db.commit()
            after = get_material_tree_from_db(db, "计算机", "user-a")

        self.assertEqual(before[0].chapters[0].knowledge_points[0].learning_status, "unlearned")
        self.assertEqual(after[0].chapters[0].knowledge_points[0].learning_status, "learned")

    def test_card_returns_base_before_background_enhancement(self):
        settings = SimpleNamespace(llm_provider="deepseek", deepseek_configured=True)
        generate = AsyncMock(return_value={
            "coverage_level": "partial",
            "coverage_notice": "增强完成",
            "estimated_minutes": 4,
            "sections": [],
        })
        with patch(
            "backend.app.services.knowledge_card_service.get_settings",
            return_value=settings,
        ), patch(
            "backend.app.services.knowledge_card_service.DeepSeekClient.generate_knowledge_card",
            new=generate,
        ):
            with Session(self.engine) as db:
                immediate = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))
            self.assertEqual(immediate.generation_status, "generating")
            generate.assert_not_awaited()

            asyncio.run(enhance_knowledge_card("kp-card", "user-a", self.engine))
            with Session(self.engine) as db:
                enhanced = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))

        generate.assert_awaited_once()
        self.assertEqual(enhanced.generation_status, "ready")
        self.assertEqual(enhanced.version, 2)

    def test_review_threshold_and_manual_add_are_idempotent(self):
        with Session(self.engine) as db:
            low = self._report("rpt-low", 23)
            db.add(low)
            db.commit()
            auto = maybe_auto_add_report(db, low)
            again = add_report_to_review_list(db, "user-a", low.id, "manual")
            count = len(db.exec(select(KnowledgeReviewItem)).all())

        self.assertIsNotNone(auto)
        self.assertEqual(auto.source, "automatic")
        self.assertEqual(again.review_item_id, auto.review_item_id)
        self.assertEqual(count, 1)

    def test_favorite_card_supports_folders_tags_notes_and_search(self):
        settings = SimpleNamespace(llm_provider="mock", deepseek_configured=False)
        with Session(self.engine) as db, patch(
            "backend.app.services.knowledge_card_service.get_settings",
            return_value=settings,
        ):
            card = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))
            folder = create_collection(db, "user-a", FavoriteCollectionCreateRequest(
                name="Java核心", description="面向对象重点", color="#3366cc"
            ))
            favorite = add_favorite(db, "user-a", FavoriteCardCreateRequest(
                card_id=card.card_id,
                collection_ids=[folder.collection_id],
                note="面试时要能解释封装与Getter/Setter的区别",
                tags=["Java", "面向对象", "Java"],
            ))
            duplicate = add_favorite(db, "user-a", FavoriteCardCreateRequest(
                card_id=card.card_id
            ))
            updated = update_favorite(db, "user-a", favorite.favorite_id,
                FavoriteCardUpdateRequest(is_pinned=True))
            result = list_favorites(
                db, "user-a", query="getter", collection_id=folder.collection_id,
                tag="Java", sort="recent",
            )

        self.assertEqual(duplicate.favorite_id, favorite.favorite_id)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].tags, ["Java", "面向对象"])
        self.assertEqual(result.items[0].collection_ids, [folder.collection_id])
        self.assertTrue(updated.is_pinned)

    def test_deleting_folder_keeps_card_and_unfavorite_removes_relationship(self):
        settings = SimpleNamespace(llm_provider="mock", deepseek_configured=False)
        with Session(self.engine) as db, patch(
            "backend.app.services.knowledge_card_service.get_settings",
            return_value=settings,
        ):
            card = asyncio.run(get_or_create_knowledge_card(db, "kp-card", "user-a"))
            folder = create_collection(db, "user-a", FavoriteCollectionCreateRequest(
                name="待整理"
            ))
            favorite = add_favorite(db, "user-a", FavoriteCardCreateRequest(
                card_id=card.card_id, collection_ids=[folder.collection_id]
            ))
            delete_collection(db, "user-a", folder.collection_id)
            after_folder_delete = list_favorites(db, "user-a")
            status = remove_favorite(db, "user-a", favorite.favorite_id)
            remaining = len(db.exec(select(KnowledgeCardFavorite)).all())

        self.assertEqual(after_folder_delete.total, 1)
        self.assertEqual(after_folder_delete.items[0].collection_ids, [])
        self.assertFalse(status.is_favorited)
        self.assertEqual(remaining, 0)

    def test_exactly_six_does_not_auto_add(self):
        with Session(self.engine) as db:
            report = self._report("rpt-six", 24)
            db.add(report)
            db.commit()
            result = maybe_auto_add_report(db, report)

        self.assertIsNone(result)

    def test_user_can_finish_after_one_explanation_without_fake_user_turn(self):
        store = InMemorySessionStore()
        service = FeynmanService(
            store=store,
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )
        asyncio.run(service.chat(FeynmanChatRequest(
            session_id="finish-session", kp_id="kp-demo",
            user_input="Dijkstra用于单源最短路径，要求边权非负。",
        )))
        result = asyncio.run(service.chat(FeynmanChatRequest(
            session_id="finish-session", kp_id="kp-demo",
            finish_requested=True,
        )))
        state = store.get("finish-session", "guest")

        self.assertEqual(result.next_action, NextAction.GENERATE_REPORT)
        self.assertEqual(
            [message.content for message in state.messages if message.role == "user"],
            ["Dijkstra用于单源最短路径，要求边权非负。"],
        )


if __name__ == "__main__":
    unittest.main()
