from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dependencies import get_current_actor
from backend.app.models.auth import CurrentActor
from backend.app.models.feynman import (
    ApiResponse,
    FeynmanChatRequest,
    GreetingResponse,
    ResetSessionRequest,
    ResetSessionResponse,
    SessionDetailResponse,
    SessionDebugResponse,
    SessionListResponse,
)
from backend.app.services.feynman_service import get_feynman_service
from backend.app.services.session_store import SessionAccessDeniedError


router = APIRouter(prefix="/feynman", tags=["feynman"])


@router.get("/greeting", response_model=GreetingResponse)
async def greeting(
    kp_id: Optional[str] = None,
    _actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    try:
        data = service.greeting(kp_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GreetingResponse(
        code=200,
        msg="success",
        data=data,
    )


@router.post("/chat", response_model=ApiResponse)
async def chat(
    request: FeynmanChatRequest,
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    try:
        data = await service.chat(request, actor.user_id)
    except ValueError as exc:
        return ApiResponse(code=400, msg=str(exc), data=None)
    except SessionAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc
    return ApiResponse(code=200, msg="success", data=data)


@router.post("/reset", response_model=ResetSessionResponse)
async def reset(
    request: ResetSessionRequest,
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    try:
        data = service.reset(request, actor.user_id)
    except SessionAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResetSessionResponse(code=200, msg="success", data=data)


@router.get("/session/{session_id}", response_model=SessionDebugResponse)
async def inspect_session(
    session_id: str,
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    try:
        data = service.inspect_session(session_id, actor.user_id)
    except SessionAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionDebugResponse(code=200, msg="success", data=data)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    try:
        data = service.get_session_detail(session_id, actor.user_id)
    except SessionAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionDetailResponse(code=200, msg="success", data=data)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()
    data = service.list_sessions(actor.user_id)
    return SessionListResponse(code=200, msg="success", data=data)
