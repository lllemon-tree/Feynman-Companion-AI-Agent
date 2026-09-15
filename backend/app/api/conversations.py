"""API for free-form expert and teach-back conversations."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from backend.app.api.dependencies import require_current_user
from backend.app.core.config import get_settings
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.conversation import FinishExplanationRequest, SendMessageRequest
from backend.app.services.conversation_service import (
    ConversationNotFound,
    ConversationService,
    InvalidAssessment,
)
from backend.app.services.deepseek_client import DeepSeekClient


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


def _model_options():
    settings = get_settings()
    options = settings.free_chat_models or (settings.deepseek_model,)
    default = settings.deepseek_model if settings.deepseek_model in options else options[0]
    return options, default


def _selected_model(requested: str | None) -> str:
    options, default = _model_options()
    if requested is None:
        return default
    if requested not in options:
        raise HTTPException(status_code=400, detail="所选模型不可用，请重新选择")
    return requested


def get_conversation_service() -> ConversationService:
    settings = get_settings()
    client = DeepSeekClient(settings) if settings.llm_provider == "deepseek" and settings.deepseek_configured else None
    return ConversationService(client)


@router.post("")
def create_conversation(
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    return {"code": 200, "msg": "success", "data": service.create(db, actor.user_id)}


@router.get("")
def list_conversations(
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    return {"code": 200, "msg": "success", "data": service.list(db, actor.user_id)}


@router.get("/models")
def list_chat_models():
    options, default = _model_options()
    labels = {"deepseek-flash": "DeepSeek Flash", "deepseek-v4-pro": "DeepSeek V4 Pro"}
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "default_model": default,
            "models": [{"id": model, "name": labels.get(model, model)} for model in options],
        },
    }


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    try:
        data = service.get(db, conversation_id, actor.user_id)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    return {"code": 200, "msg": "success", "data": data}


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    if service.client is None:
        raise HTTPException(status_code=503, detail="对话模型尚未配置")
    model = _selected_model(request.model)
    try:
        data = await service.send(db, conversation_id, actor.user_id, request.content, request.mode, model)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("conversation generation failed")
        raise HTTPException(status_code=502, detail="模型响应失败，请重试") from exc
    return {"code": 200, "msg": "success", "data": data}


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    request: SendMessageRequest,
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    if service.client is None:
        raise HTTPException(status_code=503, detail="对话模型尚未配置")
    model = _selected_model(request.model)
    try:
        text, history = service.prepare_send(db, conversation_id, actor.user_id, request.content)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def events():
        parts: list[str] = []
        try:
            async for delta in service.client.stream_in_conversation(request.mode, history, text, model):
                parts.append(delta)
                yield json.dumps({"type": "delta", "text": delta}, ensure_ascii=False) + "\n"
            reply = "".join(parts).strip()
            result = service.persist_reply(
                db, conversation_id, actor.user_id, text, request.mode, model, reply
            )
            yield json.dumps(
                {"type": "done", "data": result.model_dump(mode="json")}, ensure_ascii=False
            ) + "\n"
        except Exception:
            logger.exception("streaming conversation generation failed")
            yield json.dumps({"type": "error", "message": "模型响应失败，请重试"}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        events(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/assessment")
async def finish_explanation(
    conversation_id: str,
    _request: FinishExplanationRequest,
    actor: CurrentActor = Depends(require_current_user),
    db: Session = Depends(get_session),
    service: ConversationService = Depends(get_conversation_service),
):
    if service.client is None:
        raise HTTPException(status_code=503, detail="对话模型尚未配置")
    model = _selected_model(_request.model)
    try:
        data = await service.finish_explanation(db, conversation_id, actor.user_id, model)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidAssessment as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("free explanation assessment failed")
        raise HTTPException(status_code=502, detail="评估生成失败，请重试") from exc
    return {"code": 200, "msg": "success", "data": data}
