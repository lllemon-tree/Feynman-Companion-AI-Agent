import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlmodel import Session, select

from backend.app.core.database import engine
from backend.app.core.config import get_settings
from backend.app.models.knowledge import Chapter, Chunk, KP, RubricSchema
from backend.app.services.deepseek_client import DeepSeekClient


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

        print(f"开始为教材 {material_id} 抽取知识点，共需处理 {len(chunks)} 个切片。")

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

        # 2. 遍历切片，逐个调用大模型进行抽取
        # MVP 阶段采用最稳妥的 for 循环串行调用，避免大批量并发触发 DeepSeek 的并发限流
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            try:
                # 打印进度提示
                print(f"正在处理切片 {idx + 1}/{len(chunks)} (页码: {chunk.page_no})...")
                
                # 调用大模型，传入切片文本和物理页码
                response = await client.extract_knowledge(
                    chunk_text=chunk.text,
                    page_no=chunk.page_no
                )
                if not response.knowledge_points:
                    print(f"警告：第 {chunk.page_no} 页未提取到任何知识点。")
                
                # 3. 将 Pydantic 对象转换为 SQLModel 对象并落库
                for kp_data in response.knowledge_points:
                    if chunk.chapter_id is None:
                        continue
                    key = (chunk.chapter_id, kp_data.name.strip().lower())
                    existing_kp = kp_by_name.get(key)
                    if existing_kp is not None:
                        existing_kp.page_start = min(existing_kp.page_start, kp_data.page_no)
                        existing_kp.page_end = max(existing_kp.page_end, kp_data.page_no)
                        session.add(existing_kp)
                        continue

                    new_kp = KP(
                        id=f"kp-{uuid.uuid4().hex[:8]}",
                        chapter_id=chunk.chapter_id, # [核心变化] 直接复用切片自带的章节 ID
                        name=kp_data.name,
                        summary=kp_data.summary,
                        page_start=kp_data.page_no,
                        page_end=kp_data.page_no,
                        status="pending_regenerate"  # 初始状态，等待后续的四维 Rubric 生成
                    )
                    session.add(new_kp)
                    kp_by_name[key] = new_kp
                    total_kps_extracted += 1
                    
            except Exception as e:
                # 捕获异常，保证某个切片失败时，后续切片能继续处理
                print(f"切片 {chunk.id} (页码 {chunk.page_no}) 提取失败: {str(e)}")
                continue
            finally:
                if progress_callback is not None:
                    progress_callback(idx + 1, total_chunks)
        
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
