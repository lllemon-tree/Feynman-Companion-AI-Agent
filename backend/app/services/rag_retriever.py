import asyncio
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


class ChromaRAGRetriever:
    """ChromaDB-backed semantic retrieval for LangGraph RAG node."""

    async def retrieve(
        self,
        query: str,
        material_id: str,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        # BGE 编码和 Chroma 查询都是同步重活，放到工作线程避免卡住其他对话的事件循环。
        def search_material():
            from backend.app.services.vector_store import vector_store
            return vector_store.search(material_id=material_id, query=query, top_k=top_k)

        raw = await asyncio.to_thread(search_material)
        return [
            RetrievedChunk(
                chunk_id=item["chunk_id"],
                page_no=item["page_no"],
                text=item["text"],
                source="rag",
                score=item.get("score"),
            )
            for item in raw
        ]


@lru_cache
def get_rag_retriever() -> RAGRetriever:
    return ChromaRAGRetriever()
