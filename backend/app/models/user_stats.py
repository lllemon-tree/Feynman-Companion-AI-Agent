from typing import Optional

from pydantic import BaseModel, Field


class ScoreTrendItem(BaseModel):
    date: str
    total_score: float = Field(ge=0, le=40)


class UserStatsData(BaseModel):
    total_kps_learned: int = Field(ge=0)
    total_sessions: int = Field(ge=0)
    avg_total_score: float = Field(ge=0, le=40)
    dimension_avg: dict[str, float]
    weakest_dimension: Optional[str] = None
    recent_trend: list[ScoreTrendItem]


class UserStatsResponse(BaseModel):
    code: int
    msg: str
    data: UserStatsData
