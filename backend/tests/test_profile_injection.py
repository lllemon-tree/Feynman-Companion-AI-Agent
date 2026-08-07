# coding: utf-8
"""
后端 A —— profile 注入链路测试
===============================
测试目标：验证修复后的断点 —— 学情画像从 profile_provider
一路传到 LLM 的 evaluate 参数里，而不是永远为 None。
"""
import unittest

from backend.app.models.feynman import FeynmanChatRequest
from backend.app.models.user_profile import UserProfileResponse
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.session_store import InMemorySessionStore


class EmptyRAGRetriever:
    """假的 RAG 检索器：永远返回空结果。

    单元测试要隔离外部依赖（向量库/embedding 模型），
    我们只测 profile 注入链路，不关心 RAG，所以用假检索器。
    """

    async def retrieve(self, query, material_id, top_k=3):
        return []


class ProfileRecordingLLM(MockLLMClient):
    """一个特殊的假 LLM：记录每次 evaluate 收到的 profile 参数。

    继承 MockLLMClient（保留原有的对话逻辑），
    额外把 profile 存进 received_profiles 列表，方便测试断言。
    """

    def __init__(self):
        super().__init__()
        self.received_profiles = []

    async def evaluate(self, **kwargs):
        self.received_profiles.append(kwargs.get("profile"))
        return await super().evaluate(**kwargs)


class ProfileInjectionTest(unittest.IsolatedAsyncioTestCase):
    async def test_profile_reaches_llm_evaluate(self):
        # Arrange（准备）：一个假画像 + 一个假的画像供应商 + 记录型 LLM
        profile = UserProfileResponse(
            user_id="user-001",
            pain_points=["输出薄弱"],
            created_at="2026-08-03T00:00:00",
            updated_at="2026-08-03T00:00:00",
        )
        recording_llm = ProfileRecordingLLM()

        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=recording_llm,
            fallback_client=MockLLMClient(),
            rag_retriever=EmptyRAGRetriever(),       # 隔离外部依赖
            profile_provider=lambda user_id: profile,  # 供应商：返回假画像
        )

        # Act（执行）：发起一次正常对话（会走 evaluate 节点）
        await service.chat(
            FeynmanChatRequest(
                session_id="s1",
                user_input="Dijkstra 算法每次选未访问节点里距离最小的那个",
            )
        )

        # Assert（断言）：
        # 1. evaluate 至少被调用了一次
        self.assertTrue(len(recording_llm.received_profiles) >= 1)
        # 2. evaluate 收到的 profile 不是 None（断点修复的核心）
        self.assertIsNotNone(recording_llm.received_profiles[0])
        # 3. 收到的画像确实是那个"输出薄弱"的用户
        self.assertEqual(recording_llm.received_profiles[0].pain_points, ["输出薄弱"])

    async def test_no_profile_provider_uses_none(self):
        """不传 profile_provider 时，evaluate 收到 None（安全降级），且不报错。"""
        recording_llm = ProfileRecordingLLM()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=recording_llm,
            fallback_client=MockLLMClient(),
            rag_retriever=EmptyRAGRetriever(),
            profile_provider=None,  # 没有供应商 → 应该是 None
        )
        await service.chat(
            FeynmanChatRequest(
                session_id="s2",
                user_input="Dijkstra 算法每次选未访问节点里距离最小的那个",
            )
        )
        self.assertTrue(len(recording_llm.received_profiles) >= 1)
        self.assertIsNone(recording_llm.received_profiles[0])


if __name__ == "__main__":
    unittest.main()
