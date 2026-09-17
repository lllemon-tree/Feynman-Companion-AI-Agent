from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.learning import (
    KnowledgeReviewItemResponse,
    KnowledgeReviewListResponse,
)
from backend.app.services.review_list_service import (
    add_report_to_review_list,
    list_review_items,
)


router = APIRouter(prefix="/study-review", tags=["study-review"])


@router.get("", response_model=KnowledgeReviewListResponse)
def review_list(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return KnowledgeReviewListResponse(data=list_review_items(db, actor.user_id))


@router.post("/reports/{report_id}", response_model=KnowledgeReviewItemResponse)
def add_report(
    report_id: str,
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return KnowledgeReviewItemResponse(
        data=add_report_to_review_list(db, actor.user_id, report_id, "manual")
    )
