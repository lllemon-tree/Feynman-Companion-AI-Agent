"""A durable, user-scoped attempt connecting one review chat to its reports."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel


class ReviewAttempt(SQLModel, table=True):
    __tablename__ = "review_attempt"
    __table_args__ = (
        Index("idx_review_user", "user_id"),
        Index("idx_review_kp", "user_id", "kp_id"),
        Index(
            "uq_review_active_user_kp",
            "user_id",
            "kp_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    session_id: str = Field(unique=True, index=True)
    kp_id: str
    baseline_report_id: Optional[str] = None
    target_gap_ids: str = Field(default="[]")
    source: str
    status: str = Field(default="active")
    result_report_id: Optional[str] = None
    result_snapshot: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
