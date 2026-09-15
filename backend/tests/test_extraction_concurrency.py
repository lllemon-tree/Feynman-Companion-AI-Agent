import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.models.auth import User  # noqa: F401 - 注册 material.user_id 引用的表
from backend.app.models.knowledge import Chapter, Chunk, KP, Material
from backend.app.services import extraction_service


class ExtractionConcurrencyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add(Material(id="mat-1", subject="计算机", filename="book.pdf", raw_path="book.pdf"))
            session.add(Chapter(id="ch-1", material_id="mat-1", title="第一章"))
            for index in range(4):
                session.add(
                    Chunk(
                        id=f"chunk-{index}",
                        material_id="mat-1",
                        chapter_id="ch-1",
                        page_no=index + 1,
                        seq=0,
                        text=f"内容 {index}",
                    )
                )
            session.commit()

    async def test_requests_are_bounded_and_progress_counts_completed_chunks(self) -> None:
        active = 0
        peak = 0
        progress: list[tuple[int, int]] = []

        class FakeClient:
            async def extract_knowledge(self, chunk_text, page_no):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                try:
                    await asyncio.sleep(0.01)
                    if page_no == 3:
                        raise RuntimeError("模拟单页失败")
                    return SimpleNamespace(
                        knowledge_points=[
                            SimpleNamespace(name="共同知识点", summary=chunk_text, page_no=page_no)
                        ]
                    )
                finally:
                    active -= 1

        with (
            patch.object(extraction_service, "engine", self.engine),
            patch.object(extraction_service, "DeepSeekClient", lambda settings: FakeClient()),
            patch.object(
                extraction_service,
                "get_settings",
                lambda: SimpleNamespace(max_extraction_concurrency=2),
            ),
        ):
            count = await extraction_service.extract_kps_for_material(
                "mat-1", progress_callback=lambda completed, total: progress.append((completed, total))
            )

        self.assertEqual(peak, 2)
        self.assertEqual(progress, [(1, 4), (2, 4), (3, 4), (4, 4)])
        self.assertEqual(count, 1)
        with Session(self.engine) as session:
            kps = session.exec(select(KP)).all()
            self.assertEqual(len(kps), 1)
            self.assertEqual((kps[0].page_start, kps[0].page_end), (1, 4))

    async def test_same_page_chunks_share_one_model_request(self) -> None:
        with Session(self.engine) as session:
            session.add(Chunk(
                id="extra-1", material_id="mat-1", chapter_id="ch-1",
                page_no=1, seq=1, text="同页的第二段",
            ))
            session.add(Chunk(
                id="extra-2", material_id="mat-1", chapter_id="ch-1",
                page_no=1, seq=2, text="同页的第三段",
            ))
            session.commit()

        calls: list[tuple[int, str]] = []

        class FakeClient:
            async def extract_knowledge(self, chunk_text, page_no):
                calls.append((page_no, chunk_text))
                return SimpleNamespace(knowledge_points=[
                    SimpleNamespace(name=f"第{page_no}页知识点", summary="摘要", page_no=page_no)
                ])

        with (
            patch.object(extraction_service, "engine", self.engine),
            patch.object(extraction_service, "DeepSeekClient", lambda settings: FakeClient()),
            patch.object(extraction_service, "get_settings", lambda: SimpleNamespace(max_extraction_concurrency=2)),
        ):
            count = await extraction_service.extract_kps_for_material("mat-1")

        self.assertEqual(len(calls), 4)  # 6 slices, but only 4 same-page groups.
        self.assertEqual(count, 4)
        page_one = next(text for page, text in calls if page == 1)
        self.assertIn("同页的第二段", page_one)
        self.assertIn("同页的第三段", page_one)


if __name__ == "__main__":
    unittest.main()
