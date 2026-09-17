"""Knowledge-card, study progress, and knowledge-point review contracts."""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeCard(SQLModel, table=True):
    """A stable, cached card for one logical knowledge point."""

    __tablename__ = "knowledge_card"
    __table_args__ = (UniqueConstraint("kp_id", name="uq_knowledge_card_kp"),)

    id: str = Field(primary_key=True)
    kp_id: str = Field(index=True)
    content_json: str
    source_digest: str
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeCardCollection(SQLModel, table=True):
    """A user-defined container for organizing favorite knowledge cards."""

    __tablename__ = "knowledge_card_collection"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_card_collection_user_name"),
    )

    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    description: str = ""
    color: str = "#3b6fe8"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeCardFavorite(SQLModel, table=True):
    """The user's durable relationship with a card, independent from review needs."""

    __tablename__ = "knowledge_card_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_card_favorite_user_card"),
        Index("idx_card_favorite_user_pinned", "user_id", "is_pinned"),
    )

    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    card_id: str = Field(foreign_key="knowledge_card.id", index=True)
    kp_id: str = Field(index=True)
    kp_name: str
    summary: str = ""
    material_id: str
    material_name: str
    material_subject: str = ""
    chapter_id: str
    chapter_name: str
    content_snapshot_json: str
    note: str = ""
    tags_json: str = "[]"
    is_pinned: bool = False
    saved_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeCardFavoriteCollectionLink(SQLModel, table=True):
    __tablename__ = "knowledge_card_favorite_collection_link"
    __table_args__ = (
        UniqueConstraint("favorite_id", "collection_id", name="uq_favorite_collection_link"),
    )

    id: str = Field(primary_key=True)
    favorite_id: str = Field(foreign_key="knowledge_card_favorite.id", index=True)
    collection_id: str = Field(foreign_key="knowledge_card_collection.id", index=True)


class KnowledgeReviewItem(SQLModel, table=True):
    """A knowledge-point-level review entry, separate from dimension gaps."""

    __tablename__ = "knowledge_review_item"
    __table_args__ = (
        UniqueConstraint("user_id", "kp_id", name="uq_review_item_user_kp"),
        Index("idx_review_item_user_status", "user_id", "status"),
    )

    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    kp_id: str = Field(index=True)
    kp_name: str
    material_id: Optional[str] = None
    material_name: Optional[str] = None
    report_id: Optional[str] = Field(default=None, index=True)
    source: str = Field(default="manual")  # manual / automatic
    status: str = Field(default="pending")
    average_score: Optional[float] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


CardSourceType = Literal["textbook", "textbook_rewrite", "model_supplement"]
CardCoverageLevel = Literal["sufficient", "partial", "limited"]
CardGenerationStatus = Literal["generating", "ready", "failed"]


class KnowledgeCardSource(BaseModel):
    chunk_id: str
    page: int
    excerpt: str = ""


class KnowledgeCardSection(BaseModel):
    key: str
    title: str
    content: str = ""
    bullets: list[str] = PydanticField(default_factory=list)
    source_type: CardSourceType
    source_chunk_ids: list[str] = PydanticField(default_factory=list)
    required_for_evaluation: bool = False


class KnowledgeCardContent(BaseModel):
    generation_status: CardGenerationStatus = "ready"
    coverage_level: CardCoverageLevel = "partial"
    coverage_notice: str = ""
    estimated_minutes: int = PydanticField(default=5, ge=1, le=30)
    sections: list[KnowledgeCardSection] = PydanticField(default_factory=list)


class KnowledgeCardData(BaseModel):
    card_id: str
    kp_id: str
    name: str
    summary: str
    learning_status: Literal["unlearned", "learned"]
    version: int
    generation_status: CardGenerationStatus = "ready"
    is_favorited: bool = False
    favorite_id: Optional[str] = None
    coverage_level: CardCoverageLevel
    coverage_notice: str = ""
    estimated_minutes: int
    sections: list[KnowledgeCardSection]
    sources: list[KnowledgeCardSource]
    updated_at: datetime


class KnowledgeCardResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: KnowledgeCardData


class KnowledgeReviewItemData(BaseModel):
    review_item_id: str
    kp_id: str
    kp_name: str
    material_id: Optional[str] = None
    material_name: Optional[str] = None
    report_id: Optional[str] = None
    source: Literal["manual", "automatic"]
    status: str
    average_score: Optional[float] = None
    created_at: datetime


class KnowledgeReviewListData(BaseModel):
    items: list[KnowledgeReviewItemData]
    total: int


class KnowledgeReviewItemResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: KnowledgeReviewItemData


class KnowledgeReviewListResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: KnowledgeReviewListData


class FavoriteCollectionCreateRequest(BaseModel):
    name: str = PydanticField(min_length=1, max_length=30)
    description: str = PydanticField(default="", max_length=120)
    color: str = PydanticField(default="#3b6fe8", pattern=r"^#[0-9a-fA-F]{6}$")


class FavoriteCollectionUpdateRequest(BaseModel):
    name: Optional[str] = PydanticField(default=None, min_length=1, max_length=30)
    description: Optional[str] = PydanticField(default=None, max_length=120)
    color: Optional[str] = PydanticField(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class FavoriteCollectionData(BaseModel):
    collection_id: str
    name: str
    description: str = ""
    color: str
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class FavoriteCollectionResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: FavoriteCollectionData


class FavoriteCollectionListData(BaseModel):
    items: list[FavoriteCollectionData]
    total: int


class FavoriteCollectionListResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: FavoriteCollectionListData


class FavoriteCardCreateRequest(BaseModel):
    card_id: str
    collection_ids: list[str] = PydanticField(default_factory=list)
    note: str = PydanticField(default="", max_length=1000)
    tags: list[str] = PydanticField(default_factory=list, max_length=12)


class FavoriteCardUpdateRequest(BaseModel):
    collection_ids: Optional[list[str]] = None
    note: Optional[str] = PydanticField(default=None, max_length=1000)
    tags: Optional[list[str]] = PydanticField(default=None, max_length=12)
    is_pinned: Optional[bool] = None


class FavoriteCardData(BaseModel):
    favorite_id: str
    card_id: str
    kp_id: str
    kp_name: str
    summary: str
    material_id: str
    material_name: str
    material_subject: str
    chapter_id: str
    chapter_name: str
    card_version: int
    saved_version: int
    has_update: bool
    generation_status: CardGenerationStatus = "ready"
    coverage_level: CardCoverageLevel
    estimated_minutes: int
    sections: list[KnowledgeCardSection]
    note: str = ""
    tags: list[str] = PydanticField(default_factory=list)
    is_pinned: bool = False
    collection_ids: list[str] = PydanticField(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FavoriteCardResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: FavoriteCardData


class FavoriteCardListData(BaseModel):
    items: list[FavoriteCardData]
    total: int
    available_tags: list[str] = PydanticField(default_factory=list)


class FavoriteCardListResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: FavoriteCardListData


class FavoriteStatusData(BaseModel):
    card_id: str
    is_favorited: bool
    favorite_id: Optional[str] = None


class FavoriteStatusResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: FavoriteStatusData
