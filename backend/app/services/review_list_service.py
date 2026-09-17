"""Knowledge-point-level review list, independent from dimension gap records."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.learning import (
    KnowledgeReviewItem,
    KnowledgeReviewItemData,
    KnowledgeReviewListData,
)


AUTO_REVIEW_AVERAGE_THRESHOLD = 6.0


def _to_data(item: KnowledgeReviewItem) -> KnowledgeReviewItemData:
    return KnowledgeReviewItemData(
        review_item_id=item.id,
        kp_id=item.kp_id,
        kp_name=item.kp_name,
        material_id=item.material_id,
        material_name=item.material_name,
        report_id=item.report_id,
        source=item.source,
        status=item.status,
        average_score=item.average_score,
        created_at=item.created_at,
    )


def add_report_to_review_list(
    db: Session,
    user_id: str,
    report_id: str,
    source: str = "manual",
) -> KnowledgeReviewItemData:
    report = db.exec(select(DiagnosticReport).where(
        DiagnosticReport.id == report_id,
        DiagnosticReport.user_id == user_id,
    )).first()
    if report is None:
        raise HTTPException(status_code=404, detail="诊断报告不存在")
    return upsert_review_item(db, report, source)


def upsert_review_item(
    db: Session,
    report: DiagnosticReport,
    source: str,
) -> KnowledgeReviewItemData:
    existing = db.exec(select(KnowledgeReviewItem).where(
        KnowledgeReviewItem.user_id == report.user_id,
        KnowledgeReviewItem.kp_id == report.kp_id,
    )).first()
    average = round(report.total_score / 4, 1)
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = KnowledgeReviewItem(
            id=f"review-item-{uuid4().hex[:12]}",
            user_id=report.user_id,
            kp_id=report.kp_id,
            kp_name=report.kp_name,
            material_id=report.material_id,
            material_name=report.material_name,
            report_id=report.id,
            source="automatic" if source == "automatic" else "manual",
            status="pending",
            average_score=average,
        )
    else:
        existing.report_id = report.id
        existing.average_score = average
        existing.kp_name = report.kp_name
        existing.material_id = report.material_id
        existing.material_name = report.material_name
        existing.status = "pending"
        existing.updated_at = now
    db.add(existing)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.exec(select(KnowledgeReviewItem).where(
            KnowledgeReviewItem.user_id == report.user_id,
            KnowledgeReviewItem.kp_id == report.kp_id,
        )).first()
        if winner is None:
            raise
        return _to_data(winner)
    db.refresh(existing)
    return _to_data(existing)


def maybe_auto_add_report(
    db: Session, report: DiagnosticReport
) -> KnowledgeReviewItemData | None:
    if report.total_score / 4 >= AUTO_REVIEW_AVERAGE_THRESHOLD:
        return None
    return upsert_review_item(db, report, "automatic")


def get_review_item_for_kp(
    db: Session, user_id: str, kp_id: str
) -> KnowledgeReviewItemData | None:
    item = db.exec(select(KnowledgeReviewItem).where(
        KnowledgeReviewItem.user_id == user_id,
        KnowledgeReviewItem.kp_id == kp_id,
    )).first()
    return _to_data(item) if item else None


def list_review_items(db: Session, user_id: str) -> KnowledgeReviewListData:
    items = db.exec(select(KnowledgeReviewItem).where(
        KnowledgeReviewItem.user_id == user_id,
        KnowledgeReviewItem.status == "pending",
    ).order_by(KnowledgeReviewItem.updated_at.desc())).all()
    return KnowledgeReviewListData(items=[_to_data(item) for item in items], total=len(items))
