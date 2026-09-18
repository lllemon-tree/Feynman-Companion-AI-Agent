"""Enroll report dimensions in the canonical knowledge-gap review queue."""

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.feynman import DimensionReport
from backend.app.models.knowledge_gap import (
    KnowledgeGap,
    ReportReviewEnrollmentData,
)
from backend.app.services.review_rules import is_mastered, severity_for_score


def _dimensions_for_review(report: DiagnosticReport) -> list[DimensionReport]:
    try:
        dimensions = [
            DimensionReport.model_validate(item)
            for item in json.loads(report.dimensions)
        ]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="诊断报告缺少有效的维度数据") from exc

    if not dimensions:
        raise HTTPException(status_code=409, detail="诊断报告缺少有效的维度数据")

    unmastered = [item for item in dimensions if not is_mastered(item.score)]
    return unmastered or [min(dimensions, key=lambda item: item.score)]


def add_report_to_review_list(
    db: Session,
    user_id: str,
    report_id: str,
    source: str = "manual",
) -> ReportReviewEnrollmentData:
    del source  # The knowledge-gap queue is now the single source of truth.
    report = db.exec(select(DiagnosticReport).where(
        DiagnosticReport.id == report_id,
        DiagnosticReport.user_id == user_id,
    )).first()
    if report is None:
        raise HTTPException(status_code=404, detail="诊断报告不存在")

    selected = _dimensions_for_review(report)
    now = datetime.now(timezone.utc).isoformat()
    statuses: list[str] = []

    for dimension in selected:
        gap = db.exec(select(KnowledgeGap).where(
            KnowledgeGap.user_id == user_id,
            KnowledgeGap.kp_id == report.kp_id,
            KnowledgeGap.dimension == dimension.name,
        ).order_by(KnowledgeGap.created_at.desc())).first()

        if gap is None:
            gap = KnowledgeGap(
                user_id=user_id,
                kp_id=report.kp_id,
                kp_name=report.kp_name,
                material_id=report.material_id,
                material_name=report.material_name,
                dimension=dimension.name,
                score=dimension.score,
                severity=severity_for_score(dimension.score),
                status="open",
                gap_description=dimension.analysis,
                source_session_id=report.session_id,
                next_review_at=now,
            )
        else:
            gap.kp_name = report.kp_name
            gap.material_id = report.material_id
            gap.material_name = report.material_name
            gap.score = dimension.score
            gap.severity = severity_for_score(dimension.score)
            gap.gap_description = dimension.analysis
            gap.source_session_id = report.session_id
            gap.updated_at = now
            if gap.status != "reviewing":
                gap.status = "open"
                gap.next_review_at = now
                gap.resolved_at = None
                gap.resolution_source = None

        statuses.append(gap.status)
        db.add(gap)

    db.commit()
    return ReportReviewEnrollmentData(
        report_id=report.id,
        kp_id=report.kp_id,
        kp_name=report.kp_name,
        status="reviewing" if statuses and all(item == "reviewing" for item in statuses) else "open",
        dimensions=[item.name for item in selected],
    )
