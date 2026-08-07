from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.user_stats import UserStatsResponse
from backend.app.services.user_stats_service import get_user_learning_stats


router = APIRouter(prefix="/user", tags=["UserStats"])


@router.get("/stats", response_model=UserStatsResponse)
def get_user_stats(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return UserStatsResponse(
        code=200,
        msg="success",
        data=get_user_learning_stats(db, actor.user_id),
    )
