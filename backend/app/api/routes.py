import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

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
from backend.app.services.feynman_service import ReviewPersistenceError, get_feynman_service
from backend.app.services.session_store import SessionAccessDeniedError


router = APIRouter(prefix="/feynman", tags=["feynman"])


@router.get("/greeting", response_model=GreetingResponse)
async def greeting(
    kp_id: Optional[str] = None,
    _actor: CurrentActor = Depends(get_current_actor),
    session_id: Optional[str] = None,
):
    service = get_feynman_service()
    try:
        data = service.greeting(kp_id, session_id, _actor.user_id)
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
    except ReviewPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        print(f"❌ chat 500 error: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="internal server error") from exc
    return ApiResponse(code=200, msg="success", data=data)


@router.post("/chat/stream")
async def chat_stream(
    request: FeynmanChatRequest,
    actor: CurrentActor = Depends(get_current_actor),
):
    service = get_feynman_service()

    async def events():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        # 首个事件先于数据库、检索和模型调用发出，避免客户端在首字前一直空白。
        yield json.dumps({"type": "status", "stage": "loading", "text": "正在读取学习进度…"}, ensure_ascii=False) + "\n"

        async def run_chat():
            try:
                data = await service.chat(
                    request, actor.user_id,
                    on_reply_delta=lambda delta: queue.put_nowait({"type": "delta", "text": delta}),
                    on_status=lambda stage, message: queue.put_nowait(
                        {"type": "status", "stage": stage, "text": message}
                    ),
                )
                queue.put_nowait({"type": "done", "data": data.model_dump(mode="json")})
            except (ValueError, SessionAccessDeniedError) as exc:
                queue.put_nowait({"type": "error", "message": str(exc)})
            except ReviewPersistenceError as exc:
                queue.put_nowait({"type": "error", "message": str(exc)})
            except Exception:
                queue.put_nowait({"type": "error", "message": "讲解暂时失败，请稍后重试"})

        task = asyncio.create_task(run_chat())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    # 保持连接活跃；心跳不代表模型已产生新内容。
                    yield json.dumps({"type": "heartbeat"}) + "\n"
                    continue
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in {"done", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        events(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
