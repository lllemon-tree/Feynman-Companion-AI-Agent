# 引入 SQLModel 的数据库会话对象和查询构造器，用于执行数据库读取操作
from sqlmodel import Session, select
# 引入知识点模块中的 Chunk 数据表模型，对应 SQLite 中的 chunk 表
from backend.app.models.knowledge import Chunk, Material
# 引入我们已封装好的向量库单例对象，负责实际的 Chroma 底层交互
from backend.app.services.vector_store import vector_store
# 引入 Python 标准日志模块
import logging

# 初始化当前文件的独立日志记录器，__name__ 自动绑定当前模块路径（如 app.services.rag_service）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 指定该 logger 接收 INFO 级别

def build_material_embeddings(session: Session, material_id: str):
    """提取教材 Chunk 并调用底层向量库完成入库"""
    
    # 使用 try-except 块包裹，防止数据库断连或模型转换时抛出异常导致整个进程崩溃
    try:
        # 构造 SQL 查询语句：相当于 SELECT * FROM chunk WHERE material_id = {material_id}
        statement = select(Chunk).where(Chunk.material_id == material_id)
        # 通过传入的 session 执行查询，调用 .all() 获取所有符合条件的切片对象列表
        chunks = session.exec(statement).all()
        
        # 判空拦截：如果查询结果为空（例如刚上传还未完成文本切片）
        if not chunks:
            # 记录警告日志并附带教材 ID，便于后台排查问题
            logger.warning(f"Material {material_id} 暂无可向量化的 Chunk。")
            # 直接退出函数，避免执行后续无效的计算
            return

        # 初始化空列表，用于装载符合 vector_store 接口要求的标准化字典数据
        formatted_chunks = []
        
        # 遍历查出的所有数据库 Chunk 对象
        for chunk in chunks:
            # 脏数据清洗：检查 text 字段是否为空，或者去除首尾空格后是否为空串
            if not chunk.text or not chunk.text.strip():
                # 如果是空文本则跳过当前循环，防止空串送入 Embedding 模型引发报错
                continue
                
            # 将合法数据组装成字典结构，追加到列表中
            formatted_chunks.append({
                "id": chunk.id,           # SQLite 中的主键 ID，供底层拼接字符串作为向量唯一标识
                "text": chunk.text,       # 切片纯文本，BGE 模型将据此计算 1024 维度的特征向量
                "page_no": chunk.page_no  # 原始页码，存入 Chroma 的 metadata 中用于后续溯源展示
            })

        # 安全校验：确保清洗后确实有有效数据
        if formatted_chunks:
            # 批量将组装好的数据传给底层工具，进行向量转化与持久化写入
            vector_store.add_chunks(material_id=material_id, chunks=formatted_chunks)
            # 记录信息级日志，告知操作成功以及实际入库的数量
            logger.info(f"成功为教材 {material_id} 生成了 {len(formatted_chunks)} 条向量。")

        # --- 更新数据库状态 ---
            material = session.get(Material, material_id)
            if material:
                # 假设你要把状态改成 done，或者增加一个 embedding_done 的进度
                material.status = "done" 
                session.add(material)
                session.commit()
        
            
    # 捕获以上流程中的任意异常（包含数据库查询失败、向量库写入异常等）
    except Exception as e:
        # 记录错误日志，携带具体的异常栈信息 e
        logger.error(f"生成教材 {material_id} 向量管线执行失败: {e}")
        # 主动向上层调用方（如工作流编排函数）抛出异常，让上层决定是标记任务失败还是重试

        # --- 记录错误到数据库 ---
        material = session.get(Material, material_id)
        if material:
            material.status = "failed"
            material.error = str(e)
            session.add(material)
            session.commit()

        raise e