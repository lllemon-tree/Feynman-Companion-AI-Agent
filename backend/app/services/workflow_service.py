import asyncio
import logging

from sqlmodel import Session, select

from backend.app.core.database import engine
from backend.app.core.config import get_settings
from backend.app.models.knowledge import Chapter, KP
from backend.app.services.extraction_service import extract_kps_for_material, generate_rubric_for_kp
from backend.app.services.material_service import update_material_status
from backend.app.services.rag_service import build_material_embeddings

logger = logging.getLogger(__name__)

RUBRIC_GENERATION_TIMEOUT_SECONDS = 60


def _get_material_kps(session: Session, material_id: str) -> list[KP]:
    statement = (
        select(KP)
        .join(Chapter, KP.chapter_id == Chapter.id)
        .where(Chapter.material_id == material_id)
    )
    return list(session.exec(statement).all())


async def run_full_extraction_workflow(material_id: str) -> None:
    try:
        update_material_status(
            material_id=material_id,
            status="extracting",
            step="正在从切片中抽取核心知识点",
            progress=0.2,
        )

        with Session(engine) as session:
            existing_kps = _get_material_kps(session, material_id)

        if not existing_kps:
            def report_extraction_progress(completed: int, total: int) -> None:
                progress = 0.2 + (0.3 * completed / total) if total else 0.5
                update_material_status(
                    material_id=material_id,
                    status="extracting",
                    step=f"正在从切片中抽取核心知识点 ({completed}/{total})",
                    progress=round(progress, 2),
                )

            extracted_count = await extract_kps_for_material(
                material_id,
                progress_callback=report_extraction_progress,
            )
            if extracted_count == 0:
                raise RuntimeError("没有从教材中抽取到有效知识点")

        update_material_status(
            material_id=material_id,
            status="generating",
            step="正在为知识点生成四维分析标准",
            progress=0.5,
        )

        with Session(engine) as session:
            kp_ids = [kp.id for kp in _get_material_kps(session, material_id) if kp.status != "done"]
        total_kps = len(kp_ids)
        failed_kp_ids: list[str] = []
        timed_out = False
        semaphore = asyncio.Semaphore(get_settings().max_rubric_concurrency)

        async def generate_one(kp_id: str) -> tuple[str, bool, bool]:
            async with semaphore:
                # 每个模型请求独占数据库会话；不要在并发任务间共享 Session。
                with Session(engine) as kp_session:
                    kp = kp_session.get(KP, kp_id)
                    if kp is None:
                        return kp_id, False, False
                    try:
                        success = await asyncio.wait_for(
                            generate_rubric_for_kp(kp, kp_session),
                            timeout=RUBRIC_GENERATION_TIMEOUT_SECONDS,
                        )
                        return kp_id, success, False
                    except TimeoutError:
                        kp.status = "failed"
                        kp_session.add(kp)
                        kp_session.commit()
                        return kp_id, False, True

        tasks = [asyncio.create_task(generate_one(kp_id)) for kp_id in kp_ids]
        try:
            for index, task in enumerate(asyncio.as_completed(tasks), start=1):
                kp_id, success, exceeded_timeout = await task
                if not success:
                    failed_kp_ids.append(kp_id)
                timed_out = timed_out or exceeded_timeout
                update_material_status(
                    material_id=material_id,
                    status="generating",
                    step=f"正在生成知识点解析 ({index}/{total_kps})",
                    progress=round(0.5 + (0.4 * index / total_kps), 2),
                )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

        if timed_out:
            raise TimeoutError("单个知识点的 Rubric 生成超过 60 秒")

        if failed_kp_ids:
            raise RuntimeError(f"{len(failed_kp_ids)} 个知识点的 rubric 生成失败")

        # ==========================================
        # 阶段 3：RAG 向量化
        # ==========================================
        update_material_status(
            material_id=material_id,
            status="generating",
            step="正在建立教材检索索引",
            progress=0.9,
        )
        try:
            logger.info(f"开始为教材 {material_id} 执行异步向量化任务...")
            with Session(engine) as embedding_session:
                build_material_embeddings(session=embedding_session, material_id=material_id)
        except Exception as e:
            logger.error(f"教材 {material_id} 向量化任务异常，但不阻塞总体进度: {e}")

        update_material_status(
            material_id=material_id,
            status="done",
            step="解析完成",
            progress=1.0,
        )
    except TimeoutError:
        update_material_status(
            material_id=material_id,
            status="failed",
            step="Rubric 生成超时",
            progress=0.0,
            error="单个知识点的 Rubric 生成超过 60 秒，请重试",
        )
    except Exception as e:
        update_material_status(
            material_id=material_id,
            status="failed",
            step="解析失败",
            progress=0.0,
            error=f"处理中断: {e}",
        )


async def regenerate_kp_workflow(kp_id: str) -> None:
    with Session(engine) as session:
        kp = session.get(KP, kp_id)
        if kp is None:
            return
        try:
            await asyncio.wait_for(
                generate_rubric_for_kp(kp, session),
                timeout=RUBRIC_GENERATION_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            kp.status = "failed"
            session.add(kp)
            session.commit()
