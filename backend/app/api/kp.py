# backend/app/api/kp.py

# APIRouter 用于创建接口路由，Depends 用于依赖注入
from fastapi import APIRouter, BackgroundTasks, Depends
# 引入 Session 类型提示
from sqlmodel import Session

# 导入获取数据库连接的函数，每次接口被调用时，FastAPI 会用它自动连数据库
from backend.app.core.config import get_settings
from backend.app.core.database import get_session

# 导入我们刚刚在 kp_service.py 里写好的那 5 个真实处理函数
from backend.app.services.kp_service import (     
    get_kp_detail_from_db, create_kp_in_db, update_kp_in_db,
    delete_kp_in_db, trigger_regenerate_in_db
)
from backend.app.services.workflow_service import regenerate_kp_workflow

# 导入 Pydantic 模型，用于限制前端传进来的 JSON 格式，以及包装我们发出去的数据格式
from backend.app.models.knowledge import (
    KPDetailResponse, KPDetailData, KPRubric, KPSourceChunk,
    KPCreateRequest, KPCreateResponse, KPCreateData,
    KPUpdateRequest, KPUpdateResponse, KPUpdateData,
    KPDeleteResponse, KPDeleteData, KPRegenerateResponse
)

# 初始化路由，所有的 URL 都会自动带上 /api/v1/kp 前缀 (在 main.py 里挂载时配置了 /api/v1)
router = APIRouter(prefix="/kp", tags=["Knowledge Point"])

@router.get("/{kp_id}", response_model=KPDetailResponse)
async def get_kp_detail(kp_id: str, session: Session = Depends(get_session)):
    """
    GET 请求：前端在 URL 里带上 kp_id 查详情
    """
    
    # 如果开关开启，提前 return 假数据，函数到此结束，绝不走后面的数据库代码
    if get_settings().material_mock:
        return KPDetailResponse(
            code=200, msg="success",
            # 填入 PRD 规定的 Mock 样例数据
            data=KPDetailData(
                kp_id=kp_id, name="Dijkstra 算法", summary="非负权图求单源最短路径的贪心算法",
                page_start=30, page_end=33, status="done",
                rubric=KPRubric(),
                source_chunks=[KPSourceChunk(chunk_id="chunk-demo", page=32, text="Dijkstra算法的核心思想是...")]
            )
        )

    # 如果开关关闭，把拿到的 session 钥匙和 kp_id 扔给底层车间处理
    detail_data = get_kp_detail_from_db(session, kp_id)
    # 把底层返回的干净数据，套上 code=200 的外壳发给前端
    return KPDetailResponse(code=200, msg="success", data=detail_data)

@router.post("", response_model=KPCreateResponse)
# POST 请求：前端会在 Request Body 里塞入 JSON，FastAPI 会自动用 KPCreateRequest 去验证
async def create_kp(
    request: KPCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    新增知识点
    """
    if get_settings().material_mock:
        # 直接返回成功，告诉前端状态是待生成
        return KPCreateResponse(
            code=200, msg="success",
            data=KPCreateData(kp_id="kp-new-999", status="pending_regenerate")
        )

    create_data = create_kp_in_db(session, request)
    background_tasks.add_task(regenerate_kp_workflow, create_data.kp_id)
    return KPCreateResponse(code=200, msg="success", data=create_data)

@router.patch("/{kp_id}", response_model=KPUpdateResponse)
async def update_kp(
    kp_id: str,
    request: KPUpdateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    PATCH 请求：局部修改。允许前端只传想改的字段。
    """
    if get_settings().material_mock:
        # 判断前端传来的数据里，有没有关于页码的字段。如果有，triggered 就是 True。
        triggered = request.page_start is not None or request.page_end is not None
        return KPUpdateResponse(
            code=200, msg="success",
            # 如果改了页码，状态就变成 pending_regenerate 告诉前端等着，否则就是 done
            data=KPUpdateData(kp_id=kp_id, regenerate_triggered=triggered, status="pending_regenerate" if triggered else "done")
        )

    update_data = update_kp_in_db(session, kp_id, request)
    if update_data.regenerate_triggered:
        background_tasks.add_task(regenerate_kp_workflow, kp_id)
    return KPUpdateResponse(code=200, msg="success", data=update_data)

@router.delete("/{kp_id}", response_model=KPDeleteResponse)
async def delete_kp(kp_id: str, session: Session = Depends(get_session)):
    """
    DELETE 请求：根据 URL 里的 id 删掉该知识点
    """
    if get_settings().material_mock:
        return KPDeleteResponse(code=200, msg="success", data=KPDeleteData(kp_id=kp_id, deleted=True))

    delete_data = delete_kp_in_db(session, kp_id)
    return KPDeleteResponse(code=200, msg="success", data=delete_data)

@router.post("/{kp_id}/regenerate", response_model=KPRegenerateResponse)
async def regenerate_kp(
    kp_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    POST 请求：这只是个触发按钮，所以不需要前端传复杂的 Request Body，带个 id 就行
    """
    if get_settings().material_mock:
        return KPRegenerateResponse(code=200, msg="success", data=KPCreateData(kp_id=kp_id, status="pending_regenerate"))

    regenerate_data = trigger_regenerate_in_db(session, kp_id)
    background_tasks.add_task(regenerate_kp_workflow, kp_id)
    return KPRegenerateResponse(code=200, msg="success", data=regenerate_data)
