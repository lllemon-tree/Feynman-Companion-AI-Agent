import os
import sys
import asyncio
import fitz  # PyMuPDF
from sqlmodel import Session, select
from dotenv import load_dotenv

# 确保能正确导入 app 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import engine, create_db_and_tables
from backend.app.models.knowledge import Chapter, Chunk, KP
from backend.app.services.pdf_service import save_and_process_pdf
from backend.app.services.extraction_service import extract_kps_for_material

def create_mock_pdf() -> bytes:
    """生成一个极简的测试 PDF，提供一段真实的学术文本供大模型抽取"""
    doc = fitz.open()
    p1 = doc.new_page()
    
    # 模拟一段教材文本
    text = (
        "在计算机科学中，二分查找（Binary Search）是一种在有序数组中查找某一特定元素的搜索算法。"
        "搜索过程从数组的中间元素开始，如果中间元素正好是要查找的元素，则搜索过程结束；"
        "如果某一特定元素大于或者小于中间元素，则在数组大于或小于中间元素的那一半中查找，而且跟开始一样从中间元素开始比较。"
        "这种搜索算法每一次比较都使搜索范围缩小一半。"
    )
    p1.insert_text((50, 50), text)
    
    # 设置目录以触发分章逻辑
    doc.set_toc([[1, "第一章 算法基础", 1]])
    return doc.write()

async def main():
    # 1. 加载环境变量 (必须确保 .env.local 中有 DEEPSEEK_API_KEY)
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
    load_dotenv(dotenv_path=env_path)

    print("1. 初始化数据库...")
    create_db_and_tables()
    
    print("2. 生成测试 PDF 并执行切片解析...")
    pdf_bytes = create_mock_pdf()
    material_id = save_and_process_pdf(pdf_bytes)
    print(f"   => PDF 解析完成，Material ID: {material_id}")

    print("\n3. 启动大模型知识点抽取管线 (请耐心等待网络响应)...")
    extracted_count = await extract_kps_for_material(material_id)
    print(f"   => 抽取流程结束，共新增 {extracted_count} 个知识点。")

    print("\n4. 验证数据库 KP 表结果...")
    with Session(engine) as session:
        # 查询刚刚生成的知识点
        kps = session.exec(select(KP)).all()
        if not kps:
            print("❌ 数据库中没有找到任何知识点，抽取失败。")
        else:
            print(f"✅ 校验成功！当前数据库共有 {len(kps)} 个知识点：")
            for kp in kps:
                print(f"   - [ID]: {kp.id}")
                print(f"     [名称]: {kp.name}")
                print(f"     [摘要]: {kp.summary}")
                print(f"     [页码]: {kp.page_start}")
                print(f"     [状态]: {kp.status}")
                print(f"     [归属章节 ID]: {kp.chapter_id}")
                print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())