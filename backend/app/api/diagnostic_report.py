from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.diagnostic_report import (
    ReportDetailResponse,
    ReportListResponse,
)
from backend.app.services.diagnostic_report_service import (
    get_report_detail,
    list_reports,
)


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportListResponse)
def report_list(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return ReportListResponse(
        code=200,
        msg="success",
        data=list_reports(db, actor.user_id, page, page_size),
    )


@router.get("/{report_id}", response_model=ReportDetailResponse)
def report_detail(
    report_id: str,
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    data = get_report_detail(db, actor.user_id, report_id)
    if data is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ReportDetailResponse(code=200, msg="success", data=data)
