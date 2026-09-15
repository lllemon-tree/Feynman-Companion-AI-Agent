import unittest
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.graphs.feynman_graph import _normalize_contract
from backend.app.models.feynman import (
    CardPreview,
    DimensionEvidence,
    DimensionReport,
    FinalReport,
    FeynmanChatData,
    FeynmanChatRequest,
    NextAction,
    RelatedKp,
    ResetSessionRequest,
    ReviewPlan,
    ReviewPlanItem,
)
from backend.app.services.feynman_service import FeynmanService
from backend.app.services.mock_llm import MockLLMClient
from backend.app.services.rag_retriever import NullRAGRetriever
from backend.app.services.report_quality import sanitize_report_against_user_text
from backend.app.services.session_store import InMemorySessionStore


class FailingLLMClient:
    async def evaluate(self, **kwargs):
        raise RuntimeError("simulated provider failure")


class RecordingLLMClient:
    def __init__(self):
        self.calls = 0
        self._delegate = MockLLMClient()

    async def evaluate(self, **kwargs):
        self.calls += 1
        return await self._delegate.evaluate(**kwargs)


class StreamingLLMClient:
    async def evaluate(self, **kwargs):
        raise AssertionError("streaming path was not selected")

    async def evaluate_stream(self, *, on_reply_delta, **kwargs):
        on_reply_delta("你提到了非负权。")
        return FeynmanChatData(
            next_action=NextAction.FOLLOW_UP,
            reply_text="你提到了非负权。它为什么能保证贪心选择成立？",
        )


class FailingReportFinalizer:
    def finalize(self, session_state, response):
        raise RuntimeError("simulated report persistence failure")


class InconsistentScoreLLMClient:
    async def evaluate(self, **kwargs):
        scores = [7, 6, 8, 7]
        names = ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]
        return FeynmanChatData(
            next_action=NextAction.GENERATE_REPORT,
            reply_text="本轮讲解结束。",
            card_preview=CardPreview(total_score=7, summary="仍有少量内容可补充"),
            final_report=FinalReport(
                dimensions=[
                    DimensionReport(
                        name=name,
                        score=score,
                        analysis=f"{name}分析",
                        suggestion=f"{name}建议",
                    )
                    for name, score in zip(names, scores)
                ],
                overall_comment="主体理解正确，可以继续补充例证。",
            ),
        )


class EvidenceReportLLMClient(InconsistentScoreLLMClient):
    async def evaluate(self, **kwargs):
        result = await super().evaluate(**kwargs)
        result.final_report.dimensions[0].evidence = [
            DimensionEvidence(quote="这是一次完整讲解", observation="用户确实作出讲解"),
            DimensionEvidence(quote="用户从未说过这段话", observation="这是错误引用"),
        ]
        result.review_plan = ReviewPlan(
            reread_guide=[ReviewPlanItem(
                priority=1, material_name="当前教材", page_hint="第99页",
                focus="重新解释原理", reason="目前缺少因果解释",
            )],
            related_kps=[
                RelatedKp(kp_id="kp-demo2", kp_name="Floyd 算法", relation="对照最短路径算法"),
                RelatedKp(kp_id="made-up", kp_name="虚构知识点", relation="不应展示"),
            ],
        )
        return result


class FeynmanServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
        )

    async def test_streamed_reply_still_persists_validated_session(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=StreamingLLMClient(),
            fallback_client=MockLLMClient(),
            rag_retriever=NullRAGRetriever(),
        )
        deltas = []
        statuses = []
        data = await service.chat(
            FeynmanChatRequest(session_id="stream-service", user_input="Dijkstra 需要非负权"),
            on_reply_delta=deltas.append,
            on_status=lambda stage, text: statuses.append((stage, text)),
        )
        detail = service.get_session_detail("stream-service")
        self.assertEqual(deltas, ["你提到了非负权。"])
        self.assertEqual([stage for stage, _ in statuses], ["retrieving", "generating", "saving"])
        self.assertEqual(detail.chat_history[-1].content, data.reply_text)
        self.assertEqual(service.inspect_session("stream-service").follow_up_count, 1)

    async def test_off_topic_does_not_generate_report(self):
        response = await self.service.chat(
            FeynmanChatRequest(session_id="s1", user_input="今天天气怎么样")
        )
        self.assertEqual(response.next_action, NextAction.GUIDE_TOPIC)
        self.assertIsNone(response.card_preview)
        self.assertIsNone(response.final_report)
        debug = self.service.inspect_session("s1")
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.off_topic_count, 1)

    async def test_follow_up_then_report_after_max_rounds(self):
        first = await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="Dijkstra 是求图最短路径的算法")
        )
        self.assertEqual(first.next_action, NextAction.FOLLOW_UP)

        await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="它每次选未访问里距离最小的节点")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="然后对相邻节点做松弛更新")
        )
        final = await self.service.chat(
            FeynmanChatRequest(session_id="s2", user_input="非负权保证后续不会绕出更短路径")
        )
        self.assertEqual(final.next_action, NextAction.GENERATE_REPORT)
        self.assertIsNotNone(final.card_preview)
        self.assertIsNotNone(final.final_report)

    async def test_report_total_is_recomputed_from_dimension_scores(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=InconsistentScoreLLMClient(),
            fallback_client=MockLLMClient(),
        )

        final = await service.chat(
            FeynmanChatRequest(
                session_id="inconsistent-score",
                user_input="这是一次完整讲解，请直接生成报告",
            )
        )

        self.assertEqual(final.next_action, NextAction.GENERATE_REPORT)
        self.assertEqual(final.card_preview.total_score, 28)
        self.assertEqual(
            final.card_preview.total_score,
            sum(dimension.score for dimension in final.final_report.dimensions),
        )

        sticky = await service.chat(
            FeynmanChatRequest(
                session_id="inconsistent-score",
                user_input="已经结束后再次请求",
            )
        )
        self.assertEqual(sticky.card_preview.total_score, 28)

    async def test_report_evidence_must_quote_user_verbatim(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=EvidenceReportLLMClient(),
            fallback_client=MockLLMClient(),
            rag_retriever=NullRAGRetriever(),
        )
        report = await service.chat(FeynmanChatRequest(
            session_id="evidence-check", user_input="这是一次完整讲解，请直接生成报告",
        ))
        evidence = report.final_report.dimensions[0].evidence
        self.assertEqual([item.quote for item in evidence], ["这是一次完整讲解"])
        persisted = service.get_session_detail("evidence-check")
        self.assertEqual(persisted.report_data.final_report.dimensions[0].evidence, evidence)
        self.assertEqual(
            [item.kp_id for item in report.review_plan.related_kps], ["kp-demo2"]
        )
        self.assertEqual(report.review_plan.reread_guide[0].page_hint, "")

    async def test_first_correct_explanation_still_gets_one_understanding_check(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=InconsistentScoreLLMClient(),
            fallback_client=MockLLMClient(),
        )

        response = await service.chat(FeynmanChatRequest(
            session_id="minimum-diagnostic-exchange",
            user_input="封装通过私有属性和公开方法控制外部访问，提高安全性。",
        ))

        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertIn("再补一个最小例子", response.reply_text)
        self.assertIsNone(response.final_report)
        self.assertEqual(
            service.inspect_session("minimum-diagnostic-exchange").follow_up_count,
            1,
        )

        final = await service.chat(FeynmanChatRequest(
            session_id="minimum-diagnostic-exchange",
            user_input="例如年龄设为 private，只能通过 setAge 修改并检查不能为负数。",
        ))
        self.assertEqual(final.next_action, NextAction.GENERATE_REPORT)
        self.assertIsNotNone(final.final_report)

    async def test_user_can_explicitly_request_report_without_forced_check(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=InconsistentScoreLLMClient(),
            fallback_client=MockLLMClient(),
        )

        response = await service.chat(FeynmanChatRequest(
            session_id="explicit-report",
            user_input="我讲完了，不用追问，直接生成报告。",
        ))

        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)

    async def test_ineffective_answer_returns_hint_without_report(self):
        response = await self.service.chat(
            FeynmanChatRequest(session_id="s3", user_input="不会")
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertIsNone(response.card_preview)
        self.assertIsNone(response.final_report)
        debug = self.service.inspect_session("s3")
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.invalid_answer_count, 1)

    async def test_final_report_is_sticky_until_reset(self):
        session_id = "s4"
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="Dijkstra 是求图最短路径的算法")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="它每次选未访问里距离最小的节点")
        )
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="然后对相邻节点做松弛更新")
        )
        final = await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="非负权保证后续不会绕出更短路径")
        )
        again = await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="我想继续补充一些内容")
        )
        self.assertEqual(final, again)

    async def test_reset_clears_session_state(self):
        session_id = "s5"
        await self.service.chat(
            FeynmanChatRequest(session_id=session_id, user_input="Dijkstra 是求图最短路径的算法")
        )
        before = self.service.inspect_session(session_id)
        self.assertTrue(before.exists)
        self.assertGreater(before.follow_up_count, 0)

        reset = self.service.reset(ResetSessionRequest(session_id=session_id))
        after = self.service.inspect_session(session_id)

        self.assertTrue(reset.reset)
        self.assertTrue(after.exists)
        self.assertEqual(after.follow_up_count, 0)
        self.assertEqual(after.message_count, 0)
        self.assertFalse(after.ended)

    async def test_inspect_missing_session(self):
        debug = self.service.inspect_session("missing-session")
        self.assertFalse(debug.exists)
        self.assertEqual(debug.follow_up_count, 0)
        self.assertEqual(debug.message_count, 0)

    async def test_chat_binds_session_to_dynamic_knowledge_point(self):
        await self.service.chat(
            FeynmanChatRequest(
                session_id="dynamic-kp",
                kp_id="kp-demo2",
                user_input="Floyd 是一个求全源最短路径的动态规划算法",
            )
        )
        debug = self.service.inspect_session("dynamic-kp")
        self.assertEqual(debug.kp_id, "kp-demo2")
        self.assertEqual(debug.kp_name, "Floyd 算法")
        self.assertEqual(debug.material_id, "mat-demo")
        self.assertEqual(debug.chapter_id, "ch-demo")

    async def test_dynamic_kp_generates_generic_report_without_dijkstra_details(self):
        session_id = "floyd-report"
        answers = [
            "Floyd 用动态规划计算任意两点间最短路径",
            "状态表示只允许前 k 个点作为中间点",
            "转移时比较原距离和经过 k 的两段距离之和",
            "它可以处理负权边，但不能存在负权环",
        ]
        response = None
        for answer in answers:
            response = await self.service.chat(
                FeynmanChatRequest(
                    session_id=session_id,
                    kp_id="kp-demo2",
                    user_input=answer,
                )
            )
        self.assertIsNotNone(response)
        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        self.assertIn("Floyd", response.final_report.overall_comment)
        self.assertNotIn("Dijkstra", response.final_report.overall_comment)

    async def test_missing_knowledge_point_returns_guide_topic_and_clears_binding(self):
        response = await self.service.chat(
            FeynmanChatRequest(
                session_id="missing-kp",
                kp_id="kp-deleted",
                user_input="这是我的讲解",
            )
        )
        self.assertEqual(response.next_action, NextAction.GUIDE_TOPIC)
        self.assertIn("重新选择知识点", response.reply_text)
        self.assertIsNone(self.service.inspect_session("missing-kp").kp_id)

    async def test_switching_kp_requires_session_reset(self):
        session_id = "switch-kp"
        await self.service.chat(
            FeynmanChatRequest(
                session_id=session_id,
                kp_id="kp-demo",
                user_input="Dijkstra 是求最短路径的算法",
            )
        )
        with self.assertRaisesRegex(ValueError, "reset"):
            await self.service.chat(
                FeynmanChatRequest(
                    session_id=session_id,
                    kp_id="kp-demo2",
                    user_input="Floyd 是动态规划算法",
                )
            )

    async def test_llm_failure_falls_back_to_mock(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=FailingLLMClient(),
            fallback_client=MockLLMClient(),
        )
        response = await service.chat(
            FeynmanChatRequest(
                session_id="fallback",
                kp_id="kp-demo",
                user_input="Dijkstra 用来求图上的最短路径",
            )
        )
        self.assertEqual(response.next_action, NextAction.FOLLOW_UP)
        self.assertEqual(response.provider, "mock")
        self.assertTrue(response.fallback_used)
        debug = service.inspect_session("fallback")
        self.assertEqual(debug.last_provider, "mock")
        self.assertTrue(debug.fallback_used)

    async def test_graph_contains_expected_runtime_nodes(self):
        graph = self.service.draw_graph_mermaid()
        for node_name in [
            "load_context",
            "route_input",
            "kp_missing",
            "off_topic",
            "ineffective",
            "retrieve",
            "evaluate",
            "report",
            "persist_session",
        ]:
            self.assertIn(node_name, graph)

    async def test_forced_report_uses_primary_client_before_fallback(self):
        primary = RecordingLLMClient()
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=primary,
            fallback_client=MockLLMClient(),
        )
        session_id = "primary-report"
        for answer in [
            "Dijkstra 用于求最短路径",
            "它选择当前距离最小的未访问节点",
            "然后松弛相邻边",
            "非负权保证已确定距离不会再变短",
        ]:
            response = await service.chat(
                FeynmanChatRequest(session_id=session_id, user_input=answer)
            )

        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        self.assertEqual(primary.calls, 4)

    async def test_report_persistence_failure_does_not_block_chat_response(self):
        service = FeynmanService(
            store=InMemorySessionStore(),
            llm_client=MockLLMClient(),
            fallback_client=MockLLMClient(),
            report_finalizer=FailingReportFinalizer(),
        )
        response = None
        for answer in [
            "Dijkstra 用于求最短路径",
            "它选择当前距离最小的未访问节点",
            "然后松弛相邻边",
            "非负权保证已确定距离不会再变短",
        ]:
            response = await service.chat(
                FeynmanChatRequest(
                    session_id="report-failure",
                    user_input=answer,
                )
            )

        self.assertEqual(response.next_action, NextAction.GENERATE_REPORT)
        self.assertIsNotNone(response.final_report)


