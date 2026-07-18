from datetime import datetime
import os
import fitz  # PyMuPDF
import uuid
from sqlmodel import Session
from backend.app.core.database import engine
from backend.app.models.knowledge import Material, Chunk, Chapter 

def simple_chunking(text: str, chunk_size=600):
    """
    分片逻辑：按换行符切分段落，确保分块大小适中
    """
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < chunk_size:
            current_chunk += p + "\n"
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = p + "\n"
    if current_chunk: chunks.append(current_chunk)
    return chunks

# ==========================================
# 核心业务：保存并解析 PDF
# ==========================================
def save_and_process_pdf(file_content: bytes, subject: str) -> str:
    """
    接收 PDF 字节流，保存到本地，解析目录构建章节，然后切片并存入数据库。
    """
    # 1. 生成唯一 ID 与保存路径
    material_id = f"mat-{uuid.uuid4().hex[:8]}"
    save_dir = "./uploads"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{material_id}.pdf")
    
    with open(file_path, "wb") as f:
        f.write(file_content)

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"PDF 文件损坏或无法打开: {str(e)}")

    if len(doc) > 0:
        first_page_text = doc[0].get_text()
        if len(first_page_text.strip()) < 10:
            raise ValueError("检测到扫描版 PDF，无法提取文本，请上传电子原版。")

    # ==========================================
    # [新增核心逻辑] 2. 解析目录并构建 Chapter
    # ==========================================
    toc = doc.get_toc()
    chapter_list = []
    
    # 获取最高层级的目录项 (通常 level 1 是一级标题)
    # 如果没取到 level 1，就兜底取全部目录项
    main_toc = [item for item in toc if item[0] == 1] or toc
    
    if main_toc:
        for i, item in enumerate(main_toc):
            level, title, page_start = item
            
            # 计算当前章节的结束页：等于下一章的起始页减 1
            # 如果是最后一章，结束页就是 PDF 的总页数
            if i + 1 < len(main_toc):
                page_end = max(page_start, main_toc[i + 1][2] - 1)
            else:
                page_end = doc.page_count
                
            chapter_list.append(
                Chapter(
                    id=f"ch-{uuid.uuid4().hex[:8]}",
                    material_id=material_id,
                    chapter_no=f"第{i + 1}章",
                    title=title.strip(),
                    page_start=page_start,
                    page_end=page_end
                )
            )
    else:
        # 如果 PDF 完全没有目录，创建一个默认章节兜底
        chapter_list.append(
            Chapter(
                id=f"ch-{uuid.uuid4().hex[:8]}",
                material_id=material_id,
                title="全书内容（无目录）",
                page_start=1,
                page_end=doc.page_count
            )
        )

    # 3. 解析、切片并入库
    with Session(engine) as session:
        # 先创建 Material 记录
        new_material = Material(
            id=material_id,
            subject=subject,    
            filename=f"{material_id}.pdf",
            raw_path=file_path,
            uploaded_at=datetime.now(),
            status="parsing"        # 初始状态
        )
        session.add(new_material)

        # 先把章节数据写进数据库
        for chapter in chapter_list:
            session.add(chapter)
            
        # 遍历每一页
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if not text.strip():
                continue
            
            current_page_no = page_num + 1 # 物理页码 (1-based)
            
            # 匹配当前页码属于哪个章节 (取第一个符合条件的)
            current_chapter_id = None
            for chapter in chapter_list:
                if chapter.page_start <= current_page_no <= chapter.page_end:
                    current_chapter_id = chapter.id
                    break
            
            # 兜底：如果有些奇怪的页码没有匹配到，就分给最后一个章节
            if not current_chapter_id and chapter_list:
                current_chapter_id = chapter_list[-1].id

            page_chunks = simple_chunking(text, chunk_size=600)
            
            for seq, content in enumerate(page_chunks):
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    material_id=material_id,
                    chapter_id=current_chapter_id, # [修改点2] 将切片与对应章节绑定
                    page_no=current_page_no,
                    seq=seq + 1,
                    text=content
                )
                session.add(chunk)
                
        # 统一提交，写入 Chapter 和 Chunk 表
        session.commit()

    return material_id