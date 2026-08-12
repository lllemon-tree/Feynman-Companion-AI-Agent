from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from backend.app.core.database import get_session
from backend.app.api.dependencies import require_current_user, CurrentActor
from backend.app.models.knowledge_gap import KnowledgeGapStatus, KnowledgeGapUpdate
from backend.app.services.knowledge_gap_service import KnowledgeGapService

# 实例化 APIRouter，指定路由统一前缀为 /gaps，Swagger 标签分类为 KnowledgeGap
router = APIRouter(prefix="/gaps", tags=["KnowledgeGap"])


# 声明 HTTP GET 请求路由，路径为 /gaps，用于分页获取漏洞列表[cite: 1, 3]
@router.get("", response_model=dict)
def get_gaps(
    # 接收 URL query 参数 status，可选（如 ?status=open）[cite: 1, 3]
    status: Optional[KnowledgeGapStatus] = None,
    # 接收 URL query 参数 page，默认第 1 页[cite: 1, 3]
    page: Annotated[int, Query(ge=1)] = 1,
    # 接收 URL query 参数 page_size，默认每页 20 条[cite: 1, 3]
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    # 注入登录鉴权依赖，解析当前用户[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入数据库会话依赖
    session: Session = Depends(get_session),
):
    """GET /api/v1/gaps — 查询漏洞列表（支持 status 过滤与分页）[cite: 1, 3]"""
    # 调用 Service 层获取分页数据字典[cite: 1, 3]
    data = KnowledgeGapService.get_user_gaps(
        session, actor.user_id, status=status, page=page, page_size=page_size
    )
    # 按契约返回统一 JSON 响应[cite: 1, 3]
    return {
        "code": 200,
        "msg": "success",
        "data": data,
    }


# 声明 HTTP GET 请求路由，路径为 /gaps/stats，用于获取漏洞统计概览数据[cite: 1, 3]
@router.get("/stats", response_model=dict)
def get_gap_stats(
    # 注入登录鉴权依赖[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入数据库会话依赖
    session: Session = Depends(get_session),
):
    """GET /api/v1/gaps/stats — 查询漏洞统计数据（按状态/维度统计）[cite: 1, 3]"""
    # 调用 Service 层的统计计算方法[cite: 1, 3]
    stats_data = KnowledgeGapService.get_gap_stats(session, actor.user_id)
    # 按契约结构返回统计数据[cite: 1, 3]
    return {
        "code": 200,
        "msg": "success",
        "data": stats_data,
    }


@router.get("/review-due", response_model=dict)
def get_review_due_gaps(
    actor: CurrentActor = Depends(require_current_user),
    session: Session = Depends(get_session),
):
    """GET /api/v1/gaps/review-due — 查询当前用户今天到期的复习项。"""
    return {
        "code": 200,
        "msg": "success",
        "data": KnowledgeGapService.get_review_due_gaps(
            session,
            actor.user_id,
        ),
    }


# 声明 HTTP PATCH 请求路由，路径为 /gaps/{gap_id}，用于修改某个漏洞的状态[cite: 1, 3]
@router.patch("/{gap_id}", response_model=dict)
def update_gap_status(
    # 从 URL 路径中提取 gap_id 参数[cite: 1, 3]
    gap_id: str,
    # 校验并解析请求体中的 status 字段[cite: 1, 3]
    gap_in: KnowledgeGapUpdate,
    # 注入登录鉴权依赖[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入数据库会话依赖
    session: Session = Depends(get_session),
):
    """PATCH /api/v1/gaps/{gap_id} — 更新漏洞状态（如标记复习中/已掌握）[cite: 1, 3]"""
    # 调用 Service 层执行状态更新操作[cite: 1, 3]
    result = KnowledgeGapService.update_gap_status(
        session, actor.user_id, gap_id, gap_in
    )
    # 若漏洞不存在或不属于当前用户，抛出 404 异常
    if not result:
        raise HTTPException(status_code=404, detail="漏洞不存在或无使用权限")

    # 返回成功响应[cite: 1, 3]
    return {
        "code": 200,
        "msg": "success",
        "data": result,
    }
