from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.knowledge_gap import ReportReviewEnrollmentResponse
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
