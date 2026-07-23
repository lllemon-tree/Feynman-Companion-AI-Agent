from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from backend.app.core.database import get_session
from backend.app.core.security import decode_access_token
from backend.app.models.auth import CurrentActor, GUEST_USER_ID, User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_actor(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[Session, Depends(get_session)],
) -> CurrentActor:
    if credentials is None:
        return CurrentActor(user_id=GUEST_USER_ID, username=None, is_guest=True)

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, payload["sub"])
    if user is None or user.username != payload["username"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentActor(user_id=user.id, username=user.username, is_guest=False)


def require_current_user(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
) -> CurrentActor:
    if actor.is_guest:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return actor
