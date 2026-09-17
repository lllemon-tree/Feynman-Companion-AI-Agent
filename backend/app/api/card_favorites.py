from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session

from backend.app.api.dependencies import get_current_actor
from backend.app.core.database import get_session
from backend.app.models.auth import CurrentActor
from backend.app.models.learning import (
    FavoriteCardCreateRequest,
    FavoriteCardListResponse,
    FavoriteCardResponse,
    FavoriteCardUpdateRequest,
    FavoriteCollectionCreateRequest,
    FavoriteCollectionListResponse,
    FavoriteCollectionResponse,
    FavoriteCollectionUpdateRequest,
    FavoriteStatusResponse,
)
from backend.app.services.card_favorite_service import (
    add_favorite,
    create_collection,
    delete_collection,
    favorite_status,
    list_collections,
    list_favorites,
    remove_favorite,
    update_collection,
    update_favorite,
)


router = APIRouter(prefix="/card-favorites", tags=["Knowledge Card Favorites"])


def _require_account(actor: CurrentActor) -> None:
    if actor.is_guest:
        raise HTTPException(status_code=403, detail="登录后才能使用知识收藏")


@router.get("", response_model=FavoriteCardListResponse)
def get_favorites(
    q: str = Query(default="", max_length=100),
    collection_id: str | None = None,
    tag: str | None = Query(default=None, max_length=20),
    sort: str = Query(default="recent", pattern="^(recent|oldest|name)$"),
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    data = list_favorites(session, actor.user_id, q, collection_id, tag, sort)
    return FavoriteCardListResponse(data=data)


@router.post("", response_model=FavoriteCardResponse)
def create_favorite(
    request: FavoriteCardCreateRequest,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteCardResponse(data=add_favorite(session, actor.user_id, request))


@router.get("/collections", response_model=FavoriteCollectionListResponse)
def get_collections(
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteCollectionListResponse(data=list_collections(session, actor.user_id))


@router.post("/collections", response_model=FavoriteCollectionResponse)
def post_collection(
    request: FavoriteCollectionCreateRequest,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteCollectionResponse(data=create_collection(session, actor.user_id, request))


@router.patch("/collections/{collection_id}", response_model=FavoriteCollectionResponse)
def patch_collection(
    collection_id: str,
    request: FavoriteCollectionUpdateRequest,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    data = update_collection(session, actor.user_id, collection_id, request)
    return FavoriteCollectionResponse(data=data)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_collection(
    collection_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    delete_collection(session, actor.user_id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cards/{card_id}/status", response_model=FavoriteStatusResponse)
def get_favorite_status(
    card_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteStatusResponse(data=favorite_status(session, actor.user_id, card_id))


@router.patch("/{favorite_id}", response_model=FavoriteCardResponse)
def patch_favorite(
    favorite_id: str,
    request: FavoriteCardUpdateRequest,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteCardResponse(data=update_favorite(
        session, actor.user_id, favorite_id, request
    ))


@router.delete("/{favorite_id}", response_model=FavoriteStatusResponse)
def delete_favorite(
    favorite_id: str,
    actor: CurrentActor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    _require_account(actor)
    return FavoriteStatusResponse(data=remove_favorite(session, actor.user_id, favorite_id))
