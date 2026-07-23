import unittest

from backend.app.models.feynman import FeynmanChatRequest, NextAction
from backend.app.models.rag import RetrievedChunk
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.prompts import build_system_prompt
from backend.app.services.session_store import InMemorySessionStore


class RecordingRetriever:
    def __init__(self, chunks=None, should_fail=False):
        self.chunks = chunks or []
        self.should_fail = should_fail
        self.calls = []

    async def retrieve(self, query: str, material_id: str, top_k: int = 3):
        self.calls.append(
            {"query": query, "material_id": material_id, "top_k": top_k}
        )
        if self.should_fail:
            raise RuntimeError("vector store is not ready")
        return self.chunks


class RecordingLLMClient:
    def __init__(self):
        self.grounding_chunks = []
        self._delegate = MockLLMClient()

    async def evaluate(self, **kwargs):
        self.grounding_chunks = kwargs["grounding_chunks"]
        return await self._delegate.evaluate(**kwargs)


class RAGGraphTest(unittest.IsolatedAsyncioTestCase):
    async def test_evaluate_retrieves_current_material_top_three(self):
        retriever = RecordingRetriever(
            [
                RetrievedChunk(
                    chunk_id="rag-1",
                    page_no=8,
                    text="Dijkstra 要求边权非负。",
                    source="rag",
                    score=0.91,
                )
            ]
        )
        llm = RecordingLLMClient()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=llm,
            fallback_client=MockLLMClient(),
            rag_retriever=retriever,
        )

        response = await service.chat(
            FeynmanChatRequest(
                session_id="rag-evaluate",
                user_input="Dijkstra 用于求单源最短路径",
            )
        )

        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertEqual(
            retriever.calls,
            [
                {
                    "query": "Dijkstra 用于求单源最短路径",
                    "material_id": "mat-demo",
                    "top_k": 3,
                }
            ],
        )
        self.assertEqual([chunk.chunk_id for chunk in llm.grounding_chunks], ["rag-1"])

    async def test_rule_branch_does_not_call_retriever(self):
        retriever = RecordingRetriever()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
            rag_retriever=retriever,
        )

        await service.chat(
            FeynmanChatRequest(
                session_id="rag-off-topic",
                user_input="今天天气怎么样",
            )
        )

        self.assertEqual(retriever.calls, [])

    async def test_retrieval_failure_does_not_interrupt_chat(self):
        retriever = RecordingRetriever(should_fail=True)
        llm = RecordingLLMClient()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=llm,
            fallback_client=MockLLMClient(),
            rag_retriever=retriever,
        )

        response = await service.chat(
            FeynmanChatRequest(
                session_id="rag-failure",
                user_input="Dijkstra 用于求单源最短路径",
            )
        )

        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertEqual(llm.grounding_chunks, [])

    def test_prompt_distinguishes_fixed_and_rag_sources(self):
        prompt = build_system_prompt(
            kp_name="Dijkstra 算法",
            rubric={},
            grounding_chunks=[
                RetrievedChunk(
                    chunk_id="fixed-1",
                    page_no=2,
                    text="固定页码内容",
                    source="fixed",
                ),
                RetrievedChunk(
                    chunk_id="rag-1",
                    page_no=9,
                    text="跨章节召回内容",
                    source="rag",
                ),
            ],
        )

        self.assertIn("[第2页 / fixed-1]", prompt)
        self.assertIn("固定页码内容", prompt)
        self.assertIn("[第9页 / rag-1]", prompt)
        self.assertIn("跨章节召回内容", prompt)
