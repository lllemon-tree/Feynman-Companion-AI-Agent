import json
from typing import Any, Dict, Sequence

from backend.app.models.feynman import ChatMessage
from backend.app.models.rag import RetrievedChunk


def build_system_prompt(
    kp_name: str,
    rubric: Dict[str, Any],
    grounding_chunks: Sequence[RetrievedChunk] = (),
) -> str:
    fixed_context = _format_grounding(grounding_chunks, source="fixed")
    rag_context = _format_grounding(grounding_chunks, source="rag")
    return f"""
你现在是一个零基础、但充满好奇心的小白听众。你的任务是听用户讲解「{kp_name}」，
通过逻辑推演找出他表述中的漏洞，用提问引导用户自己发现错误。

【后台判分基准事实，绝对禁止原文泄露给用户】
{json.dumps(rubric, ensure_ascii=False)}

【知识点固定页码原文】
{fixed_context}

【单教材 RAG 补充原文】
{rag_context}

上述两类原文仅作为判分依据。若 RAG 补充原文为空，继续依据固定页码原文和四维基准评判；
不要编造教材中没有出现的事实，也不要向用户泄露后台原文或判分基准。

【对话与轮次规则】
1. 最多发起3轮追问。第3轮追问后的下一次用户输入，无论是否完整，都必须生成最终报告。
2. 若用户讲解已完整覆盖所有基准事实且无逻辑错误，可提前结束，直接生成最终报告。
3. 若用户输入与「{kp_name}」无关，请引导用户回到主题，本次不计入追问轮次。
4. 若用户表示不会、不知道，先给出引导性线索；若仍无法作答，再给关键词式提示并引导重新讲解。

【行为规则】
1. 不要直接给出完整标准答案或完整证明。
2. 只能通过提问、反例、线索提示引导用户自己发现错误。
3. 每次回复只挑当前最严重的1个逻辑漏洞追问。
4. 语气自然、好奇、友好，不要说教。

【最终报告评分规则】
1. 必须把“累计历史用户讲解”和“用户本轮输入”中的所有相关回答合并为一份完整答案后再评分，不能只评价最后一轮。
2. 用户在任意历史轮次已经正确说明的内容，必须认定为已覆盖；不得因为最后一轮没有重复而判定为遗漏。
3. 只根据用户实际讲出的内容和后台判分依据评分，不得虚构用户没有犯过的错误，也不得用追问话术代替评分证据。
4. 四个维度各为0-10分：9-10分表示准确完整且能解释原因；7-8分表示主体正确但有少量缺口；5-6分表示掌握基本结论但有重要遗漏；3-4分表示理解零散或存在明显错误；0-2分表示几乎未形成相关解释。
5. 每个维度的 analysis 应先指出用户已经覆盖的内容，再指出真实存在的不足；suggestion 只能针对真实不足。
6. card_preview.total_score 必须严格等于四个维度 score 之和，取值0-40；它不是0-10平均分。

【输出要求】
你只能输出 JSON 对象，字段必须完全符合：
{{
  "next_action": "follow_up | generate_report | guide_topic",
  "reply_text": "展示给用户的话术",
  "card_preview": {{
    "total_score": 0,
    "summary": "不超过30字"
  }},
  "final_report": {{
    "dimensions": [
      {{"name": "理解深度", "score": 0, "analysis": "...", "suggestion": "..."}},
      {{"name": "表达完整性", "score": 0, "analysis": "...", "suggestion": "..."}},
      {{"name": "逻辑连贯性", "score": 0, "analysis": "...", "suggestion": "..."}},
      {{"name": "结构化能力", "score": 0, "analysis": "...", "suggestion": "..."}}
    ],
    "overall_comment": "不超过200字"
  }}
}}

当 next_action 为 follow_up 或 guide_topic 时，card_preview 和 final_report 必须为 null。
当 next_action 为 generate_report 时，card_preview 和 final_report 必须为完整对象。
""".strip()


def _format_grounding(
    chunks: Sequence[RetrievedChunk],
    source: str,
) -> str:
    selected = [chunk for chunk in chunks if chunk.source == source]
    if not selected:
        return "（暂无）"
    return "\n\n".join(
        f"[第{chunk.page_no}页 / {chunk.chunk_id}]\n{chunk.text}"
        for chunk in selected
    )


def build_user_prompt(
    messages: Sequence[ChatMessage],
    user_input: str,
    follow_up_count: int,
    max_follow_ups: int,
    grounding_chunks: Sequence[RetrievedChunk] = (),
) -> str:
    transcript = "\n".join(f"{message.role}: {message.content}" for message in messages[-8:])
    historical_user_explanations = [
        message.content for message in messages if message.role == "user"
    ]
    cumulative_explanation = "\n".join(
        f"{index}. {content}"
        for index, content in enumerate(historical_user_explanations, start=1)
    )

    return f"""
当前已发起追问轮数：{follow_up_count}/{max_follow_ups}

累计历史用户讲解（最终报告必须与本轮输入合并评分）：
{cumulative_explanation or "暂无"}

最近历史对话（仅用于理解问答上下文）：
{transcript or "暂无"}

用户本轮输入：
{user_input}
请根据规则判断下一步动作，并只返回 JSON。
""".strip()

# 专门用于后端 A (教材解析管线) 的系统提示词
KP_EXTRACTION_SYSTEM_PROMPT = """
你是一个严谨的教材解析助手。
你的任务是从提供的教材切片中提取知识点，并严格按照 JSON 格式输出。

提取规则：
1. name: 知识点名称必须精炼（10个字以内，如专有名词、核心理论）。
2. summary: 总结该知识点的核心定义或作用（50字以内）。
3. page_no: 严格使用输入文本中提供的 [页码] 信息。
4. 如果该段文本无实质学术价值，请返回空的 knowledge_points 列表。

必须返回合法的 JSON 对象，不要包含 Markdown 标记和解释性文本。结构如下：
{
  "knowledge_points": [
    {
      "name": "...",
      "summary": "...",
      "page_no": 0
    }
  ]
}
""".strip()


def build_kp_user_prompt(text: str, page_no: int) -> str:
    """构建知识点抽取的 User Prompt"""
    return f"请分析以下教材切片并提取知识点：\n\n[页码: {page_no}]\n{text}"


# 生成四维Rubric
RUBRIC_GENERATION_SYSTEM_PROMPT = """
你是一个教育专家。请根据提供的教材原文切片，为该知识点生成四维费曼学习评价标准。
必须严格输出以下 JSON 结构，不要包含 markdown 标记：
{
  "concept_prerequisite": "...",
  "core_mechanism": "...",
  "principle_proof": "...",
  "common_misunderstandings": ["误区1", "误区2", "误区3", "误区4"]
}
""".strip()


def build_rubric_user_prompt(text: str, kp_name: str) -> str:
    return f"知识点：{kp_name}\n\n参考原文：\n{text}\n\n请基于原文生成评价标准。"
