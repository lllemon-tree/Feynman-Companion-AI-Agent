from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session

from backend.app.api.dependencies import get_current_actor
from backend.app.core.config import get_settings
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor, GUEST_USER_ID
from backend.app.models.knowledge import (
    ChapterItem,
    KnowledgePointItem,
    MaterialStatusData,
    MaterialStatusResponse,
    MaterialTreeData,
    MaterialTreeResponse,
    MaterialUploadData,
    MaterialUploadResponse,
    SubjectListResponse,
)
from backend.app.services.material_service import (
    get_material_status_from_db,
    get_material_tree_from_db,
    get_subjects_from_db,
    prepare_material_retry,
)
from backend.app.services.pdf_service import save_and_process_pdf
from backend.app.services.workflow_service import run_full_extraction_workflow
from backend.app.services.vector_store import vector_store
from backend.app.services.rag_service import build_material_embeddings

# 1.  ()
# prefix="/material":  URL 
# tags=["Material"]:  FastAPI  Swagger 
router = APIRouter(prefix="/material", tags=["Material"])


@router.get("/subjects", response_model=SubjectListResponse)
async def get_subjects(
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    subjects = get_subjects_from_db(session, user_id=actor.user_id)
    return SubjectListResponse(code=200, msg="success", data=subjects)

# =====================================================================
#  1
#  URL: GET /api/v1/material/{material_id}/status
# =====================================================================
@router.get("/{material_id}/status", response_model=MaterialStatusResponse)
async def get_material_status(
    material_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    if get_settings().material_mock:
        #  Pydantic FastAPI  JSON 
        #  material_id 
        return MaterialStatusResponse(
            code=200,
            msg="success",
            data=MaterialStatusData(
                material_id=material_id, 
                status="done",           # PRD parsing/chunking/extracting/generating/done/failed
                step="",             # 
                progress=1.0,            # 0.0  1.0 
                error=None               # 
            )
        )

    #  Service 
    status_data = get_material_status_from_db(session, material_id, user_id=actor.user_id)
    return MaterialStatusResponse(code=200, msg="success", data=status_data)


# =====================================================================
#  2 ( ->  ->  -> )
#  URL: GET /api/v1/material/tree?subject=
# =====================================================================
@router.get("/tree", response_model=MaterialTreeResponse)
async def get_material_tree(
    subject: str = "computer",
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """Get material tree filtered by subject and current user."""
    if get_settings().material_mock:
        #  PRD 
        # Tree -> Chapter -> KnowledgePoint
        return MaterialTreeResponse(
            code=200,
            msg="success",
            data=[
                MaterialTreeData(
                    material_id="mat-demo",
                    title="",
                    status="done",
                    step="",
                    progress=1.0,
                    chapters=[
                        ChapterItem(
                            chapter_id="ch-demo",
                            title="",
                            knowledge_points=[
                                KnowledgePointItem(
                                    kp_id="kp-demo",
                                    name="Dijkstra ",
                                    summary="",
                                    page_start=30,
                                    page_end=33,
                                    status="done",
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    #  Service 
    tree_data = get_material_tree_from_db(session, subject, user_id=actor.user_id)
    return MaterialTreeResponse(code=200, msg="success", data=tree_data)
# =====================================================================
#  3 PDF
#  URL: POST /api/v1/material/upload
# =====================================================================
@router.post("/upload", response_model=MaterialUploadResponse)
async def upload_material(
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    file: UploadFile = File(...),
    subject: str = Form(...),
    name: str = Form(""),
):
    if get_settings().material_mock:
        return MaterialUploadResponse(
            code=200,
            msg="success",
            data=MaterialUploadData(material_id="mat-demo-upload", status="parsing")
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=" PDF ")
    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="")

    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF  50MB")

    try:
        generated_id = save_and_process_pdf(
            content,
            subject,
            filename=file.filename,
            name=name,
            user_id=actor.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f": {str(e)}")

    # 3.  ( try-except add_task )
    background_tasks.add_task(run_full_extraction_workflow, generated_id)
   
    # 4. 
    return MaterialUploadResponse(
        code=200,
        msg="success",
        data=MaterialUploadData(material_id=generated_id, status="parsing")
    )
# =====================================================================
#  4
#  URL: GET /api/v1/material/{material_id}/retrieve
# =====================================================================
@router.get("/{material_id}/retrieve")
def retrieve_chunks(
    material_id: str,
    query: str = Query(..., description=""),
    top_k: int = Query(3, description=" Chunk "),
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """RAG  Top-K  Chunk"""
    # 
    status_data = get_material_status_from_db(session, material_id, user_id=actor.user_id)
    results = vector_store.search(material_id=material_id, query=query, top_k=top_k)
    return {"code": 200, "status": "success", "data": results}


@router.post("/{material_id}/embedding/rebuild")
def rebuild_material_embedding(
    material_id: str,
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    db: Session = Depends(get_session),
):
    """"""
    # 
    get_material_status_from_db(db, material_id, user_id=actor.user_id)
    background_tasks.add_task(build_material_embeddings, session=db, material_id=material_id)
    return {"code": 200, "status": "success", "message": f" {material_id} "}


@router.post("/{material_id}/retry", response_model=MaterialUploadResponse)
async def retry_material(
    material_id: str,
    background_tasks: BackgroundTasks,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """"""
    material = prepare_material_retry(session, material_id, user_id=actor.user_id)
    background_tasks.add_task(run_full_extraction_workflow, material_id)
    return MaterialUploadResponse(
        code=200,
        msg="success",
        data=MaterialUploadData(material_id=material.id, status=material.status),
    )


@router.delete("/{material_id}")
def delete_material(
    material_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """"""
    # 
    from backend.app.models.knowledge import Material
    import os as _os

    material = session.get(Material, material_id)
    if material is None or material.user_id != actor.user_id:
        raise HTTPException(status_code=404, detail=" ID ")

    # 
    vector_store.delete_material(material_id)

    #  PDF
    if material.raw_path and _os.path.exists(material.raw_path):
        _os.remove(material.raw_path)

    #  (CASCADE //)
    session.delete(material)
    session.commit()

    return {"code": 200, "msg": "success", "data": {"material_id": material_id, "deleted": True}}
