"""知识点复习列表相关接口"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, func, select

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.knowledge_gap import (
    KnowledgeGap,
    ReportReviewEnrollmentData,
    ReportReviewEnrollmentResponse,
)
from backend.app.services.review_list_service import add_report_to_review_list


router = APIRouter(prefix="/study-review", tags=["study-review"])


@router.post("/reports/{report_id}", response_model=ReportReviewEnrollmentResponse)
def add_report(
    report_id: str,
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return ReportReviewEnrollmentResponse(
        data=add_report_to_review_list(db, actor.user_id, report_id, "manual")
    )


class StudyReviewItem:
    """知识点复习列表中的单条记录"""
    review_item_id: str  # kp_id
    kp_id: str
    kp_name: str
    material_id: Optional[str]
    material_name: Optional[str]
    source: str  # "automatic" 或 "manual"
    average_score: Optional[float]
    dimension_count: int


@router.get("/list")
def list_study_review(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=200),
):
    """获取用户的知识点复习列表，按 kp_id 分组，返回每个 KP 的最新状态"""
    # 查询该用户所有 open 状态的 gap
    gaps = db.exec(
        select(KnowledgeGap)
        .where(
            col(KnowledgeGap.user_id) == actor.user_id,
            col(KnowledgeGap.status) == "open",
        )
        .order_by(col(KnowledgeGap.created_at).desc())
        .limit(limit)
    ).all()

    # 按 kp_id 分组，取每个 KP 的最新记录
    kp_groups: dict[str, list] = {}
    for gap in gaps:
        kp_groups.setdefault(gap.kp_id, []).append(gap)

    items = []
    for kp_id, group in kp_groups.items():
        latest = group[0]  # 最新的记录
        scores = [g.score for g in group if g.score is not None]
        avg_score = sum(scores) / len(scores) if scores else None

        # 判断来源：如果有手动添加的记录就是 manual，否则 automatic
        source = "manual" if any(g.source_session_id is None for g in group) else "automatic"

        items.append({
            "review_item_id": kp_id,
            "kp_id": kp_id,
            "kp_name": latest.kp_name,
            "material_id": latest.material_id,
            "material_name": latest.material_name,
            "source": source,
            "average_score": round(avg_score, 1) if avg_score is not None else None,
            "dimension_count": len(group),
        })

    # 按平均分数升序排列（分数低的优先复习）
    items.sort(key=lambda x: x["average_score"] if x["average_score"] is not None else 10)

    return {
        "code": 200,
        "msg": "success",
        "data": {
            "items": items,
            "total": len(items),
        },
    }