class FeynmanApiTest(unittest.TestCase):
    def test_report_removes_false_missing_claims_and_optional_requirements(self):
        user_texts = [
            "封装隐藏了实现细节，提高安全性和可维护性。",
            "通过方法修改时可以进行年龄校验，直接修改则没有校验。",
        ]
        response = FeynmanChatData(
            next_action=NextAction.GENERATE_REPORT,
            reply_text="本轮诊断已生成。",
            card_preview=CardPreview(total_score=32, summary="补充反例辨析"),
            final_report=FinalReport(
                dimensions=[
                    DimensionReport(
                        name="理解深度", score=8,
                        covered_points=["说明方法可以校验"],
                        gaps=["未提到隐藏实现细节、提高可维护性", "未举出反例或迁移应用"],
                        analysis="缺少实现细节、可维护性和反例。", suggestion="补反例。",
                    ),
                    DimensionReport(
                        name="表达完整性", score=8,
                        covered_points=["说明封装作用"],
                        gaps=["未明确说明封装还隐藏了实现细节"],
                        analysis="没有说明实现细节。", suggestion="补一句实现细节。",
                    ),
                    DimensionReport(
                        name="逻辑连贯性", score=8,
                        covered_points=["安全性因果成立"],
                        gaps=["未进一步解释封装如何提高可维护性"],
                        analysis="尚未解释可维护性的原因。", suggestion="补充原因。",
                    ),
                    DimensionReport(
                        name="结构化能力", score=8,
                        covered_points=["顺序清楚"],
                        gaps=["未使用分点或小标题，但短回答中可接受"],
                        analysis="没有分点。", suggestion="使用小标题。",
                    ),
                ],
                overall_comment="需要补充隐藏实现细节、反例和可维护性。",
            ),
        )

        sanitized = sanitize_report_against_user_text(response, user_texts)

        self.assertEqual(
            [item.score for item in sanitized.final_report.dimensions],
            [9, 9, 9, 9],
        )
        self.assertEqual(sanitized.card_preview.total_score, 36)
        self.assertEqual(sanitized.final_report.dimensions[0].gaps, [])
        self.assertEqual(sanitized.final_report.dimensions[1].gaps, [])
        self.assertEqual(
            sanitized.final_report.dimensions[2].gaps,
            ["未进一步解释封装如何提高可维护性"],
        )
        self.assertEqual(sanitized.final_report.dimensions[3].gaps, [])
        self.assertEqual(
            len({item.analysis for item in sanitized.final_report.dimensions}),
            4,
        )
        self.assertNotIn("反例", sanitized.card_preview.summary)
        self.assertIn("可维护性", sanitized.card_preview.summary)

    def test_report_keeps_only_the_truly_missing_part_of_a_combined_gap(self):
        response = FeynmanChatData(
            next_action=NextAction.GENERATE_REPORT,
            reply_text="诊断完成。",
            card_preview=CardPreview(total_score=32, summary="补充核心内容"),
            final_report=FinalReport(
                dimensions=[
                    DimensionReport(
                        name=name, score=8, analysis="分析", suggestion="建议",
                        gaps=["未提到隐藏实现细节、提高可维护性"] if index == 0 else [],
                    )
                    for index, name in enumerate(
                        ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]
                    )
                ],
                overall_comment="诊断。",
            ),
        )

        sanitized = sanitize_report_against_user_text(
            response, ["封装能够隐藏实现细节。"]
        )

        self.assertEqual(
            sanitized.final_report.dimensions[0].gaps,
            ["未提到提高可维护性"],
        )

    def test_optional_diagnostic_details_tolerate_empty_model_fields(self):
        dimension = DimensionReport.model_validate({
            "name": "理解深度", "score": 7, "analysis": "主体正确", "suggestion": "补充原因",
            "covered_points": None, "gaps": ["", "缺少原因"],
            "evidence": [
                {"quote": "", "observation": "无效"},
                {"quote": "提到非负权", "observation": "说明了适用条件"},
            ],
        })
        self.assertEqual(dimension.covered_points, [])
        self.assertEqual(dimension.gaps, ["缺少原因"])
        self.assertEqual([item.quote for item in dimension.evidence], ["提到非负权"])

    def test_follow_up_never_exposes_premature_review_plan(self):
        data = FeynmanChatData(
            next_action=NextAction.FOLLOW_UP,
            reply_text="再讲讲原因",
            review_plan=ReviewPlan(),
        )
        self.assertIsNone(_normalize_contract(data).review_plan)

    def test_generated_report_never_keeps_asking_the_user(self):
        data = FeynmanChatData(
            next_action=NextAction.GENERATE_REPORT,
            reply_text="如果外部直接给年龄赋值，会发生什么？",
            card_preview=CardPreview(total_score=28, summary="补充访问边界的因果说明"),
            final_report=FinalReport(
                dimensions=[
                    DimensionReport(
                        name=name, score=7, analysis="分析", suggestion="建议",
                    )
                    for name in ["理解深度", "表达完整性", "逻辑连贯性", "结构化能力"]
                ],
                overall_comment="主体正确。",
            ),
        )

        normalized = _normalize_contract(data)

        self.assertNotIn("？", normalized.reply_text)
        self.assertIn("诊断报告已经生成", normalized.reply_text)
        self.assertIn("补充访问边界的因果说明", normalized.reply_text)

    def test_stream_endpoint_sends_deltas_then_validated_result(self):
        class FakeService:
            async def chat(self, request, user_id, on_reply_delta=None, on_status=None):
                on_status("retrieving", "正在检索相关教材内容…")
                on_reply_delta("先看非负权")
                on_status("saving", "正在保存本轮讲解与诊断…")
                return FeynmanChatData(
                    next_action=NextAction.FOLLOW_UP,
                    reply_text="先看非负权，再想想为什么贪心选择成立？",
                )

        with patch("backend.app.api.routes.get_feynman_service", return_value=FakeService()):
            response = TestClient(app).post("/api/v1/feynman/chat/stream", json={
                "session_id": "stream-unit-test", "kp_id": "kp-demo", "user_input": "Dijkstra 为什么成立？",
            })
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(response.status_code, 200)
        self.assertEqual([event["type"] for event in events], ["status", "status", "delta", "status", "done"])
        self.assertEqual([event.get("stage") for event in events if event["type"] == "status"],
                         ["loading", "retrieving", "saving"])
        self.assertEqual(events[-1]["data"]["reply_text"], "先看非负权，再想想为什么贪心选择成立？")

    def test_greeting_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 200)
        self.assertIn("reply_text", body["data"])
        self.assertEqual(body["data"]["kp_id"], "kp-demo")
        self.assertEqual(body["data"]["kp_name"], "Dijkstra 算法")

    def test_dynamic_greeting_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting", params={"kp_id": "kp-demo2"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["kp_id"], "kp-demo2")
        self.assertIn("Floyd", body["data"]["reply_text"])

    def test_missing_greeting_kp_returns_404(self):
        client = TestClient(app)
        response = client.get("/api/v1/feynman/greeting", params={"kp_id": "kp-missing"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
