# coding: utf-8
"""
后端 A —— mock_llm 痛点 + review_plan 修复测试
==============================================
测试目标：
  1. _build_mock_review_plan 纯函数：低分维度（<=6）进入 reread_guide，高分不进
  2. 多轮对话到报告后，review_plan 非 None（验证修复生效）
  3. 画像含「输出薄弱」→ 追问话术带引导语；无画像 → 不带
"""
import unittest

from backend.app.models.feynman import (
    DimensionReport,
    FeynmanChatRequest,
    NextAction,
)
from backend.app.models.user_profile import UserProfileResponse
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient, _build_mock_review_plan
from backend.app.services.session_store import InMemorySessionStore


class EmptyRAGRetriever:
    """假的 RAG 检索器：隔离外部依赖（向量库/embedding 模型）。"""

    async def retrieve(self, query, material_id, top_k=3):
        return []


def _make_profile(pain_points=None):
    return UserProfileResponse(
        user_id="user-001",
        pain_points=pain_points,
        created_at="2026-08-03T00:00:00",
        updated_at="2026-08-03T00:00:00",
    )


def _make_service(profile):
    return FeynmanService(
        store=InMemorySessionStore(),
        llm_client=MockLLMClient(),
        fallback_client=MockLLMClient(),
        rag_retriever=EmptyRAGRetriever(),
        profile_provider=lambda user_id: profile,
    )


class ReviewPlanBuilderTest(unittest.TestCase):
    """直接测纯函数 _build_mock_review_plan（确定性最高）。"""

    def test_low_score_dimension_enters_reread_guide(self):
        # 1 个低分（4 分）+ 1 个高分（8 分）
        dims = [
            DimensionReport(name="理解深度", score=4, analysis="a", suggestion="补证明"),
            DimensionReport(name="表达完整性", score=8, analysis="b", suggestion="补充细节"),
        ]
        plan = _build_mock_review_plan(dims, "Dijkstra 算法")
        # 只有低分维度进重读指引
        self.assertEqual(len(plan.reread_guide), 1)
        self.assertIn("理解深度", plan.reread_guide[0].reason)
        self.assertGreaterEqual(len(plan.priority_order), 1)

    def test_no_low_score_returns_empty_plan(self):
        dims = [
            DimensionReport(name="理解深度", score=9, analysis="a", suggestion="s"),
            DimensionReport(name="表达完整性", score=8, analysis="b", suggestion="s"),
            DimensionReport(name="逻辑连贯性", score=8, analysis="c", suggestion="s"),
            DimensionReport(name="结构化能力", score=8, analysis="d", suggestion="s"),
        ]
        plan = _build_mock_review_plan(dims, "Dijkstra 算法")
        self.assertEqual(plan.reread_guide, [])
        self.assertEqual(plan.priority_order, [])


class MockReportTest(unittest.IsolatedAsyncioTestCase):
    """链路测试：多轮对话推到报告后，review_plan 必须非 None（验证修复）。"""

    async def test_report_returns_review_plan(self):
        service = _make_service(profile=None)
        inputs = [
            "这个知识点先讲一下它的基本流程",
            "它主要解决什么问题",
            "核心机制和适用条件是什么",
            "为什么这个方法是成立的",
            "它有哪些前提条件需要注意",
        ]
        response = None
        for text in inputs:
            response = await service.chat(
                FeynmanChatRequest(session_id="s1", user_input=text)
            )
            if response.next_action == NextAction.GENERATE_REPORT:
                break
        # 多轮追问后应产出报告
        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        # 修复后的核心断言：报告必须带 review_plan（修复前为 None）
        self.assertIsNotNone(response.review_plan)


class MockPainPointTest(unittest.IsolatedAsyncioTestCase):
    async def test_pain_point_appears_in_followup(self):
        # 有「输出薄弱」画像 → kp-demo 硬编码追问也带引导语（本次修复点）
        service = _make_service(profile=_make_profile(pain_points=["输出薄弱"]))
        response = await service.chat(
            FeynmanChatRequest(session_id="s2", user_input="冒泡排序是一种排序算法")
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertIn("一步步来", response.reply_text)

    async def test_no_profile_no_pain_point_suffix(self):
        # 无画像 → 追问话术不带引导语
        service = _make_service(profile=None)
        response = await service.chat(
            FeynmanChatRequest(session_id="s3", user_input="冒泡排序是一种排序算法")
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertNotIn("一步步来", response.reply_text)


if __name__ == "__main__":
    unittest.main()
