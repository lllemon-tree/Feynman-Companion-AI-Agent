# backend/app/api/kp.py

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from backend.app.api.dependencies import get_current_actor
from backend.app.core.config import get_settings
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.knowledge import (
    KPDetailResponse, KPDetailData, KPRubric, KPSourceChunk,
    KPCreateRequest, KPCreateResponse, KPCreateData,
    KPUpdateRequest, KPUpdateResponse, KPUpdateData,
    KPDeleteResponse, KPDeleteData, KPRegenerateResponse
)
from backend.app.services.kp_service import (
    get_kp_detail_from_db, create_kp_in_db, update_kp_in_db,
    delete_kp_in_db, trigger_regenerate_in_db
)
from backend.app.services.workflow_service import regenerate_kp_workflow

router = APIRouter(prefix="/kp", tags=["Knowledge Point"])

@router.get("/{kp_id}", response_model=KPDetailResponse)
async def get_kp_detail(
    kp_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        return KPDetailResponse(
            code=200, msg="success",
            data=KPDetailData(
                kp_id=kp_id, name="Dijkstra 算法", summary="非负权图求单源最短路径的贪心算法",
                page_start=30, page_end=33, status="done",
                rubric=KPRubric(),
                source_chunks=[KPSourceChunk(chunk_id="chunk-demo", page=32, text="Dijkstra算法的核心思想是...")]
            )
        )

    detail_data = get_kp_detail_from_db(session, kp_id, user_id=actor.user_id)
    return KPDetailResponse(code=200, msg="success", data=detail_data)

@router.post("", response_model=KPCreateResponse)
async def create_kp(
    request: KPCreateRequest,
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        return KPCreateResponse(
            code=200, msg="success",
            data=KPCreateData(kp_id="kp-new-999", status="pending_regenerate")
        )

    create_data = create_kp_in_db(session, request, user_id=actor.user_id)
    background_tasks.add_task(regenerate_kp_workflow, create_data.kp_id)
    return KPCreateResponse(code=200, msg="success", data=create_data)

@router.patch("/{kp_id}", response_model=KPUpdateResponse)
async def update_kp(
    kp_id: str,
    request: KPUpdateRequest,
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        triggered = request.page_start is not None or request.page_end is not None
        return KPUpdateResponse(
            code=200, msg="success",
            data=KPUpdateData(kp_id=kp_id, regenerate_triggered=triggered, status="pending_regenerate" if triggered else "done")
        )

    update_data = update_kp_in_db(session, kp_id, request, user_id=actor.user_id)
    if update_data.regenerate_triggered:
        background_tasks.add_task(regenerate_kp_workflow, kp_id)
    return KPUpdateResponse(code=200, msg="success", data=update_data)

@router.delete("/{kp_id}", response_model=KPDeleteResponse)
async def delete_kp(
    kp_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        return KPDeleteResponse(code=200, msg="success", data=KPDeleteData(kp_id=kp_id, deleted=True))

    delete_data = delete_kp_in_db(session, kp_id, user_id=actor.user_id)
    return KPDeleteResponse(code=200, msg="success", data=delete_data)

@router.post("/{kp_id}/regenerate", response_model=KPRegenerateResponse)
async def regenerate_kp(
    kp_id: str,
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        return KPRegenerateResponse(code=200, msg="success", data=KPCreateData(kp_id=kp_id, status="pending_regenerate"))

    regenerate_data = trigger_regenerate_in_db(session, kp_id, user_id=actor.user_id)
    background_tasks.add_task(regenerate_kp_workflow, kp_id)
    return KPRegenerateResponse(code=200, msg="success", data=regenerate_data)
