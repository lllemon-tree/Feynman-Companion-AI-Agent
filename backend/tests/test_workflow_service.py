import unittest
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.models.knowledge import Chapter, KP, Material
from backend.app.services import workflow_service


class WorkflowServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            for material_id in ["mat-current", "mat-other"]:
                session.add(
                    Material(
                        id=material_id,
                        subject="计算机",
                        filename=f"{material_id}.pdf",
                        raw_path=f"uploads/{material_id}.pdf",
                        status="generating",
                    )
                )
                chapter_id = material_id.replace("mat-", "ch-")
                session.add(
                    Chapter(
                        id=chapter_id,
                        material_id=material_id,
                        title="图",
                        page_start=1,
                        page_end=2,
                    )
                )
                session.add(
                    KP(
                        id=material_id.replace("mat-", "kp-"),
                        chapter_id=chapter_id,
                        name="测试知识点",
                        summary="测试",
                        page_start=1,
                        page_end=1,
                        status="pending_regenerate",
                    )
                )
            session.commit()

    async def test_workflow_only_generates_current_material_kps(self) -> None:
        processed: list[str] = []
        status_updates: list[dict] = []

        async def fake_generate(kp, session):
            processed.append(kp.id)
            kp.status = "done"
            session.add(kp)
            session.commit()
            return True

        with (
            patch.object(workflow_service, "engine", self.engine),
            patch.object(workflow_service, "generate_rubric_for_kp", fake_generate),
            patch.object(
                workflow_service,
                "update_material_status",
                lambda **kwargs: status_updates.append(kwargs),
            ),
        ):
            await workflow_service.run_full_extraction_workflow("mat-current")

        self.assertEqual(processed, ["kp-current"])
        self.assertEqual(status_updates[-1]["status"], "done")
        with Session(self.engine) as session:
            self.assertEqual(session.get(KP, "kp-other").status, "pending_regenerate")

    async def test_rubric_failure_marks_material_failed(self) -> None:
        status_updates: list[dict] = []

        async def fake_failure(kp, session):
            kp.status = "failed"
            session.add(kp)
            session.commit()
            return False

        with (
            patch.object(workflow_service, "engine", self.engine),
            patch.object(workflow_service, "generate_rubric_for_kp", fake_failure),
            patch.object(
                workflow_service,
                "update_material_status",
                lambda **kwargs: status_updates.append(kwargs),
            ),
        ):
            await workflow_service.run_full_extraction_workflow("mat-current")

        self.assertEqual(status_updates[-1]["status"], "failed")
        self.assertIn("rubric 生成失败", status_updates[-1]["error"])

    async def test_extraction_reports_progress_without_batch_timeout(self) -> None:
        status_updates: list[dict] = []

        with Session(self.engine) as session:
            session.delete(session.get(KP, "kp-current"))
            session.commit()

        async def fake_extract(material_id, progress_callback=None):
            self.assertEqual(material_id, "mat-current")
            self.assertIsNotNone(progress_callback)
            progress_callback(1, 2)
            progress_callback(2, 2)
            with Session(self.engine) as session:
                session.add(
                    KP(
                        id="kp-extracted",
                        chapter_id="ch-current",
                        name="新知识点",
                        summary="测试",
                        page_start=1,
                        page_end=1,
                        status="done",
                    )
                )
                session.commit()
            return 1

        with (
            patch.object(workflow_service, "engine", self.engine),
            patch.object(workflow_service, "extract_kps_for_material", fake_extract),
            patch.object(
                workflow_service,
                "update_material_status",
                lambda **kwargs: status_updates.append(kwargs),
            ),
        ):
            await workflow_service.run_full_extraction_workflow("mat-current")

        extraction_updates = [
            update for update in status_updates if update["status"] == "extracting"
        ]
        self.assertEqual(extraction_updates[-1]["progress"], 0.5)
        self.assertIn("(2/2)", extraction_updates[-1]["step"])
        self.assertEqual(status_updates[-1]["status"], "done")


if __name__ == "__main__":
    unittest.main()
