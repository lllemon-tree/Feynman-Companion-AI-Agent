import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, Sequence
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    MetaData,
    Table,
    func,
    inspect,
    insert,
    select as sa_select,
    update,
)
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from backend.app.models.auth import GUEST_USER_ID
from backend.app.models.diagnostic_report import (
    DiagnosticReport,
    ReportDetailData,
    ReportDimensionScore,
    ReportListData,
    ReportListItem,
)
from backend.app.models.feynman import (
    DimensionReport,
    FeynmanChatData,
    NextAction,
    ReviewPlan,
)
from backend.app.models.knowledge import Material
from backend.app.models.knowledge_gap import KnowledgeGap
from backend.app.models.review_attempt import ReviewAttempt
from backend.app.services.review_rules import is_mastered, next_review_at, severity_for_score
from backend.app.services.review_service import finalize_review
from backend.app.services.session_store import SessionState


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportContext:
    user_id: str
    session_id: str
    kp_id: str
    kp_name: str
    material_id: Optional[str]
    material_name: Optional[str]


class KnowledgeGapWriter(Protocol):
    def sync(
        self,
        engine: Engine,
        context: ReportContext,
        dimensions: Sequence[DimensionReport],
    ) -> int: ...


class ReflectiveKnowledgeGapWriter:
    """Writes gaps once Backend A's knowledge_gap table is available."""

    def sync(
        self,
        engine: Engine,
        context: ReportContext,
        dimensions: Sequence[DimensionReport],
    ) -> int:
        if not inspect(engine).has_table("knowledge_gap"):
            logger.info("knowledge_gap table is not available; gap persistence skipped")
            return 0

        metadata = MetaData()
        gap_table = Table("knowledge_gap", metadata, autoload_with=engine)
        now = datetime.now(timezone.utc)
        timestamp_values = {
            "created_at": _timestamp_for(gap_table.c.created_at, now),
            "updated_at": _timestamp_for(gap_table.c.updated_at, now),
        }

        with Session(engine) as db:
            synced = 0
            for dimension in dimensions:
                existing = db.execute(
                    sa_select(gap_table.c.id, gap_table.c.status).where(
                        gap_table.c.user_id == context.user_id,
                        gap_table.c.kp_id == context.kp_id,
                        gap_table.c.dimension == dimension.name,
                    ).order_by(gap_table.c.created_at.desc())
                ).first()

                values = {
                    "score": dimension.score,
                    "severity": severity_for_score(dimension.score),
                    "gap_description": dimension.analysis,
                    "source_session_id": context.session_id,
                    "material_id": context.material_id,
                    "material_name": context.material_name,
                    "updated_at": timestamp_values["updated_at"],
                }
                if is_mastered(dimension.score):
                    if existing is not None:
                        values["status"] = "resolved"
                        values["next_review_at"] = None
                        if "resolved_at" in gap_table.c:
                            values["resolved_at"] = _timestamp_for(gap_table.c.resolved_at, now)
                        if "resolution_source" in gap_table.c:
                            values["resolution_source"] = "assessment"
                        db.execute(update(gap_table).where(gap_table.c.id == existing.id).values(**values))
                    continue

                if existing is not None:
                    if existing.status == "resolved":
                        values["status"] = "open"
                        values["next_review_at"] = _timestamp_for(
                            gap_table.c.next_review_at, next_review_at(0, now)
                        )
                        if "resolved_at" in gap_table.c:
                            values["resolved_at"] = None
                        if "resolution_source" in gap_table.c:
                            values["resolution_source"] = None
                    db.execute(
                        update(gap_table)
                        .where(gap_table.c.id == existing.id)
                        .values(**values)
                    )
                else:
                    values["next_review_at"] = _timestamp_for(
                        gap_table.c.next_review_at, next_review_at(0, now)
                    )
                    db.execute(
                        insert(gap_table).values(
                            id=f"gap-{uuid4().hex[:12]}",
                            user_id=context.user_id,
                            kp_id=context.kp_id,
                            kp_name=context.kp_name,
                            dimension=dimension.name,
                            status="open",
                            review_count=0,
                            created_at=timestamp_values["created_at"],
                            **values,
                        )
                    )
                synced += 1
            db.commit()
        return synced


class ReportFinalizer(Protocol):
    def finalize(
        self,
        session_state: SessionState,
        response: FeynmanChatData,
    ) -> Optional[DiagnosticReport]: ...


class NullReportFinalizer:
    def finalize(
        self,
        session_state: SessionState,
        response: FeynmanChatData,
    ) -> Optional[DiagnosticReport]:
        return None


