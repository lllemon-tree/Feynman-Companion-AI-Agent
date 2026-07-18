
from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, Form, HTTPException
from sqlmodel import Session
from backend.app.core.database import get_session
from backend.app.models.knowledge import MaterialUploadResponse, MaterialUploadData
from backend.app.services.pdf_service import save_and_process_pdf
# 导入我们在 models 里定义好的 Pydantic 数据外壳，用于规范输出格式
from backend.app.models.knowledge import (
    MaterialStatusResponse,
    MaterialStatusData,
    MaterialTreeResponse,
    MaterialTreeData,
    ChapterItem,
    KnowledgePointItem,
    MaterialUploadResponse,
    MaterialUploadData
)
from backend.app.services.workflow_service import run_full_extraction_workflow
from backend.app.services.material_service import get_material_status_from_db, get_material_tree_from_db

# 1. 初始化路由器 (设立服务员)
# prefix="/material": 这个文件里所有接口的 URL 都会自动加上这个前缀
# tags=["Material"]: 仅用于在 FastAPI 自动生成的 Swagger 接口文档中进行分组展示，方便调试
router = APIRouter(prefix="/material", tags=["Material"])

# 2. Mock 假数据开关
# 在真实后厨（解析 PDF、调大模型）写好之前，打开这个开关，直接把假数据端给前端，不阻塞前端画 UI
USE_MOCK = False

# =====================================================================
# 接口 1：查询教材解析状态
# 完整 URL: GET /api/v1/material/{material_id}/status
# =====================================================================
@router.get("/{material_id}/status", response_model=MaterialStatusResponse)
async def get_material_status(material_id: str, session: Session = Depends(get_session)):
    """
    根据给定的 material_id，查询当前教材的解析进度。
    （三引号内的这段文字，会自动显示在生成的接口文档中作为接口说明）
    """
    if USE_MOCK:
        # 直接使用 Pydantic 实例化对象并返回，FastAPI 会自动将其转换为 JSON 发给前端
        # 我们把前端传进来的 material_id 原样塞回给前端，让假数据更逼真
        return MaterialStatusResponse(
            code=200,
            msg="success",
            data=MaterialStatusData(
                material_id=material_id, 
                status="done",           # PRD 枚举值：parsing/chunking/extracting/generating/done/failed
                step="完成",             # 当前进度的中文描述
                progress=1.0,            # 0.0 到 1.0 之间的浮点数进度
                error=None               # 如果失败了，这里填错误信息
            )
        )

    # 调用 Service 层拿真实数据
    status_data = get_material_status_from_db(session, material_id)
    return MaterialStatusResponse(code=200, msg="success", data=status_data)


# =====================================================================
# 接口 2：查询知识点树 (四级级联：科目 -> 教材 -> 章节 -> 知识点)
# 完整 URL: GET /api/v1/material/tree?subject=计算机
# =====================================================================
@router.get("/tree", response_model=MaterialTreeResponse)
async def get_material_tree(subject: str = "计算机", session: Session = Depends(get_session)):
    """
    根据科目名称，查询该科目下所有已解析完成的教材，及其
    对应的章节和知识点结构。
    如果不传 subject，默认查询"计算机"科目。
    """
    if USE_MOCK:
        # 这里的结构看起来很深，是因为 PRD 要求的级联选择器需要这种“树状”数据
        # 一层一层向内嵌套实例化：Tree -> Chapter -> KnowledgePoint
        return MaterialTreeResponse(
            code=200,
            msg="success",
            data=[
                MaterialTreeData(
                    material_id="mat-demo",
                    title="数据结构教材",
                    chapters=[
                        ChapterItem(
                            chapter_id="ch-demo",
                            title="图论",
                            knowledge_points=[
                                KnowledgePointItem(
                                    kp_id="kp-demo",
                                    name="Dijkstra 算法",
                                    summary="非负权图求单源最短路径的贪心算法"
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    # 调用 Service 层组装树状结构
    tree_data = get_material_tree_from_db(session, subject)
    return MaterialTreeResponse(code=200, msg="success", data=tree_data)
# =====================================================================
# 接口 3：上传教材 PDF
# 完整 URL: POST /api/v1/material/upload
# =====================================================================
@router.post("/upload", response_model=MaterialUploadResponse)
async def upload_material(
    file: UploadFile = File(...), 
    subject: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks() # 必须在这里显式注入
):
    """
    接收前端上传的教材，自动实现切片存入数据库。
    调用大模型进行知识点抽取和 Rubric 生成。
    """
    if USE_MOCK:
        return MaterialUploadResponse(
            code=200,
            msg="success",
            data=MaterialUploadData(material_id="mat-demo-upload", status="parsing")
        )
    
    # 1. 读取文件
    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="文件读取失败")
    
    # 2. 调用 Service 层解析
    try:
        generated_id = save_and_process_pdf(content, subject) 
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部解析失败: {str(e)}")

    # 3. 加入后台任务 (无需 try-except，因为 add_task 本身是同步操作，不会报错)
    background_tasks.add_task(run_full_extraction_workflow, generated_id)
   
    # 4. 返回响应
    return MaterialUploadResponse(
        code=200,
        msg="success",
        data=MaterialUploadData(material_id=generated_id, status="parsing")
    )