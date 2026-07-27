import json
import unittest
from unittest.mock import mock_open, patch

import fitz
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.models.knowledge import Chapter, Chunk, KP, KPUpdateRequest, Material
from backend.app.main import app
from backend.app.services.kp_service import get_kp_detail_from_db, update_kp_in_db
from backend.app.services.material_service import get_material_tree_from_db
from backend.app.services import pdf_service


class MaterialServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            session.add(
                Material(
                    id="mat-real",
                    subject="计算机",
                    filename="数据结构.pdf",
                    raw_path="uploads/mat-real.pdf",
                    status="done",
                    progress_step="解析完成",
                    progress=1.0,
                )
            )
            session.add(
                Chapter(
                    id="ch-real",
                    material_id="mat-real",
                    chapter_no="第6章",
                    title="图",
                    page_start=10,
                    page_end=20,
                )
            )
            session.add(
                Chunk(
                    id="chunk-real",
                    material_id="mat-real",
                    chapter_id="ch-real",
                    page_no=12,
                    seq=1,
                    text="Dijkstra 算法要求边权非负。",
                )
            )
            session.add(
                KP(
                    id="kp-real",
                    chapter_id="ch-real",
                    name="Dijkstra 算法",
                    summary="单源最短路径算法",
                    rubric=json.dumps(
                        {
                            "concept_prerequisite": "带权图和路径长度",
                            "core_mechanism": "选择当前距离最小的节点并松弛邻边",
                            "principle_proof": "非负权保证贪心选择成立",
                            "common_misunderstandings": ["错误处理负权边"],
                        },
                        ensure_ascii=False,
                    ),
                    page_start=12,
                    page_end=12,
                    status="done",
                )
            )
            session.commit()

    def test_tree_contains_real_status_and_page_range(self) -> None:
        with Session(self.engine) as session:
            tree = get_material_tree_from_db(session, "计算机")

        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0].status, "done")
        kp = tree[0].chapters[0].knowledge_points[0]
        self.assertEqual(kp.page_start, 12)
        self.assertEqual(kp.page_end, 12)
        self.assertEqual(kp.status, "done")

    def test_detail_contains_polling_fields_and_grounding_chunk(self) -> None:
        with Session(self.engine) as session:
            detail = get_kp_detail_from_db(session, "kp-real")

        self.assertEqual(detail.status, "done")
        self.assertEqual(detail.page_start, 12)
        self.assertEqual(detail.source_chunks[0].chunk_id, "chunk-real")
        self.assertEqual(detail.rubric.core_mechanism.name, "核心机制")
        self.assertIn("距离最小", detail.rubric.core_mechanism.content)

    def test_update_rejects_inverted_page_range(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(HTTPException) as context:
                update_kp_in_db(session, "kp-real", KPUpdateRequest(page_start=13))

        self.assertEqual(context.exception.status_code, 400)

    def test_pdf_with_toc_persists_original_filename_and_chunks(self) -> None:
        pdf_bytes = _build_text_pdf(with_toc=True)

        with (
            patch.object(pdf_service, "engine", self.engine),
            patch.object(pdf_service.os, "makedirs"),
            patch("builtins.open", mock_open()),
        ):
            material_id = pdf_service.save_and_process_pdf(
                pdf_bytes,
                subject="计算机",
                filename="算法教材.pdf",
            )

        with Session(self.engine) as session:
            material = session.get(Material, material_id)
            chapters = session.exec(
                select(Chapter).where(Chapter.material_id == material_id)
            ).all()
            chunks = session.exec(
                select(Chunk).where(Chunk.material_id == material_id)
            ).all()

        self.assertEqual(material.filename, "算法教材.pdf")
        self.assertEqual(len(chapters), 1)
        self.assertGreaterEqual(len(chunks), 1)

    def test_pdf_without_toc_uses_full_document_chapter(self) -> None:
        pdf_bytes = _build_text_pdf(with_toc=False)

        with (
            patch.object(pdf_service, "engine", self.engine),
            patch.object(pdf_service.os, "makedirs"),
            patch("builtins.open", mock_open()),
        ):
            material_id = pdf_service.save_and_process_pdf(
                pdf_bytes,
                subject="计算机",
                filename="短讲义.pdf",
            )

        with Session(self.engine) as session:
            chapters = session.exec(
                select(Chapter).where(Chapter.material_id == material_id)
            ).all()
            chunks = session.exec(
                select(Chunk).where(Chunk.material_id == material_id)
            ).all()

        self.assertEqual([chapter.title for chapter in chapters], ["全文（无目录）"])
        self.assertGreaterEqual(len(chunks), 1)

    def test_pdf_with_wrapper_title_uses_level_two_chapters(self) -> None:
        pdf_bytes = _build_text_pdf(
            with_toc=True,
            toc=[
                [1, "毛概大题整理", 1],
                [2, "导论", 1],
                [2, "第一章", 1],
            ],
        )

        with (
            patch.object(pdf_service, "engine", self.engine),
            patch.object(pdf_service.os, "makedirs"),
            patch("builtins.open", mock_open()),
        ):
            material_id = pdf_service.save_and_process_pdf(
                pdf_bytes,
                subject="政治",
                filename="毛概大题整理.pdf",
            )

        with Session(self.engine) as session:
            chapters = session.exec(
                select(Chapter).where(Chapter.material_id == material_id)
            ).all()

        self.assertEqual([chapter.title for chapter in chapters], ["导论", "第一章"])

    def test_chunking_enforces_maximum_size(self) -> None:
        chunks = pdf_service.simple_chunking("A" * 1200, chunk_size=500)

        self.assertEqual([len(chunk) for chunk in chunks], [500, 500, 200])


def _build_text_pdf(with_toc: bool, toc: list[list] | None = None) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (50, 50),
        "Dijkstra algorithm computes shortest paths in a non-negative weighted graph.",
    )
    if with_toc:
        document.set_toc(toc or [[1, "Shortest Paths", 1]])
    content = document.tobytes()
    document.close()
    return content


class MaterialApiContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_tree_uses_real_empty_result_for_unknown_subject(self) -> None:
        response = self.client.get(
            "/api/v1/material/tree",
            params={"subject": "不存在的科目"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])

    def test_upload_rejects_non_pdf_file(self) -> None:
        response = self.client.post(
            "/api/v1/material/upload",
            data={"subject": "计算机"},
            files={"file": ("notes.txt", b"not a pdf", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "仅支持 PDF 文件")

    def test_create_rejects_inverted_page_range_before_background_work(self) -> None:
        response = self.client.post(
            "/api/v1/kp",
            json={
                "chapter_id": "ch-missing",
                "name": "测试知识点",
                "page_start": 5,
                "page_end": 3,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["msg"], "invalid request body")


if __name__ == "__main__":
    unittest.main()
