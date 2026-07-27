from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.database import get_session
from backend.app.models.auth import (
    AuthCredentialsRequest,
    CurrentActor,
    CurrentUserData,
    CurrentUserResponse,
    LoginResponse,
    RegisterResponse,
)
from backend.app.services.auth_service import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
    login_user,
    register_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(
    request: AuthCredentialsRequest,
    session: Annotated[Session, Depends(get_session)],
):
    try:
        data = register_user(
            session,
            username=request.username,
            password=request.password,
        )
    except UsernameAlreadyExistsError as exc:
        return JSONResponse(
            status_code=400,
            content=RegisterResponse(code=400, msg=str(exc), data=None).model_dump(),
        )
    return RegisterResponse(code=200, msg="注册成功，请登录", data=data)


@router.post("/login", response_model=LoginResponse)
def login(
    request: AuthCredentialsRequest,
    session: Annotated[Session, Depends(get_session)],
):
    try:
        data = login_user(
            session,
            username=request.username,
            password=request.password,
        )
    except InvalidCredentialsError as exc:
        return JSONResponse(
            status_code=401,
            content=LoginResponse(code=401, msg=str(exc), data=None).model_dump(),
        )
    return LoginResponse(code=200, msg="登录成功", data=data)


@router.get("/current", response_model=CurrentUserResponse)
def current_user(
    actor: Annotated[CurrentActor, Depends(require_current_user)],
):
    return CurrentUserResponse(
        code=200,
        msg="success",
        data=CurrentUserData(
            user_id=actor.user_id,
            username=actor.username or "",
        ),
    )
