import json
from copy import deepcopy
from typing import Any, Dict, Optional, Protocol

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from backend.app.core.database import engine
from backend.app.models.knowledge import Chapter, Chunk, KP
from backend.app.models.rag import RetrievedChunk
from backend.app.services.knowledge_base import DIJKSTRA_GROUND_TRUTH


DEFAULT_KP_ID = "kp-demo"


class KnowledgePoint(BaseModel):
    kp_id: str
    name: str
    summary: str
    rubric: Dict[str, Any]
    material_id: str
    chapter_id: str
    source_chunks: list[RetrievedChunk] = Field(default_factory=list)


class KnowledgePointProvider(Protocol):
    def get(self, kp_id: str) -> Optional[KnowledgePoint]:
        ...


class MockKnowledgePointProvider:
    """Demo knowledge points used when the database has no matching item."""

    def __init__(self) -> None:
        self._items = {
            DEFAULT_KP_ID: KnowledgePoint(
                kp_id=DEFAULT_KP_ID,
                name="Dijkstra 算法",
                summary="非负权图求单源最短路径的贪心算法",
                rubric=deepcopy(DIJKSTRA_GROUND_TRUTH["ground_truth"]),
                material_id="mat-demo",
                chapter_id="ch-demo",
            ),
            "kp-demo2": KnowledgePoint(
                kp_id="kp-demo2",
                name="Floyd 算法",
                summary="通过动态规划求解全源最短路径",
                rubric={
                    "concept_prerequisite": {
                        "name": "概念前提",
                        "content": "Floyd 算法用于求所有顶点对之间的最短路径，允许负权边，但不能存在负权环。",
                    },
                    "core_mechanism": {
                        "name": "核心机制",
                        "content": "动态规划状态表示只允许经过前 k 个顶点时两点间的最短距离，并逐步扩大中间点集合。",
                    },
                    "principle_proof": {
                        "name": "原理证明",
                        "content": "最短路径要么不经过第 k 个顶点，要么可拆成经过 k 的两段最短路径。",
                    },
                    "common_misunderstandings": {
                        "name": "常见误区",
                        "content": [
                            "误以为 Floyd 不能处理任何负权边",
                            "混淆中间点和路径端点",
                            "原地更新时写错三层循环中 k 的位置",
                            "忽略负权环会使最短路径无定义",
                        ],
                    },
                },
                material_id="mat-demo",
                chapter_id="ch-demo",
            ),
        }

    def get(self, kp_id: str) -> Optional[KnowledgePoint]:
        item = self._items.get(kp_id)
        return item.model_copy(deep=True) if item is not None else None


class SQLiteKnowledgePointProvider:
    def __init__(self, db_engine: Engine = engine) -> None:
        self._engine = db_engine

    def get(self, kp_id: str) -> Optional[KnowledgePoint]:
        try:
            with Session(self._engine) as session:
                kp = session.get(KP, kp_id)
                if kp is None or kp.status != "done" or not kp.rubric:
                    return None

                chapter = session.get(Chapter, kp.chapter_id)
                if chapter is None:
                    return None

                try:
                    rubric = json.loads(kp.rubric)
                except (json.JSONDecodeError, TypeError):
                    return None
                if not isinstance(rubric, dict):
                    return None

                chunks = session.exec(
                    select(Chunk)
                    .where(Chunk.material_id == chapter.material_id)
                    .where(Chunk.page_no >= kp.page_start)
                    .where(Chunk.page_no <= kp.page_end)
                    .order_by(Chunk.page_no, Chunk.seq)
                ).all()
                return KnowledgePoint(
                    kp_id=kp.id,
                    name=kp.name,
                    summary=kp.summary or "暂无摘要",
                    rubric=normalize_rubric(rubric),
                    material_id=chapter.material_id,
                    chapter_id=chapter.id,
                    source_chunks=[
                        RetrievedChunk(
                            chunk_id=chunk.id,
                            page_no=chunk.page_no,
                            text=chunk.text,
                            source="fixed",
                        )
                        for chunk in chunks
                    ],
                )
        except OperationalError:
            # The app lifespan creates tables. Before startup, demo data can still work.
            return None


class FallbackKnowledgePointProvider:
    def __init__(
        self,
        primary: KnowledgePointProvider,
        fallback: KnowledgePointProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    def get(self, kp_id: str) -> Optional[KnowledgePoint]:
        return self._primary.get(kp_id) or self._fallback.get(kp_id)


def normalize_rubric(rubric: Dict[str, Any]) -> Dict[str, Any]:
    labels = {
        "concept_prerequisite": "概念前提",
        "core_mechanism": "核心机制",
        "principle_proof": "原理证明",
        "common_misunderstandings": "常见误区",
    }
    normalized: Dict[str, Any] = {}
    for key, label in labels.items():
        value = rubric.get(key, "暂无说明")
        if isinstance(value, dict) and "content" in value:
            normalized[key] = value
        else:
            normalized[key] = {"name": label, "content": value}
    return normalized


kp_provider = FallbackKnowledgePointProvider(
    primary=SQLiteKnowledgePointProvider(),
    fallback=MockKnowledgePointProvider(),
)
