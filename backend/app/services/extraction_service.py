import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from backend.app.core.database import engine
from backend.app.core.config import get_settings
from backend.app.models.knowledge import Chapter, Chunk, KP, Material, RubricSchema
from backend.app.services.deepseek_client import DeepSeekClient


@dataclass(frozen=True)
class ExtractionUnit:
    chunk_id: str
    chapter_id: str | None
    page_no: int
    text: str


def group_chunks_for_extraction(chunks: list[Chunk], max_chars: int = 1500) -> list[ExtractionUnit]:
    """Merge adjacent same-page chunks for fewer model calls; keep original chunks for citations."""
    units: list[ExtractionUnit] = []
    current: ExtractionUnit | None = None
    for chunk in sorted(chunks, key=lambda item: (item.page_no, item.seq)):
        if current is not None and (
            current.page_no == chunk.page_no
            and current.chapter_id == chunk.chapter_id
            and len(current.text) + len(chunk.text) + 1 <= max_chars
        ):
            current = ExtractionUnit(
                chunk_id=current.chunk_id,
                chapter_id=current.chapter_id,
                page_no=current.page_no,
                text=f"{current.text}\n{chunk.text}",
            )
        else:
            if current is not None:
                units.append(current)
            current = ExtractionUnit(
                chunk_id=chunk.id,
                chapter_id=chunk.chapter_id,
                page_no=chunk.page_no,
                text=chunk.text,
            )
    if current is not None:
        units.append(current)
    return units


async def extract_kps_for_material(
    material_id: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """
    教材解析管线：知识点抽取环节。
    读取教材切片，调用大模型提取知识点，并存入数据库。
    
    返回:
        int: 成功入库的知识点数量
    """
    settings = get_settings()
    client = DeepSeekClient(settings)
    total_kps_extracted = 0

    # 1. 开启数据库同步会话
    with Session(engine) as session:
        # 获取该教材的所有切片
        statement = select(Chunk).where(Chunk.material_id == material_id)
        chunks = session.exec(statement).all()
        
        if not chunks:
            print(f"未找到 material_id={material_id} 的切片，退出提取逻辑。")
            return 0

        # 读取教材的 user_id，用于新建 KP 时继承
        material = session.get(Material, material_id)
        material_user_id = material.user_id if material else "guest"

        units = group_chunks_for_extraction(chunks)
        print(f"开始为教材 {material_id} 抽取知识点，{len(chunks)} 个原始切片合并为 {len(units)} 次模型请求。")

        existing_statement = (
            select(KP)
            .join(Chapter, KP.chapter_id == Chapter.id)
            .where(Chapter.material_id == material_id)
        )
        existing_kps = session.exec(existing_statement).all()
        kp_by_name = {
            (kp.chapter_id, kp.name.strip().lower()): kp
            for kp in existing_kps
        }

        # 2. 只并发模型请求，数据库写入仍在单一 Session 内顺序执行。
        # 上限默认 2，避免把整本书的请求同时打到模型服务。
        total_chunks = len(units)
        semaphore = asyncio.Semaphore(settings.max_extraction_concurrency)

        async def extract_one(item: ExtractionUnit):
            async with semaphore:
                try:
                    response = await client.extract_knowledge(
                        chunk_text=item.text,
                        page_no=item.page_no,
                    )
                    return item, response, None
                except Exception as exc:
                    return item, None, exc

        tasks = [asyncio.create_task(extract_one(unit)) for unit in units]
        try:
            for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
                chunk, response, error = await task
                if error is not None:
                    print(f"抽取单元 {chunk.chunk_id} (页码 {chunk.page_no}) 提取失败: {error}")
                    if progress_callback is not None:
                        progress_callback(completed, total_chunks)
                    continue
                if not response.knowledge_points:
                    print(f"警告：第 {chunk.page_no} 页未提取到任何知识点。")

                # 3. 将返回结果顺序写入数据库；相同章节与名称仍去重。
                for kp_data in response.knowledge_points:
                    if chunk.chapter_id is None:
                        continue
                    key = (chunk.chapter_id, kp_data.name.strip().lower())
                    existing_kp = kp_by_name.get(key)
                    if existing_kp is not None:
                        existing_kp.page_start = min(existing_kp.page_start, chunk.page_no)
                        existing_kp.page_end = max(existing_kp.page_end, chunk.page_no)
                        session.add(existing_kp)
                        continue

                    new_kp = KP(
                        id=f"kp-{uuid.uuid4().hex[:8]}",
                        chapter_id=chunk.chapter_id,
                        name=kp_data.name,
                        summary=kp_data.summary,
                        page_start=chunk.page_no,
                        page_end=chunk.page_no,
                        status="pending_regenerate",
                        user_id=material_user_id,
                    )
                    session.add(new_kp)
                    kp_by_name[key] = new_kp
                    total_kps_extracted += 1
                    
                if progress_callback is not None:
                    progress_callback(completed, total_chunks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
        
        # 4. 批量提交所有新产生的知识点到 feynman.db
        session.commit()
        print(f"抽取完成！成功入库 {total_kps_extracted} 个知识点。")
        
    return total_kps_extracted

# 修改为接收 session 作为参数
async def generate_rubric_for_kp(kp: KP, session: Session) -> bool:
    try:
        chapter = session.get(Chapter, kp.chapter_id)
        if chapter is None:
            raise ValueError("知识点找不到所属章节")

        stmt = (
            select(Chunk)
            .where(
                Chunk.material_id == chapter.material_id,
                Chunk.page_no >= kp.page_start,
                Chunk.page_no <= kp.page_end,
            )
            .order_by(Chunk.page_no, Chunk.seq)
        )
        chunks = session.exec(stmt).all()
        if not chunks:
            raise ValueError("知识点页码范围内没有可用的教材原文")

        full_text = "\n".join(chunk.text for chunk in chunks)
        client = DeepSeekClient(get_settings())
        rubric_json = await client.generate_rubric(full_text, kp.name)
        validated_rubric = RubricSchema.model_validate(rubric_json)

        kp.rubric = json.dumps(validated_rubric.model_dump(), ensure_ascii=False)
        kp.status = "done"
        kp.updated_at = datetime.now(timezone.utc)
        session.add(kp)
        session.commit()
        return True
    except Exception as e:
        print(f"Rubric 生成失败: {e}")
        kp.status = "failed"
        kp.updated_at = datetime.now(timezone.utc)
        session.add(kp)
        session.commit()
        return False
