from sqlmodel import Session, select
from fastapi import HTTPException
from backend.app.core.database import engine
# 导入底层数据库模型
from backend.app.models.knowledge import Material, Chapter, KP
# 导入返回给前端的数据外壳
from backend.app.models.knowledge import (
    MaterialStatusData, 
    MaterialTreeData, 
    ChapterItem, 
    KnowledgePointItem
)

# ==========================================
# 1. 供后台 Workflow 调用的写操作
# ==========================================
def update_material_status(
    material_id: str, 
    status: str, 
    step: str, 
    progress: float, 
    error: str = None
):
    """
    更新教材处理状态到底层数据库。
    独立开启短连接 Session，修改完立刻 commit，防止与长耗时任务冲突。
    """
    with Session(engine) as session:
        material = session.get(Material, material_id)
        if not material:
            print(f"⚠️ 找不到 material_id={material_id}，状态更新失败。")
            return
            
        material.status = status
        material.progress_step = step 
        material.progress = progress
        if error:
            material.error = error 
            
        session.add(material)
        session.commit()

# ==========================================
# 2. 供 API 层调用的读操作：查询状态
# ==========================================
def get_material_status_from_db(session: Session, material_id: str) -> MaterialStatusData:
    """从数据库查询教材当前的解析状态"""
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="未找到该教材，请检查 ID 是否正确")
        
    return MaterialStatusData(
        material_id=material.id,
        status=material.status,
        step=material.progress_step or "处理中",
        progress=material.progress,
        error=material.error
    )

# ==========================================
# 3. 供 API 层调用的读操作：查询教材结构树
# ==========================================
def get_material_tree_from_db(session: Session, subject: str) -> list[MaterialTreeData]:
    """级联查询：按科目查出 教材 -> 章节 -> 知识点"""
    # 1. 查教材 (过滤掉解析失败的教材)
    statement = select(Material).where(Material.subject == subject, Material.status != "failed")
    materials = session.exec(statement).all()
    
    tree_list = []
    for mat in materials:
        # 2. 查该教材下的所有章节
        ch_stmt = select(Chapter).where(Chapter.material_id == mat.id)
        chapters = session.exec(ch_stmt).all()
        
        chapter_items = []
        for ch in chapters:
            # 3. 查该章节下的所有知识点
            kp_stmt = select(KP).where(KP.chapter_id == ch.id)
            kps = session.exec(kp_stmt).all()
            
            # 组装知识点列表
            kp_items = [
                KnowledgePointItem(
                    kp_id=kp.id, 
                    name=kp.name, 
                    summary=kp.summary or "暂无摘要"
                ) for kp in kps
            ]
            
            # 组装章节
            chapter_items.append(ChapterItem(
                chapter_id=ch.id,
                title=ch.title,
                knowledge_points=kp_items
            ))
            
        # 组装单本教材的树结构
        tree_list.append(MaterialTreeData(
            material_id=mat.id,
            title=mat.filename, # 使用原始文件名作为展示标题
            chapters=chapter_items
        ))
        
    return tree_list