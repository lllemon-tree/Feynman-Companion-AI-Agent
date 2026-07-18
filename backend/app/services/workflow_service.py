# backend/app/services/workflow_service.py

# asyncio 用于写异步代码 (带 async/await 的代码)
import asyncio
# 导入数据库会话操作相关工具
from sqlmodel import Session, select
from backend.app.core.database import engine

# 导入我们要操作的数据表 KP
from backend.app.models.knowledge import KP

# 导入大模型核心能力：抽取知识点、生成评价标准 (Rubric)
from backend.app.services.extraction_service import extract_kps_for_material, generate_rubric_for_kp
# 导入状态更新函数。用来随时把当前进度写进数据库，让前端轮询时能查到
from backend.app.services.material_service import update_material_status


async def run_full_extraction_workflow(material_id: str):
    """
    全自动教材解析管线。它是被扔在后台运行的，哪怕用户关了网页，它也会默默跑完。
    """
    print(f"🚀 [后台任务启动] 开始处理教材: {material_id}")
    
    # 必须用 try-except 包裹全部代码！
    # 因为后台任务如果没有被包裹，一旦大模型报错崩溃，状态就不会更新，前端就会一直傻等
    try:
        # ==========================================
        # 阶段 1：大模型抽取知识点
        # ==========================================
        # 马上去数据库里修改状态，告诉前端：“我要开始抽知识点了”，进度条推到 20%
        update_material_status(material_id=material_id, status="extracting", step="正在从切片中抽取核心知识点", progress=0.2)
        
        # 真正调用函数干活，这步可能需要几十秒
        extracted_count = await extract_kps_for_material(material_id)
        print(f"✅ [抽取完成] 共提取到 {extracted_count} 个知识点")


        # ==========================================
        # 阶段 2：大模型为每个知识点生成 Rubric
        # ==========================================
        # 告诉前端：“开始最耗时的步骤了”，进度条推到 50%
        update_material_status(material_id=material_id, status="generating", step="正在为知识点生成四维分析标准", progress=0.5)

        # 开启一个新的专属数据库连接 (因为这里是后台独立线程，不能用 API 层的连接)
        with Session(engine) as session:
            # 查出当前数据库里，所有状态为 pending_regenerate (排队中) 的知识点
            kps = session.exec(select(KP).where(KP.status == "pending_regenerate")).all()
            # 获取一共有多少个，用来算进度条百分比
            total_kps = len(kps)
            
            # 一个一个遍历过去，依次调用大模型生成 Rubric
            for idx, kp in enumerate(kps):
                print(f"🔄 正在生成 Rubric ({idx+1}/{total_kps}): {kp.name}")
                # 调大模型函数干活
                await generate_rubric_for_kp(kp, session)
                
                # 计算动态进度。比如有 2 个知识点：处理完第一个进度是 70%，第二个是 90%
                if total_kps > 0:
                    current_progress = 0.5 + (0.4 * (idx + 1) / total_kps)
                    # 每处理完一个，就去数据库里刷新一次进度条和当前进行到的序号
                    update_material_status(
                        material_id=material_id, 
                        status="generating", 
                        step=f"正在生成知识点解析 ({idx+1}/{total_kps})", 
                        progress=round(current_progress, 2) # 保留两位小数
                    )

        # ==========================================
        # 阶段 3：顺利结束
        # ==========================================
        # 所有代码都跑通了，没报错。告诉前端：“大功告成”，进度条推满 100%
        update_material_status(material_id=material_id, status="done", step="解析完成", progress=1.0)
        print(f"🎉 [后台任务结束] 教材 {material_id} 全部处理完成！")

    except Exception as e:
        # ==========================================
        # 异常兜底 (防雪崩机制)
        # ==========================================
        # 如果上面任何一行代码崩溃（比如 API 超时），就一定会跳到这里
        error_msg = f"处理中断: {str(e)}"
        print(f"❌ [后台任务失败] {error_msg}")
        # 将状态置为 failed，进度清零，并把错误信息写进去，前端识别到 failed 就会显示重试按钮
        update_material_status(material_id=material_id, status="failed", step="解析失败", progress=0.0, error=error_msg)