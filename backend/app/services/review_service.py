"""Persistent review entry, result comparison, and atomic completion."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.feynman import DimensionReport, FeynmanChatData
from backend.app.models.knowledge import LearnSession
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.models.review_attempt import ReviewAttempt
from backend.app.services.review_rules import is_mastered, next_review_at, severity_for_score
from backend.app.services.session_store import SessionState


class NoUnresolvedGapsError(Exception):
    pass


def _target_ids(attempt: ReviewAttempt) -> list[str]:
    return json.loads(attempt.target_gap_ids or "[]")


def _scores(report: DiagnosticReport | None) -> dict[str, int]:
    if report is None:
        return {}
    return {
        item["name"]: item["score"]
        for item in json.loads(report.dimensions or "[]")
        if "name" in item and "score" in item
    }


def _target_payload(db: Session, attempt: ReviewAttempt) -> list[dict]:
    gaps = [db.get(KnowledgeGap, gap_id) for gap_id in _target_ids(attempt)]
    return [
        {
            "gap_id": gap.id,
            "dimension": gap.dimension,
            "score": gap.score,
            "gap_description": gap.gap_description,
            "review_count": gap.review_count,
        }
        for gap in gaps
        if gap is not None and gap.user_id == attempt.user_id and gap.kp_id == attempt.kp_id
    ]


def _ensure_learning_session(
    db: Session,
    attempt: ReviewAttempt,
    representative_gap: KnowledgeGap | None = None,
) -> LearnSession:
    existing = db.get(LearnSession, attempt.session_id)
    if existing is not None:
        return existing
    gap = representative_gap
    if gap is None:
        gap = next(
            (
                candidate
                for gap_id in _target_ids(attempt)
                if (candidate := db.get(KnowledgeGap, gap_id)) is not None
                and candidate.user_id == attempt.user_id
            ),
            None,
        )
    learning_session = LearnSession(
        id=attempt.session_id,
        user_id=attempt.user_id,
        kp_id=attempt.kp_id,
        kp_name=gap.kp_name if gap is not None else attempt.kp_id,
        material_id=gap.material_id if gap is not None else None,
    )
    db.add(learning_session)
    return learning_session


def start_review(db: Session, user_id: str, kp_id: str, source: str) -> dict:
    existing = db.exec(select(ReviewAttempt).where(
        ReviewAttempt.user_id == user_id,
        ReviewAttempt.kp_id == kp_id,
        ReviewAttempt.status == "active",
    )).first()
    if existing is not None:
        _ensure_learning_session(db, existing)
        db.commit()
        return _start_payload(db, existing, resumed=True)

    gaps = db.exec(select(KnowledgeGap).where(
        KnowledgeGap.user_id == user_id,
        KnowledgeGap.kp_id == kp_id,
        KnowledgeGap.status.in_(["open", "reviewing"]),
    ).order_by(KnowledgeGap.created_at, KnowledgeGap.id)).all()
    if not gaps:
        raise NoUnresolvedGapsError("no unresolved gaps")

    baseline = db.exec(select(DiagnosticReport).where(
        DiagnosticReport.user_id == user_id,
        DiagnosticReport.kp_id == kp_id,
    ).order_by(DiagnosticReport.created_at.desc(), DiagnosticReport.id.desc())).first()
    attempt = ReviewAttempt(
        id=f"review-{uuid4().hex[:12]}",
        user_id=user_id,
        session_id=f"session-{uuid4().hex}",
        kp_id=kp_id,
        baseline_report_id=baseline.id if baseline else None,
        target_gap_ids=json.dumps([gap.id for gap in gaps]),
        source=source,
    )
    db.add(attempt)
    _ensure_learning_session(db, attempt, gaps[0])
    for gap in gaps:
        gap.status = "reviewing"
        gap.updated_at = attempt.started_at
        db.add(gap)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.exec(select(ReviewAttempt).where(
            ReviewAttempt.user_id == user_id,
            ReviewAttempt.kp_id == kp_id,
            ReviewAttempt.status == "active",
        )).first()
        if winner is None:
            raise
        _ensure_learning_session(db, winner)
        db.commit()
        return _start_payload(db, winner, resumed=True)
    return _start_payload(db, attempt, resumed=False)


def _start_payload(db: Session, attempt: ReviewAttempt, resumed: bool) -> dict:
    targets = _target_payload(db, attempt)
    return {
        "review_id": attempt.id,
        "session_id": attempt.session_id,
        "kp_id": attempt.kp_id,
        "kp_name": _kp_name(db, attempt),
        "baseline_report_id": attempt.baseline_report_id,
        "status": attempt.status,
        "resumed": resumed,
        "target_gaps": targets,
    }


def _kp_name(db: Session, attempt: ReviewAttempt) -> str:
    for gap_id in _target_ids(attempt):
        gap = db.get(KnowledgeGap, gap_id)
        if gap is not None and gap.user_id == attempt.user_id:
            return gap.kp_name
    baseline = db.get(DiagnosticReport, attempt.baseline_report_id) if attempt.baseline_report_id else None
    return baseline.kp_name if baseline is not None else attempt.kp_id


def get_review_result(db: Session, user_id: str, review_id: str) -> dict | None:
    attempt = db.exec(select(ReviewAttempt).where(
        ReviewAttempt.id == review_id,
        ReviewAttempt.user_id == user_id,
    )).first()
    if attempt is None:
        return None
    result = {
        "review_id": attempt.id,
        "status": attempt.status,
        "session_id": attempt.session_id,
        "kp_id": attempt.kp_id,
        "kp_name": _kp_name(db, attempt),
        "baseline_report_id": attempt.baseline_report_id,
        "result_report_id": attempt.result_report_id,
        "dimension_changes": [],
        "action": "continue" if attempt.status == "active" else "completed",
    }
    if attempt.status != "completed" or not attempt.result_report_id:
        return result
    if attempt.result_snapshot:
        result["dimension_changes"] = json.loads(attempt.result_snapshot)
        return result

    baseline = db.get(DiagnosticReport, attempt.baseline_report_id) if attempt.baseline_report_id else None
    current = db.get(DiagnosticReport, attempt.result_report_id)
    if current is None or current.user_id != user_id:
        return result
    previous_scores = _scores(baseline) if baseline is None or baseline.user_id == user_id else {}
    target_gaps = [db.get(KnowledgeGap, gap_id) for gap_id in _target_ids(attempt)]
    by_dimension = {
        gap.dimension: gap
        for gap in target_gaps
        if gap is not None and gap.user_id == user_id and gap.kp_id == attempt.kp_id
    }
    for dimension, score in _scores(current).items():
        gap = by_dimension.get(dimension)
        previous = previous_scores.get(dimension)
        result["dimension_changes"].append({
            "dimension": dimension,
            "previous_score": previous,
            "current_score": score,
            "delta": score - previous if previous is not None else None,
            "result": ("mastered" if is_mastered(score) else "continue") if gap else "unchanged",
            "gap_id": gap.id if gap else None,
            "gap_status": gap.status if gap else None,
            "review_count": gap.review_count if gap else None,
            "next_review_at": gap.next_review_at if gap else None,
        })
    return result


def get_review_stats(db: Session, user_id: str) -> dict:
    """Summarize completed reviews per knowledge point without mixing users."""
    attempts = db.exec(select(ReviewAttempt).where(
        ReviewAttempt.user_id == user_id,
        ReviewAttempt.status == "completed",
    ).order_by(ReviewAttempt.completed_at.desc())).all()
    by_kp: dict[str, dict] = {}
    deltas: dict[str, list[int]] = {}
    for attempt in attempts:
        entry = by_kp.setdefault(attempt.kp_id, {
            "kp_id": attempt.kp_id,
            "kp_name": _kp_name(db, attempt),
            "completed_reviews": 0,
            "avg_dimension_delta": None,
            "manual_resolved": 0,
            "assessment_resolved": 0,
            "latest_review": None,
        })
        changes = json.loads(attempt.result_snapshot or "[]")
        entry["completed_reviews"] += 1
        deltas.setdefault(attempt.kp_id, []).extend(
            item["delta"] for item in changes if item.get("delta") is not None
        )
        if entry["latest_review"] is None:
            entry["latest_review"] = {
                "review_id": attempt.id,
                "completed_at": attempt.completed_at,
                "result_report_id": attempt.result_report_id,
                "mastered": sum(item.get("result") == "mastered" for item in changes),
                "continue": sum(item.get("result") == "continue" for item in changes),
            }
    gaps = db.exec(select(KnowledgeGap).where(
        KnowledgeGap.user_id == user_id,
        KnowledgeGap.status == "resolved",
    )).all()
    for gap in gaps:
        entry = by_kp.setdefault(gap.kp_id, {
            "kp_id": gap.kp_id,
            "kp_name": gap.kp_name,
            "completed_reviews": 0,
            "avg_dimension_delta": None,
            "manual_resolved": 0,
            "assessment_resolved": 0,
            "latest_review": None,
        })
        if gap.resolution_source == "manual":
            entry["manual_resolved"] += 1
        elif gap.resolution_source == "assessment":
            entry["assessment_resolved"] += 1
    for kp_id, entry in by_kp.items():
        values = deltas.get(kp_id, [])
        if values:
            entry["avg_dimension_delta"] = round(sum(values) / len(values), 1)
    return {"items": list(by_kp.values()), "total": len(by_kp)}


def finalize_review(
    engine,
    state: SessionState,
    response: FeynmanChatData,
    material_name: str | None,
) -> DiagnosticReport | None:
    """Commit report, attempt and all affected gaps as one unit of work."""
    if not inspect(engine).has_table("review_attempt"):
        return None
    assert response.final_report is not None
    with Session(engine) as db:
        attempt = db.exec(select(ReviewAttempt).where(
            ReviewAttempt.session_id == state.session_id,
            ReviewAttempt.user_id == state.user_id,
        )).first()
        if attempt is None:
            return None
        if attempt.status == "completed":
            return db.get(DiagnosticReport, attempt.result_report_id) if attempt.result_report_id else None
        if attempt.kp_id != state.kp_id:
            raise ValueError("review session is bound to another knowledge point")

        dimensions = response.final_report.dimensions
        by_name: dict[str, DimensionReport] = {item.name: item for item in dimensions}
        baseline = db.get(DiagnosticReport, attempt.baseline_report_id) if attempt.baseline_report_id else None
        previous_scores = _scores(baseline) if baseline is None or baseline.user_id == state.user_id else {}
        target_ids = _target_ids(attempt)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        report = DiagnosticReport(
            id=f"rpt-{uuid4().hex[:12]}",
            user_id=state.user_id,
            session_id=state.session_id,
            kp_id=state.kp_id,
            kp_name=state.kp_name or attempt.kp_id,
            material_id=state.material_id,
            material_name=material_name,
            dimensions=json.dumps([item.model_dump(mode="json") for item in dimensions], ensure_ascii=False),
            total_score=sum(item.score for item in dimensions),
            overall_comment=response.final_report.overall_comment,
            gaps_identified=sum(not is_mastered(item.score) for item in dimensions),
            review_plan=response.review_plan.model_dump_json() if response.review_plan else None,
            review_attempt_id=attempt.id,
        )
        db.add(report)

        targeted_dimensions: set[str] = set()
        targeted_gaps: dict[str, KnowledgeGap] = {}
        for gap_id in target_ids:
            gap = db.get(KnowledgeGap, gap_id)
            if gap is None or gap.user_id != state.user_id or gap.kp_id != attempt.kp_id:
                raise ValueError("review target gap is missing or inaccessible")
            dimension = by_name.get(gap.dimension)
            if dimension is None:
                raise ValueError("review report lacks a target dimension")
            targeted_dimensions.add(gap.dimension)
            targeted_gaps[gap.dimension] = gap
            gap.score = dimension.score
            gap.severity = severity_for_score(dimension.score)
            gap.gap_description = dimension.analysis
            gap.source_session_id = state.session_id
            gap.review_count += 1
            gap.last_reviewed_at = now_iso
            gap.updated_at = now_iso
            if is_mastered(dimension.score):
                gap.status = "resolved"
                gap.resolved_at = now_iso
                gap.resolution_source = "assessment"
                gap.next_review_at = None
            else:
                gap.status = "reviewing"
                gap.resolved_at = None
                gap.resolution_source = None
                gap.next_review_at = next_review_at(gap.review_count, now).isoformat()
            db.add(gap)

        for dimension in dimensions:
            if dimension.name in targeted_dimensions or is_mastered(dimension.score):
                continue
            existing = db.exec(select(KnowledgeGap).where(
                KnowledgeGap.user_id == state.user_id,
                KnowledgeGap.kp_id == attempt.kp_id,
                KnowledgeGap.dimension == dimension.name,
            ).order_by(KnowledgeGap.created_at.desc())).first()
            if existing is None:
                existing = KnowledgeGap(
                    user_id=state.user_id,
                    kp_id=attempt.kp_id,
                    kp_name=state.kp_name or attempt.kp_id,
                    material_id=state.material_id,
                    material_name=material_name,
                    dimension=dimension.name,
                    score=dimension.score,
                    gap_description=dimension.analysis,
                    severity=severity_for_score(dimension.score),
                    status="open",
                    next_review_at=next_review_at(0, now).isoformat(),
                    source_session_id=state.session_id,
                )
            else:
                existing.score = dimension.score
                existing.gap_description = dimension.analysis
                existing.severity = severity_for_score(dimension.score)
                existing.status = "open"
                existing.resolved_at = None
                existing.resolution_source = None
                existing.next_review_at = next_review_at(0, now).isoformat()
                existing.source_session_id = state.session_id
                existing.updated_at = now_iso
            db.add(existing)

        attempt.status = "completed"
        attempt.result_report_id = report.id
        attempt.result_snapshot = json.dumps([
            {
                "dimension": dimension.name,
                "previous_score": previous_scores.get(dimension.name),
                "current_score": dimension.score,
                "delta": (
                    dimension.score - previous_scores[dimension.name]
                    if dimension.name in previous_scores else None
                ),
                "result": (
                    "mastered" if is_mastered(dimension.score) else "continue"
                ) if dimension.name in targeted_gaps else "unchanged",
                "gap_id": targeted_gaps[dimension.name].id if dimension.name in targeted_gaps else None,
                "gap_status": targeted_gaps[dimension.name].status if dimension.name in targeted_gaps else None,
                "review_count": targeted_gaps[dimension.name].review_count if dimension.name in targeted_gaps else None,
                "next_review_at": targeted_gaps[dimension.name].next_review_at if dimension.name in targeted_gaps else None,
            }
            for dimension in dimensions
        ], ensure_ascii=False)
        attempt.completed_at = now_iso
        db.add(attempt)
        db.commit()
        db.refresh(report)
        return report
