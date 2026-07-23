# backend/app/services/kp_service.py

# json 用于将数据库里的字符串转换成 Python 的字典，或者反过来
import json
# uuid 用于生成绝对不重复的随机字符串，作为数据库的主键 ID
import uuid
from datetime import datetime, timezone
# 从 sqlmodel 导入 Session（数据库连接通道）和 select（用于写查询语句）
from sqlmodel import Session, select
# 当查不到数据时，直接用 HTTPException 砸一个报错给前端（比如 404）
from fastapi import HTTPException

# ==========================================
# 导入底层数据库模型 (对应 feynman.db 里的真实表)
# ==========================================
from backend.app.models.knowledge import KP, Chapter, Chunk

# ==========================================
# 导入前后端约定的数据格式 (Pydantic Schema)
# ==========================================
from backend.app.models.knowledge import (
    KPDetailData, KPRubric, KPSourceChunk,
    KPCreateRequest, KPCreateData,
    KPUpdateRequest, KPUpdateData,
    KPDeleteData
)
from backend.app.services.kp_provider import normalize_rubric

def get_kp_detail_from_db(session: Session, kp_id: str) -> KPDetailData:
    """
    获取知识点详情。
    这里包含了 PRD 中最核心的“动态溯源”逻辑：不存 chunk_id，每次按页码现查。
    """
    # 1. 用 session.get() 根据主键 ID 直接去 KP 表里抓取这条数据
    kp = session.get(KP, kp_id)
    # 如果没抓到，说明前端传的 ID 是错的，直接报错 404
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 2. 查这个知识点属于哪个章节。目的是为了拿到 material_id。
    chapter = session.get(Chapter, kp.chapter_id)
    # 理论上一定能查到，查不到说明数据库关系乱了，报 500 服务器内部错误
    if not chapter:
        raise HTTPException(status_code=500, detail="数据异常：知识点找不到归属章节")

    # 3. 核心：动态组装原文切片 (Grounding)
    # 写一条 SQL 查询语句：去 Chunk 表里找属于这本书，且页码在知识点起止范围内的切片
    chunk_stmt = select(Chunk).where(
        Chunk.material_id == chapter.material_id,
        Chunk.page_no >= kp.page_start,
        Chunk.page_no <= kp.page_end
    ).order_by(Chunk.page_no, Chunk.seq) # 按页码和先后顺序排好，保证拼接连贯
    
    # 执行上面写好的查询语句，把满足条件的所有切片拿出来
    chunks = session.exec(chunk_stmt).all()
    # 遍历拿出来的切片，塞进规定的 KPSourceChunk 格式里，准备发给前端
    source_chunks = [
        KPSourceChunk(chunk_id=c.id, page=c.page_no, text=c.text)
        for c in chunks
    ]

    # 4. 反序列化 Rubric
    # 数据库里存的是长得像 JSON 的普通字符串，我们需要把它变回 Python 的字典
    parsed_rubric = {}
    if kp.rubric:
        try:
            # json.loads 负责把字符串变回字典
            parsed_rubric = json.loads(kp.rubric)
        except json.JSONDecodeError:
            # 如果大模型生成的 JSON 格式残缺，这里会报错，我们拦截下来打个日志
            print(f"⚠️ 解析知识点 {kp_id} 的 Rubric 失败")

    # 5. 把所有查到的数据，组装进约定好的 KPDetailData 外壳里返回
    return KPDetailData(
        kp_id=kp.id,
        name=kp.name,
        # 如果 summary 是空的，就给个默认提示，防止前端展示出 null
        summary=kp.summary or "暂无摘要",
        page_start=kp.page_start,
        page_end=kp.page_end,
        status=kp.status,
        rubric=KPRubric(**normalize_rubric(parsed_rubric)),
        source_chunks=source_chunks
    )

def create_kp_in_db(session: Session, request: KPCreateRequest) -> KPCreateData:
    """手动在数据库插入一个新的知识点"""
    if session.get(Chapter, request.chapter_id) is None:
        raise HTTPException(status_code=404, detail="所属章节不存在")

    # 生成一个随机 ID，比如 kp-a1b2c3d4
    new_id = f"kp-{uuid.uuid4().hex[:8]}"
    
    # 实例化一个 KP 数据库对象，把前端传过来的值塞进去
    new_kp = KP(
        id=new_id, 
        chapter_id=request.chapter_id, 
        name=request.name,
        summary=request.summary, 
        page_start=request.page_start, 
        page_end=request.page_end,
        # 按照 PRD：刚建好的知识点必须等大模型处理，所以状态锁死为这个
        status="pending_regenerate" 
    )
    
    # 告诉数据库：“我要准备添加这行数据了”
    session.add(new_kp)
    # 告诉数据库：“确认添加，立刻保存到硬盘上！” (不写这句就丢了)
    session.commit()
    
    return KPCreateData(kp_id=new_id, status=new_kp.status)

def update_kp_in_db(session: Session, kp_id: str, request: KPUpdateRequest) -> KPUpdateData:
    """局部更新知识点（修改名称或页码）"""
    # 先把旧数据从数据库里抓出来
    kp = session.get(KP, kp_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 提取前端传来的数据。exclude_unset=True 表示：前端没传的字段直接忽略，保留旧值
    update_data = request.model_dump(exclude_unset=True)
    # 设定一个开关，用来记录用户到底有没有修改起止页码
    regenerate_triggered = False
    
    next_page_start = update_data.get("page_start", kp.page_start)
    next_page_end = update_data.get("page_end", kp.page_end)
    if next_page_end < next_page_start:
        raise HTTPException(status_code=400, detail="结束页码不能小于起始页码")

    # 遍历前端传来的每一个要改的字段
    for key, value in update_data.items():
        # setattr 把新值覆盖到 kp 对象对应的字段上
        setattr(kp, key, value)
        # 如果发现前端改了起止页码...
        if key in ("page_start", "page_end"):
            # 就把开关打开
            regenerate_triggered = True

    # 按照 PRD：如果页码变了，说明原文变了，必须让大模型重写 Rubric
    if regenerate_triggered:
        kp.status = "pending_regenerate"
    kp.updated_at = datetime.now(timezone.utc)
        
    session.add(kp)
    session.commit()
    
    return KPUpdateData(kp_id=kp.id, regenerate_triggered=regenerate_triggered, status=kp.status)

def delete_kp_in_db(session: Session, kp_id: str) -> KPDeleteData:
    """物理硬删除知识点"""
    kp = session.get(KP, kp_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")
        
    # 直接告诉数据库：“删掉这行数据”
    session.delete(kp)
    session.commit()
    return KPDeleteData(kp_id=kp_id, deleted=True)

def trigger_regenerate_in_db(session: Session, kp_id: str) -> KPCreateData:
    """手动触发重跑大模型"""
    kp = session.get(KP, kp_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")
        
    # 只需要把状态打回 pending_regenerate，后台管线就会自动发现它并处理
    kp.status = "pending_regenerate"
    session.add(kp)
    session.commit()
    
    return KPCreateData(kp_id=kp.id, status=kp.status)
