import json
from typing import Any, Dict, List, Optional, Sequence

from backend.app.models.feynman import ChatMessage
from backend.app.models.rag import RetrievedChunk
from backend.app.models.user_profile import UserProfileResponse

# ==========================================
# 1. 定義痛點與階段的 Prompt 映射字典
# ==========================================

# 痛點映射：將用戶選擇的痛點轉化為具體的大模型追問與評價策略
PAIN_POINTS_MAPPING = {
    "概念理解困难": "学习者对抽象概念理解有困难。追问时多用生活类比和具体例子引导，避免纯术语堆砌。评价时重点关注'是否能用大白话解释核心原理'。",
    "输出薄弱": "学习者口头表达/文字输出能力弱、不善组织语言。追问时采用'先简后详'策略——第一轮让用户一句话概括，第二轮扩展到段落，第三轮要求完整讲解。评价时不过度扣表达完整性的分，但引导用户逐步输出。",
    "知识碎片化": "学习者知识点分散、不成体系。追问时强调知识之间的关联，例如'这个概念和你之前学的 X 有什么联系？''它在整个章节中处于什么位置？'",
    "盲目刷题": "学习者倾向机械刷题而非理解原理。追问时少给题目、多问'为什么'。评价时重点扣'理解深度'维度，引导用户关注原理而非答案。",
    "自律性差": "学习者需要外部激励和明确指引。追问语气温暖坚定，多给正向反馈和阶段性肯定（如'这一步理解得很好'），并在每轮结束时明确告知下一步要做什么。"
}

# 階段映射：將用戶的備考階段轉化為大模型的難度控制標準
STAGE_MAPPING = {
    "基础": "学习者处于基础阶段，刚接触该学科。追问侧重概念定义和基本流程的确认，不要求严格证明和跨知识点关联。评分时适当放宽'理解深度'标准。",
    "强化": "学习者处于强化阶段，已完成一轮基础复习。追问侧重跨知识点关联、方法对比和适用条件辨析。评分标准正常。",
    "冲刺": "学习者处于冲刺阶段，临近考试。追问侧重易错点辨析、高频考点的深度理解和实战应用。评分时严格对待概念混淆问题。"
}

# ==========================================
# 2. 輔助函數：解析學情畫像並生成個性化指令
# ==========================================

def _build_personalized_instructions(profile: Optional[UserProfileResponse]) -> str:
    """
    根據用戶畫像生成個性化的 Prompt 指令。
    如果畫像為空，則返回空字符串（安全降級）。
    """
    # 兼容遊客模式或無畫像用戶
    if not profile:
        return ""

    instructions: List[str] = []

    # 處理痛點：檢查 pain_points 是否存在且不為空
    if profile.pain_points:
        for pain_point in profile.pain_points:
            # 去字典中安全獲取對應指令，找不到則忽略
            instruction = PAIN_POINTS_MAPPING.get(pain_point)
            if instruction:
                instructions.append(f"- 针对「{pain_point}」：{instruction}")

    # 處理備考階段：檢查 preparation_stage 是否存在
    if profile.preparation_stage:
        stage_instruction = STAGE_MAPPING.get(profile.preparation_stage)
        if stage_instruction:
            instructions.append(f"- 针对「{profile.preparation_stage}阶段」：{stage_instruction}")

    # 如果組裝後有內容，則加上標題並返回；否則返回空字符串
    if instructions:
        joined_instructions = "\n".join(instructions)
        return f"\n【个性化教学策略（务必遵守）】\n{joined_instructions}\n"

    return ""


def _format_grounding(chunks: Sequence[RetrievedChunk], source: str) -> str:
    """
    格式化 RAG 檢索原文（保留原來的邏辑）
    """
    selected = [chunk for chunk in chunks if chunk.source == source]
    if not selected:
        return "（暂无）"
    return "\n\n".join(
        f"[第{chunk.page_no}页 / {chunk.chunk_id}]\n{chunk.text}"
        for chunk in selected
    )

# ==========================================
# 3. 核心構建函數：構建 System Prompt
# ==========================================

def build_system_prompt(
    kp_name: str,
    rubric: Dict[str, Any],
    grounding_chunks: Sequence[RetrievedChunk] = (),
    profile: Optional[UserProfileResponse] = None # 新增：接收用戶畫像
) -> str:
    """
    構建系統提示詞，注入個性化教學策略，並擴展 JSON 輸出結構。
    """
    fixed_context = _format_grounding(grounding_chunks, source="fixed")
    rag_context = _format_grounding(grounding_chunks, source="rag")

    # 調用輔助函數獲取個性化指令片段
    personalized_section = _build_personalized_instructions(profile)

    return f"""
你现在是一个零基础、但充满好奇心的小白听众。你的任务是听用户讲解「{kp_name}」，
通过逻辑推演找出他表述中的漏洞，用提问引导用户自己发现错误。
{personalized_section}
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
你只能输出 JSON 对象，字段必须完全符合以下结构（注意新增了 review_plan）：
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
  }},
  "review_plan": {{
    "reread_guide": [
      {{
        "priority": 1,
        "material_name": "教材名称",
        "page_hint": "如第3章 第30页",
        "focus": "重点关注的内容",
        "reason": "为什么建议读这段"
      }}
    ],
    "related_kps": [
      {{ "kp_id": "关联的id", "kp_name": "知识点名称", "relation": "关系说明" }}
    ],
    "priority_order": [
      {{ "rank": 1, "dimension": "薄弱维度名称", "kp_name": "知识点名称", "suggestion": "具体的复习建议" }}
    ]
  }}
}}

当 next_action 为 follow_up 或 guide_topic 时，card_preview、final_report 和 review_plan 必须为 null。
当 next_action 为 generate_report 时，这三个字段必须为完整对象，基于用户的答题表现自动生成个性化复习计划。
""".strip()

# ==========================================
# 4. 構建 User Prompt (直接遷移原有代碼)
# ==========================================

def build_user_prompt(
    messages: Sequence[ChatMessage],
    user_input: str,
    follow_up_count: int,
    max_follow_ups: int,
    grounding_chunks: Sequence[RetrievedChunk] = (),
) -> str:
    """
    構建用戶輸入提示詞。保留原有邏輯不變。
    """
    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in messages[-8:]
    )
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
