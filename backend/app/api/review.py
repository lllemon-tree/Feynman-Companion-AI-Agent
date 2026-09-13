from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.services.review_service import (
    NoUnresolvedGapsError,
    get_review_result,
    get_review_stats,
    start_review,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])


class StartReviewRequest(BaseModel):
    kp_id: str = Field(min_length=1)
    source: Literal["gap", "due"] = "gap"


@router.post("/start")
def start(
    request: StartReviewRequest,
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    try:
        data = start_review(db, actor.user_id, request.kp_id, request.source)
    except NoUnresolvedGapsError:
        return JSONResponse(status_code=409, content={"code": 409, "msg": "no unresolved gaps", "data": None})
    return {"code": 200, "msg": "success", "data": data}


@router.get("/stats")
def stats(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return {"code": 200, "msg": "success", "data": get_review_stats(db, actor.user_id)}


@router.get("/{review_id}")
def detail(
    review_id: str,
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    data = get_review_result(db, actor.user_id, review_id)
    if data is None:
        raise HTTPException(status_code=404, detail="review not found")
    return {"code": 200, "msg": "success", "data": data}