class DiagnosticReportFinalizer:
    def __init__(
        self,
        engine: Engine,
        gap_writer: Optional[KnowledgeGapWriter] = None,
    ) -> None:
        self._engine = engine
        self._gap_writer = gap_writer or ReflectiveKnowledgeGapWriter()

    def is_review_session(self, session_state: SessionState) -> bool:
        if not inspect(self._engine).has_table("review_attempt"):
            return False
        with Session(self._engine) as db:
            return db.exec(select(ReviewAttempt).where(
                ReviewAttempt.session_id == session_state.session_id,
                ReviewAttempt.user_id == session_state.user_id,
            )).first() is not None

    def finalize(
        self,
        session_state: SessionState,
        response: FeynmanChatData,
    ) -> Optional[DiagnosticReport]:
        if session_state.user_id == GUEST_USER_ID:
            return None
        if (
            response.next_action != NextAction.GENERATE_REPORT
            or response.final_report is None
            or not session_state.kp_id
            or not session_state.kp_name
        ):
            return None

        material_name = self._get_material_name(session_state.material_id)
        context = ReportContext(
            user_id=session_state.user_id,
            session_id=session_state.session_id,
            kp_id=session_state.kp_id,
            kp_name=session_state.kp_name,
            material_id=session_state.material_id,
            material_name=material_name,
        )
        if self.is_review_session(session_state):
            report = finalize_review(
                self._engine,
                session_state,
                response,
                material_name,
            )
            return report

        with Session(self._engine) as db:
            existing = db.exec(select(DiagnosticReport).where(
                DiagnosticReport.session_id == context.session_id
            )).first()
            if existing is not None:
                return existing
        try:
            gaps_identified = self._gap_writer.sync(
                self._engine,
                context,
                response.final_report.dimensions,
            )
        except Exception:
            gaps_identified = 0
            logger.exception(
                "knowledge gap persistence failed for session %s",
                session_state.session_id,
            )

        report = self._save_report(
            context=context,
            response=response,
            gaps_identified=gaps_identified,
        )
        return report

    def review_list_metadata(self, report: DiagnosticReport) -> tuple[bool, Optional[str]]:
        with Session(self._engine) as db:
            active_gap = db.exec(select(KnowledgeGap).where(
                KnowledgeGap.user_id == report.user_id,
                KnowledgeGap.kp_id == report.kp_id,
                KnowledgeGap.status.in_(["open", "reviewing"]),
            )).first()
        return active_gap is not None, None

    def _get_material_name(self, material_id: Optional[str]) -> Optional[str]:
        if material_id is None:
            return None
        with Session(self._engine) as db:
            material = db.get(Material, material_id)
            if material is None:
                return None
            return material.name or material.filename

    def _save_report(
        self,
        context: ReportContext,
        response: FeynmanChatData,
        gaps_identified: int,
    ) -> DiagnosticReport:
        assert response.final_report is not None
        with Session(self._engine) as db:
            existing = db.exec(
                select(DiagnosticReport).where(
                    DiagnosticReport.session_id == context.session_id
                )
            ).first()
            if existing is not None:
                if gaps_identified > existing.gaps_identified:
                    existing.gaps_identified = gaps_identified
                    db.add(existing)
                    db.commit()
                    db.refresh(existing)
                return existing

            dimensions = response.final_report.dimensions
            report = DiagnosticReport(
                id=f"rpt-{uuid4().hex[:12]}",
                user_id=context.user_id,
                session_id=context.session_id,
                kp_id=context.kp_id,
                kp_name=context.kp_name,
                material_id=context.material_id,
                material_name=context.material_name,
                dimensions=json.dumps(
                    [dimension.model_dump(mode="json") for dimension in dimensions],
                    ensure_ascii=False,
                ),
                total_score=sum(dimension.score for dimension in dimensions),
                overall_comment=response.final_report.overall_comment,
                gaps_identified=gaps_identified,
                review_plan=(
                    json.dumps(
                        response.review_plan.model_dump(mode="json"),
                        ensure_ascii=False,
                    )
                    if response.review_plan is not None
                    else None
                ),
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return report


def list_reports(
    db: Session,
    user_id: str,
    page: int,
    page_size: int,
    kp_id: Optional[str] = None,
) -> ReportListData:
    filters = [DiagnosticReport.user_id == user_id]
    if kp_id:
        filters.append(DiagnosticReport.kp_id == kp_id)
    total = int(
        db.exec(
            select(func.count())
            .select_from(DiagnosticReport)
            .where(*filters)
        ).one()
    )
    records = db.exec(
        select(DiagnosticReport)
        .where(*filters)
        .order_by(DiagnosticReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ReportListData(
        items=[_to_list_item(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_report_detail(
    db: Session,
    user_id: str,
    report_id: str,
) -> Optional[ReportDetailData]:
    record = db.exec(
        select(DiagnosticReport).where(
            DiagnosticReport.id == report_id,
            DiagnosticReport.user_id == user_id,
        )
    ).first()
    if record is None:
        return None
    active_gap = db.exec(select(KnowledgeGap).where(
        KnowledgeGap.user_id == user_id,
        KnowledgeGap.kp_id == record.kp_id,
        KnowledgeGap.status.in_(["open", "reviewing"]),
    )).first()
    return ReportDetailData(
        report_id=record.id,
        kp_id=record.kp_id,
        kp_name=record.kp_name,
        material_name=record.material_name,
        session_id=record.session_id,
        dimensions_full=_parse_dimensions(record.dimensions),
        total_score=record.total_score,
        overall_comment=record.overall_comment,
        gaps_identified=record.gaps_identified,
        review_plan=_parse_review_plan(record.review_plan),
        review_list_added=active_gap is not None,
        review_list_source=None,
        created_at=record.created_at,
    )


def _to_list_item(record: DiagnosticReport) -> ReportListItem:
    dimensions = _parse_dimensions(record.dimensions)
    return ReportListItem(
        report_id=record.id,
        kp_id=record.kp_id,
        kp_name=record.kp_name,
        material_name=record.material_name,
        total_score=record.total_score,
        dimensions=[
            ReportDimensionScore(name=dimension.name, score=dimension.score)
            for dimension in dimensions
        ],
        gaps_identified=record.gaps_identified,
        created_at=record.created_at,
    )


def _parse_dimensions(value: str) -> list[DimensionReport]:
    return [
        DimensionReport.model_validate(item)
        for item in json.loads(value)
    ]


def _parse_review_plan(value: Optional[str]) -> Optional[ReviewPlan]:
    """把数据库里存的 review_plan JSON 字符串解析回 ReviewPlan 对象。"""
    if not value:
        return None
    try:
        return ReviewPlan.model_validate(json.loads(value))
    except Exception:
        # 数据损坏时降级为 None，不影响报告主体返回
        return None


def _timestamp_for(column, value: datetime):
    return value if isinstance(column.type, DateTime) else value.isoformat()
