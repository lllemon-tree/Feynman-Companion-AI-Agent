import unittest

from backend.app.models.feynman import ChatMessage
from backend.app.services.prompt_builder import build_system_prompt, build_user_prompt


class FeynmanPromptTest(unittest.TestCase):
    def test_system_prompt_defines_canonical_total_and_whole_dialog_scoring(self):
        prompt = build_system_prompt("测试知识点", {})

        self.assertIn("不能只评价最后一轮", prompt)
        self.assertIn("已经正确说明的内容，必须认定为已覆盖", prompt)
        self.assertIn("严格等于四个维度 score 之和", prompt)
        self.assertIn("它不是0-10平均分", prompt)

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
