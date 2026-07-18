import asyncio
import os
import fitz  # PyMuPDF
import sys
from sqlmodel import Session, select

# 确保能找到项目根目录 (根据你的目录结构向上找)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.core.database import engine, create_db_and_tables
from backend.app.models.knowledge import KP
from backend.app.services.pdf_service import save_and_process_pdf
from backend.app.services.extraction_service import extract_kps_for_material, generate_rubric_for_kp
from backend.app.services.deepseek_client import DeepSeekClient
from backend.app.core.config import get_settings


def create_mock_pdf() -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    text = "在计算机科学中，二分查找（Binary Search）是一种在有序数组中查找某一特定元素的搜索算法。"
    p1.insert_text((50, 50), text)
    doc.set_toc([[1, "第一章 算法基础", 1]])
    return doc.write()

async def main():
    # 1. 自动清空环境：每次测试前，删除旧表并重建
    print("🧹 正在清理旧的测试数据...")
    # 使用 SQLModel/SQLAlchemy 直接删除所有表，确保每次测试都是从 0 开始
    from backend.app.core.database import SQLModel
    SQLModel.metadata.drop_all(engine) 
    print("开始冒烟测试")
    create_db_and_tables()
    
    # 1. 跑通解析与切片
    pdf_bytes = create_mock_pdf()
    material_id = save_and_process_pdf(pdf_bytes)
    print(f"✅ [步骤1] PDF 解析完成，Material ID: {material_id}")

    # 2. 跑通知识点抽取
    count = await extract_kps_for_material(material_id)
    print(f"✅ [步骤2] 知识点抽取完成，共 {count} 个。")

    # 3. 跑通 Rubric 生成
    with Session(engine) as session:
        kps = session.exec(select(KP)).all()

        for kp in kps:
            print(f"🔄 正在为知识点 '{kp.name}' 生成四维 Rubric...")
            success = await generate_rubric_for_kp(kp, session)
            if success:
                print(f"✅ [步骤3] Rubric 生成成功！")
                # 打印一下结果看是否合规
                print(f"   内容预览: {kp.rubric[:50]}...")
            else:
                print(f"❌ [步骤3] Rubric 生成失败。")

if __name__ == "__main__":
    asyncio.run(main())