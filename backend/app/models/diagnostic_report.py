from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from backend.app.models.feynman import DimensionReport


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosticReport(SQLModel, table=True):
    __tablename__ = "diagnostic_report"
    __table_args__ = (
        Index("idx_report_user", "user_id"),
        Index("idx_report_user_date", "user_id", "created_at"),
        UniqueConstraint("session_id", name="uq_report_session"),
    )

    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    session_id: Optional[str] = None
    kp_id: str
    kp_name: str
    material_id: Optional[str] = None
    material_name: Optional[str] = None
    dimensions: str
    total_score: int = Field(ge=0, le=40)
    overall_comment: Optional[str] = None
    gaps_identified: int = Field(default=0, ge=0, le=4)
    created_at: datetime = Field(default_factory=utc_now)


class ReportDimensionScore(BaseModel):
    name: str
    score: int = PydanticField(ge=0, le=10)


class ReportListItem(BaseModel):
    report_id: str
    kp_id: str
    kp_name: str
    material_name: Optional[str] = None
    total_score: int = PydanticField(ge=0, le=40)
    dimensions: list[ReportDimensionScore]
    gaps_identified: int = PydanticField(ge=0, le=4)
    created_at: datetime


class ReportListData(BaseModel):
    items: list[ReportListItem]
    total: int = PydanticField(ge=0)
    page: int = PydanticField(ge=1)
    page_size: int = PydanticField(ge=1)


class ReportDetailData(BaseModel):
    report_id: str
    kp_id: str
    kp_name: str
    material_name: Optional[str] = None
    session_id: Optional[str] = None
    dimensions_full: list[DimensionReport]
    total_score: int = PydanticField(ge=0, le=40)
    overall_comment: Optional[str] = None
    gaps_identified: int = PydanticField(ge=0, le=4)
    created_at: datetime


class ReportListResponse(BaseModel):
    code: int
    msg: str
    data: ReportListData


class ReportDetailResponse(BaseModel):
    code: int
    msg: str
    data: ReportDetailData
