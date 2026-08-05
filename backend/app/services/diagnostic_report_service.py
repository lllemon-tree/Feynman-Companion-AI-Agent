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
                existing_id = db.execute(
                    sa_select(gap_table.c.id).where(
                        gap_table.c.user_id == context.user_id,
                        gap_table.c.kp_id == context.kp_id,
                        gap_table.c.dimension == dimension.name,
                        gap_table.c.status == "open",
                    )
                ).scalar_one_or_none()

                values = {
                    "score": dimension.score,
                    "severity": severity_for_score(dimension.score),
                    "gap_description": dimension.analysis,
                    "source_session_id": context.session_id,
                    "material_id": context.material_id,
                    "material_name": context.material_name,
                    "updated_at": timestamp_values["updated_at"],
                }
                if existing_id is not None:
                    db.execute(
                        update(gap_table)
                        .where(gap_table.c.id == existing_id)
                        .values(**values)
                    )
                else:
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
        low_score_dimensions = [
            dimension
            for dimension in response.final_report.dimensions
            if dimension.score <= 6
        ]

        try:
            gaps_identified = self._gap_writer.sync(
                self._engine,
                context,
                low_score_dimensions,
            )
        except Exception:
            gaps_identified = 0
            logger.exception(
                "knowledge gap persistence failed for session %s",
                session_state.session_id,
            )

        return self._save_report(
            context=context,
            response=response,
            gaps_identified=gaps_identified,
        )

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


def severity_for_score(score: int) -> int:
    if score <= 3:
        return 5
    if score <= 5:
        return 4
    return 3


def list_reports(
    db: Session,
    user_id: str,
    page: int,
    page_size: int,
) -> ReportListData:
    total = int(
        db.exec(
            select(func.count())
            .select_from(DiagnosticReport)
            .where(DiagnosticReport.user_id == user_id)
        ).one()
    )
    records = db.exec(
        select(DiagnosticReport)
        .where(DiagnosticReport.user_id == user_id)
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
