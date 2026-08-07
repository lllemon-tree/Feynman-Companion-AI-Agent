import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from backend.app.models.diagnostic_report import DiagnosticReport
from backend.app.models.user_stats import ScoreTrendItem, UserStatsData


DIMENSION_NAMES = (
    "理解深度",
    "表达完整性",
    "逻辑连贯性",
    "结构化能力",
)
RECENT_TREND_DAYS = 7


def get_user_learning_stats(db: Session, user_id: str) -> UserStatsData:
    records = db.exec(
        select(DiagnosticReport)
        .where(DiagnosticReport.user_id == user_id)
        .order_by(DiagnosticReport.created_at.asc())
    ).all()

    if not records:
        return _empty_stats()

    dimension_totals = {name: 0.0 for name in DIMENSION_NAMES}
    dimension_counts = {name: 0 for name in DIMENSION_NAMES}
    daily_scores: dict[str, list[float]] = defaultdict(list)

    for record in records:
        for item in _safe_dimension_items(record.dimensions):
            name = item.get("name")
            score = item.get("score")
            if name not in dimension_totals or not isinstance(score, (int, float)):
                continue
            dimension_totals[name] += float(score)
            dimension_counts[name] += 1

        daily_scores[_date_key(record.created_at)].append(float(record.total_score))

    dimension_avg = {
        name: (
            round(dimension_totals[name] / dimension_counts[name], 1)
            if dimension_counts[name]
            else 0.0
        )
        for name in DIMENSION_NAMES
    }
    observed_dimensions = [
        name for name in DIMENSION_NAMES if dimension_counts[name] > 0
    ]
    weakest_dimension = (
        min(observed_dimensions, key=lambda name: dimension_avg[name])
        if observed_dimensions
        else None
    )

    recent_dates = sorted(daily_scores)[-RECENT_TREND_DAYS:]
    recent_trend = [
        ScoreTrendItem(
            date=date,
            total_score=round(
                sum(daily_scores[date]) / len(daily_scores[date]),
                1,
            ),
        )
        for date in recent_dates
    ]

    return UserStatsData(
        total_kps_learned=len({record.kp_id for record in records}),
        total_sessions=len(records),
        avg_total_score=round(
            sum(record.total_score for record in records) / len(records),
            1,
        ),
        dimension_avg=dimension_avg,
        weakest_dimension=weakest_dimension,
        recent_trend=recent_trend,
    )


def _empty_stats() -> UserStatsData:
    return UserStatsData(
        total_kps_learned=0,
        total_sessions=0,
        avg_total_score=0.0,
        dimension_avg={name: 0.0 for name in DIMENSION_NAMES},
        weakest_dimension=None,
        recent_trend=[],
    )


def _safe_dimension_items(raw_dimensions: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw_dimensions)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _date_key(value: datetime) -> str:
    return value.date().isoformat()
