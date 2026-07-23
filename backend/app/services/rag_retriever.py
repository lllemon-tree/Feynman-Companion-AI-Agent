from functools import lru_cache
from typing import Protocol

from backend.app.models.rag import RetrievedChunk


class RAGRetriever(Protocol):
    async def retrieve(
        self,
        query: str,
        material_id: str,
        top_k: int = 3,
    ) -> list[RetrievedChunk]: ...


class NullRAGRetriever:
    """Fallback used while a material has no vector collection yet."""

    async def retrieve(
        self,
        query: str,
        material_id: str,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        return []


@lru_cache
def get_rag_retriever() -> RAGRetriever:
    # Backend A can replace this factory with the Chroma-backed implementation.
    return NullRAGRetriever()
