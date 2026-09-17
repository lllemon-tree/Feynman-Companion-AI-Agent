"""User-owned knowledge-card collections, metadata, and retrieval."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.models.knowledge import Chapter, KP, Material
from backend.app.models.learning import (
    FavoriteCardCreateRequest,
    FavoriteCardData,
    FavoriteCardListData,
    FavoriteCardUpdateRequest,
    FavoriteCollectionCreateRequest,
    FavoriteCollectionData,
    FavoriteCollectionListData,
    FavoriteCollectionUpdateRequest,
    FavoriteStatusData,
    KnowledgeCard,
    KnowledgeCardCollection,
    KnowledgeCardContent,
    KnowledgeCardFavorite,
    KnowledgeCardFavoriteCollectionLink,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owned_card(
    db: Session, card_id: str, user_id: str
) -> tuple[KnowledgeCard, KP, Chapter, Material]:
    card = db.get(KnowledgeCard, card_id)
    kp = db.get(KP, card.kp_id) if card else None
    chapter = db.get(Chapter, kp.chapter_id) if kp else None
    material = db.get(Material, chapter.material_id) if chapter else None
    if card is None or kp is None or chapter is None or material is None or material.user_id != user_id:
        raise HTTPException(status_code=404, detail="知识卡片不存在")
    return card, kp, chapter, material


def _owned_favorite(db: Session, favorite_id: str, user_id: str) -> KnowledgeCardFavorite:
    favorite = db.get(KnowledgeCardFavorite, favorite_id)
    if favorite is None or favorite.user_id != user_id:
        raise HTTPException(status_code=404, detail="收藏记录不存在")
    return favorite


def _owned_collection(
    db: Session, collection_id: str, user_id: str
) -> KnowledgeCardCollection:
    collection = db.get(KnowledgeCardCollection, collection_id)
    if collection is None or collection.user_id != user_id:
        raise HTTPException(status_code=404, detail="收藏夹不存在")
    return collection


def _normalize_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    for raw in tags:
        tag = str(raw).strip()[:20]
        if tag and tag not in result:
            result.append(tag)
        if len(result) == 12:
            break
    return result


def _collection_ids(db: Session, favorite_id: str) -> list[str]:
    return list(db.exec(
        select(KnowledgeCardFavoriteCollectionLink.collection_id)
        .where(KnowledgeCardFavoriteCollectionLink.favorite_id == favorite_id)
    ).all())


def _replace_collections(
    db: Session, favorite: KnowledgeCardFavorite, collection_ids: list[str], user_id: str
) -> None:
    unique_ids = list(dict.fromkeys(collection_ids))
    for collection_id in unique_ids:
        _owned_collection(db, collection_id, user_id)
    existing = db.exec(
        select(KnowledgeCardFavoriteCollectionLink)
        .where(KnowledgeCardFavoriteCollectionLink.favorite_id == favorite.id)
    ).all()
    for link in existing:
        db.delete(link)
    for collection_id in unique_ids:
        db.add(KnowledgeCardFavoriteCollectionLink(
            id=f"fav-link-{uuid4().hex[:12]}",
            favorite_id=favorite.id,
            collection_id=collection_id,
        ))


def _serialize_favorite(db: Session, favorite: KnowledgeCardFavorite) -> FavoriteCardData:
    card = db.get(KnowledgeCard, favorite.card_id)
    content = KnowledgeCardContent.model_validate_json(
        card.content_json if card else favorite.content_snapshot_json
    )
    try:
        tags = _normalize_tags(json.loads(favorite.tags_json or "[]"))
    except (json.JSONDecodeError, TypeError):
        tags = []
    return FavoriteCardData(
        favorite_id=favorite.id,
        card_id=favorite.card_id,
        kp_id=favorite.kp_id,
        kp_name=favorite.kp_name,
        summary=favorite.summary or "暂无摘要",
        material_id=favorite.material_id,
        material_name=favorite.material_name,
        material_subject=favorite.material_subject,
        chapter_id=favorite.chapter_id,
        chapter_name=favorite.chapter_name,
        card_version=card.version if card else favorite.saved_version,
        saved_version=favorite.saved_version,
        has_update=bool(card and card.version > favorite.saved_version),
        generation_status=content.generation_status,
        coverage_level=content.coverage_level,
        estimated_minutes=content.estimated_minutes,
        sections=content.sections,
        note=favorite.note,
        tags=tags,
        is_pinned=favorite.is_pinned,
        collection_ids=_collection_ids(db, favorite.id),
        created_at=favorite.created_at,
        updated_at=favorite.updated_at,
    )


def favorite_status(db: Session, user_id: str, card_id: str) -> FavoriteStatusData:
    _owned_card(db, card_id, user_id)
    favorite = db.exec(select(KnowledgeCardFavorite).where(
        KnowledgeCardFavorite.user_id == user_id,
        KnowledgeCardFavorite.card_id == card_id,
    )).first()
    return FavoriteStatusData(
        card_id=card_id,
        is_favorited=favorite is not None,
        favorite_id=favorite.id if favorite else None,
    )


def add_favorite(
    db: Session, user_id: str, request: FavoriteCardCreateRequest
) -> FavoriteCardData:
    card, kp, chapter, material = _owned_card(db, request.card_id, user_id)
    favorite = db.exec(select(KnowledgeCardFavorite).where(
        KnowledgeCardFavorite.user_id == user_id,
        KnowledgeCardFavorite.card_id == request.card_id,
    )).first()
    if favorite is None:
        favorite = KnowledgeCardFavorite(
            id=f"favorite-{uuid4().hex[:12]}",
            user_id=user_id,
            card_id=card.id,
            kp_id=kp.id,
            kp_name=kp.name,
            summary=kp.summary or "暂无摘要",
            material_id=material.id,
            material_name=material.name or material.filename,
            material_subject=material.subject,
            chapter_id=chapter.id,
            chapter_name=chapter.title,
            content_snapshot_json=card.content_json,
            note=request.note.strip(),
            tags_json=json.dumps(_normalize_tags(request.tags), ensure_ascii=False),
            saved_version=card.version,
        )
        db.add(favorite)
        db.flush()
        _replace_collections(db, favorite, request.collection_ids, user_id)
    elif request.collection_ids or request.note.strip() or request.tags:
        favorite.note = request.note.strip()
        favorite.tags_json = json.dumps(_normalize_tags(request.tags), ensure_ascii=False)
        favorite.updated_at = _now()
        _replace_collections(db, favorite, request.collection_ids, user_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        favorite = db.exec(select(KnowledgeCardFavorite).where(
            KnowledgeCardFavorite.user_id == user_id,
            KnowledgeCardFavorite.card_id == request.card_id,
        )).first()
        if favorite is None:
            raise
    db.refresh(favorite)
    return _serialize_favorite(db, favorite)


def update_favorite(
    db: Session, user_id: str, favorite_id: str, request: FavoriteCardUpdateRequest
) -> FavoriteCardData:
    favorite = _owned_favorite(db, favorite_id, user_id)
    card = db.get(KnowledgeCard, favorite.card_id)
    if request.note is not None:
        favorite.note = request.note.strip()
    if request.tags is not None:
        favorite.tags_json = json.dumps(_normalize_tags(request.tags), ensure_ascii=False)
    if request.is_pinned is not None:
        favorite.is_pinned = request.is_pinned
    if request.collection_ids is not None:
        _replace_collections(db, favorite, request.collection_ids, user_id)
    if card is not None:
        favorite.saved_version = card.version
        favorite.content_snapshot_json = card.content_json
    favorite.updated_at = _now()
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return _serialize_favorite(db, favorite)


def remove_favorite(db: Session, user_id: str, favorite_id: str) -> FavoriteStatusData:
    favorite = _owned_favorite(db, favorite_id, user_id)
    card_id = favorite.card_id
    links = db.exec(select(KnowledgeCardFavoriteCollectionLink).where(
        KnowledgeCardFavoriteCollectionLink.favorite_id == favorite.id
    )).all()
    for link in links:
        db.delete(link)
    db.delete(favorite)
    db.commit()
    return FavoriteStatusData(card_id=card_id, is_favorited=False, favorite_id=None)


def list_favorites(
    db: Session,
    user_id: str,
    query: str = "",
    collection_id: str | None = None,
    tag: str | None = None,
    sort: str = "recent",
) -> FavoriteCardListData:
    if collection_id:
        _owned_collection(db, collection_id, user_id)
        favorite_ids = set(db.exec(
            select(KnowledgeCardFavoriteCollectionLink.favorite_id)
            .where(KnowledgeCardFavoriteCollectionLink.collection_id == collection_id)
        ).all())
    else:
        favorite_ids = None
    favorites = db.exec(select(KnowledgeCardFavorite).where(
        KnowledgeCardFavorite.user_id == user_id
    )).all()
    items: list[FavoriteCardData] = []
    normalized_query = query.strip().casefold()
    normalized_tag = tag.strip() if tag else ""
    candidate_tags: set[str] = set()
    for favorite in favorites:
        if favorite_ids is not None and favorite.id not in favorite_ids:
            continue
        item = _serialize_favorite(db, favorite)
        if normalized_query and normalized_query not in " ".join((
            item.kp_name, item.summary, item.material_name, item.chapter_name,
            item.note, " ".join(item.tags),
        )).casefold():
            continue
        candidate_tags.update(item.tags)
        if normalized_tag and normalized_tag not in item.tags:
            continue
        items.append(item)
    if sort == "name":
        items.sort(key=lambda item: (not item.is_pinned, item.kp_name.casefold()))
    elif sort == "oldest":
        items.sort(key=lambda item: (not item.is_pinned, item.created_at))
    else:
        items.sort(key=lambda item: (not item.is_pinned, -item.updated_at.timestamp()))
    return FavoriteCardListData(
        items=items, total=len(items), available_tags=sorted(candidate_tags)
    )


def list_collections(db: Session, user_id: str) -> FavoriteCollectionListData:
    collections = db.exec(select(KnowledgeCardCollection).where(
        KnowledgeCardCollection.user_id == user_id
    ).order_by(KnowledgeCardCollection.created_at)).all()
    items = []
    for collection in collections:
        count = len(db.exec(select(KnowledgeCardFavoriteCollectionLink.id).where(
            KnowledgeCardFavoriteCollectionLink.collection_id == collection.id
        )).all())
        items.append(FavoriteCollectionData(
            collection_id=collection.id,
            name=collection.name,
            description=collection.description,
            color=collection.color,
            item_count=count,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        ))
    return FavoriteCollectionListData(items=items, total=len(items))


def create_collection(
    db: Session, user_id: str, request: FavoriteCollectionCreateRequest
) -> FavoriteCollectionData:
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="收藏夹名称不能为空")
    collection = KnowledgeCardCollection(
        id=f"collection-{uuid4().hex[:12]}",
        user_id=user_id,
        name=name,
        description=request.description.strip(),
        color=request.color,
    )
    db.add(collection)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="已存在同名收藏夹") from exc
    db.refresh(collection)
    return FavoriteCollectionData(
        collection_id=collection.id, name=collection.name,
        description=collection.description, color=collection.color,
        item_count=0, created_at=collection.created_at, updated_at=collection.updated_at,
    )


def update_collection(
    db: Session, user_id: str, collection_id: str,
    request: FavoriteCollectionUpdateRequest,
) -> FavoriteCollectionData:
    collection = _owned_collection(db, collection_id, user_id)
    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="收藏夹名称不能为空")
        collection.name = name
    if request.description is not None:
        collection.description = request.description.strip()
    if request.color is not None:
        collection.color = request.color
    collection.updated_at = _now()
    db.add(collection)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="已存在同名收藏夹") from exc
    db.refresh(collection)
    return next(
        item for item in list_collections(db, user_id).items
        if item.collection_id == collection.id
    )


def delete_collection(db: Session, user_id: str, collection_id: str) -> None:
    collection = _owned_collection(db, collection_id, user_id)
    links = db.exec(select(KnowledgeCardFavoriteCollectionLink).where(
        KnowledgeCardFavoriteCollectionLink.collection_id == collection_id
    )).all()
    for link in links:
        db.delete(link)
    db.delete(collection)
    db.commit()
