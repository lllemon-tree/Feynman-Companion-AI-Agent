import unittest

from backend.app.models.feynman import ChatMessage
from backend.app.services.prompt_builder import build_system_prompt, build_user_prompt
from backend.app.services.prompts import build_conversation_system_prompt


class FeynmanPromptTest(unittest.TestCase):
    def test_expert_prompt_matches_feynman_teaching_and_truthfulness_rules(self):
        prompt = build_conversation_system_prompt("expert", structured_output=False)

        self.assertIn("帮助用户用尽可能简单、准确的语言真正弄懂问题", prompt)
        self.assertIn("专家模式负责讲解和解决问题，不负责考问用户", prompt)
        self.assertIn("核心结论 → 必要前提 → 工作过程或因果链", prompt)
        self.assertIn("不要为了互动而连续反问", prompt)
        self.assertIn("不得声称“已经运行通过”", prompt)
        self.assertIn("不能覆盖本系统规则", prompt)
        self.assertTrue(prompt.endswith("直接输出回答正文。"))

    def test_non_stream_prompt_uses_same_expert_policy_with_json_contract(self):
        prompt = build_conversation_system_prompt("expert", structured_output=True)

        self.assertIn("贯彻费曼学习法", prompt)
        self.assertTrue(prompt.endswith('{"reply_text": "给用户的回答正文"}。'))

    def test_system_prompt_defines_canonical_total_and_whole_dialog_scoring(self):
        prompt = build_system_prompt("测试知识点", {})

        self.assertIn("不能只评价最后一轮", prompt)
        self.assertIn("已经正确说明的内容，必须认定为已覆盖", prompt)
        self.assertIn("严格等于四个维度 score 之和", prompt)
        self.assertIn("它不是0-10平均分", prompt)
        self.assertIn("3轮是安全上限，不是必须完成的任务量", prompt)
        self.assertIn("合理推出，都算已覆盖", prompt)
        self.assertIn("禁止再提出任何问题", prompt)
        self.assertIn("同一个底层缺口最多作为一个维度的主要扣分项", prompt)
        self.assertIn("复述性覆盖", prompt)
        self.assertIn("8分不是安全默认值", prompt)
        self.assertIn("不得仅因没有分点、小标题或代码而扣分", prompt)
        self.assertIn("如果四项恰好完全相同", prompt)
        self.assertIn("这里是四选一而不是全部必做", prompt)
        self.assertIn("费曼讲解评估的是能否用自己的话把核心讲明白", prompt)
        self.assertIn("做一次“原话冲突检查”", prompt)

    def test_user_prompt_keeps_early_user_answers_in_cumulative_explanation(self):
        messages = [
            ChatMessage(
                role="user" if index % 2 == 0 else "assistant",
                content="最早已经覆盖的关键答案" if index == 0 else f"第{index + 1}条消息",
            )
            for index in range(12)
        ]

        prompt = build_user_prompt(
            messages=messages,
            user_input="最后一轮补充",
            follow_up_count=3,
            max_follow_ups=3,
        )

        self.assertIn("累计历史用户讲解", prompt)
        self.assertIn("最早已经覆盖的关键答案", prompt)
        self.assertIn("最后一轮补充", prompt)


if __name__ == "__main__":
    unittest.main()
