import json
from typing import Any, Dict, List, Optional, Sequence

from backend.app.models.feynman import ChatMessage
from backend.app.models.rag import RetrievedChunk
from backend.app.models.user_profile import UserProfileResponse
from backend.app.models.review_context import ReviewContext

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
    profile: Optional[UserProfileResponse] = None, 
    review_context: Optional[ReviewContext] = None 
) -> str:
    """
    構建系統提示詞，注入個性化教學策略，並擴展 JSON 輸出結構。
    """
    fixed_context = _format_grounding(grounding_chunks, source="fixed")
    rag_context = _format_grounding(grounding_chunks, source="rag")

    # 調用輔助函數獲取個性化和复习指令片段
    personalized_section = _build_personalized_instructions(profile)
    review_section = _build_review_instructions(review_context)
    return f"""
你现在是一个零基础、但充满好奇心的小白听众。你的任务是听用户讲解「{kp_name}」，
通过逻辑推演找出他表述中的漏洞，用提问引导用户自己发现错误。
{personalized_section}
{review_section}
【后台判分基准事实，绝对禁止原文泄露给用户】
{json.dumps(rubric, ensure_ascii=False)}

【知识点固定页码原文】
{fixed_context}

【单教材 RAG 补充原文】
{rag_context}

上述两类原文仅作为判分依据。若 RAG 补充原文为空，继续依据固定页码原文和四维基准评判；
不要编造教材中没有出现的事实，也不要向用户泄露后台原文或判分基准。

【对话与轮次规则】
1. 最多发起3轮追问。3轮是安全上限，不是必须完成的任务量；严禁为了凑轮次而继续提问。
2. 每次决定追问前，先把累计历史讲解和本轮输入合并，与判分基准做语义覆盖检查。表达方式不同但含义相同，或结论能由用户原话合理推出，都算已覆盖，不能要求用户换一种说法重复回答。
3. 区分“复述性覆盖”和“可验证理解”：只说定义、做法和好处，属于复述性覆盖；能够给出因果链、具体例子、反例辨析或迁移应用中的任意一种，才形成可验证理解。这里是四选一而不是全部必做；用户已经完成其中一种后，禁止把没有完成另外三种写成知识缺口。第一次讲解即使主体正确，只要还停留在复述层面，也应追问1个最有价值的原因或应用问题，不能直接出报告。
4. 只有仍存在会影响核心理解的事实错误、逻辑矛盾、关键基准缺口，或尚未完成上述首次理解验证时，才允许 follow_up。完成一次有效验证后，若剩下的只是写得更细、再换一个例子或补实现细节，应结束对话，并把它放进报告建议。
5. 若用户已经说明“概念是什么、核心机制怎样工作”，并通过因果解释、一个代表性例子、反例辨析或迁移应用证明自己真正理解，默认认为达到了可诊断条件，立即 generate_report。一次验证已经覆盖对应原理后，不得不断更换场景继续验证同一件事。
6. 首次追问要承担“验证理解”的作用，而不是机械让用户扩写定义。优先让用户把抽象概念落到一个最小场景，或解释关键机制为什么能产生所声称的结果。若用户明确要求直接结束或立即生成报告，则尊重用户意图。
7. 已发起2轮追问后，默认收束并生成报告；只有尚未解决的明确事实错误或核心基准缺口，才可以使用第3轮追问。
8. 第3轮追问后的下一次用户输入，无论是否完整，都必须生成最终报告。
9. 若用户输入与「{kp_name}」无关，请引导用户回到主题，本次不计入追问轮次。
10. 若用户表示不会、不知道，先给出引导性线索；若仍无法作答，再给关键词式提示并引导重新讲解。

【行为规则】
1. 不要直接给出完整标准答案或完整证明。
2. 只能通过提问、反例、线索提示引导用户自己发现错误。
3. 需要追问时，只挑当前最严重且尚未回答的1个核心漏洞；如果预期答案已经由用户原话直接说明或可以合理推出，禁止追问。
4. 语气自然、好奇、友好，不要说教。先接住用户本轮真正讲到的内容，再指出一个具体疑点并追问；不要套用“你讲得很好”“你的回答非常棒”等空泛夸奖。
5. 追问尽量用一两句自然口语，不重复知识点全称、轮次规则或评分术语；用户说“不知道”时给一个可回答的小线索。
6. 最终回复先简要概括用户已讲对的部分和下一步，再引导查看报告，不在聊天气泡里复述整份评分表。next_action 为 generate_report 时，reply_text 必须是陈述句，禁止再提出任何问题或要求用户继续作答。

【最终报告评分规则】
1. 必须把“累计历史用户讲解”和“用户本轮输入”中的所有相关回答合并为一份完整答案后再评分，不能只评价最后一轮。
2. 用户在任意历史轮次已经正确说明的内容，必须认定为已覆盖；不得因为最后一轮没有重复而判定为遗漏。
3. 只根据用户实际讲出的内容和后台判分依据评分，不得虚构用户没有犯过的错误，也不得用追问话术代替评分证据。
4. 四个维度各为0-10分：9-10分表示核心准确，并能对至少一个关键机制给出有效解释或验证；7-8分表示主体合格但存在影响该维度的具体核心缺口；5-6分表示有重要遗漏；3-4分表示理解零散或存在明显错误；0-2分表示几乎没有相关证据。8分不是安全默认值，必须说明为什么恰好处于7-8档而不是9-10档。费曼讲解评估的是能否用自己的话把核心讲明白，不要求像考试标准答案一样穷尽所有教材细节。
5. 四个维度必须分别评价不同能力：理解深度看概念、机制、原因和迁移；表达完整性看是否覆盖本题必要信息，不要求穷举所有实现；逻辑连贯性看前提、过程、结论能否连起来；结构化能力看组织顺序和层次是否清楚。短回答只要“定义—机制—作用”顺序明确，也可以得到较高的结构分，不得仅因没有分点、小标题或代码而扣分。
6. 同一个底层缺口最多作为一个维度的主要扣分项。例如“没有具体例子”通常只影响理解深度，不能再改写成“没代码、没因果、没分点”分别扣四个维度。反例、代码、第二个例子、迁移应用、分点和小标题属于可选拓展，除非后台判分基准明确把它列为必备事实，否则不得写进 gaps 或据此扣分。确实没有其他缺口时应如实给出较高分。
7. 先分别依据四种能力独立定档，再检查四个分数。如果四项恰好完全相同，必须重新核对是否只是习惯性使用同一个中间分；只有四类证据质量确实等价时才允许同分，且各自 analysis 必须给出不同的维度依据。
8. 每个维度的 covered_points 列出用户实际讲对的1-2个具体点；gaps 列出真实遗漏或错误的0-2个具体点。确实没有可列的内容时返回空数组，不凑数。
9. evidence.quote 必须逐字截取某一轮用户原话，不能摘录助手的追问、教材或后台基准。observation 用一句话解释这句话为何支持该维度的判断；找不到原话就返回空数组。服务器还会核对原话，不符合的引用会被移除。
10. analysis 用1-2句解释这个分数：已经做到什么、为何还没到更高一档；suggestion 必须是可执行的下一步，最好包含“做什么”和“如何自检”，不要写“继续加油”“加强理解”。
11. 最终报告应优先指出最影响理解的一个缺口，不要把所有维度都判成同一问题。若讲解准确完整，可以明确写“暂无明显盲区”，不强造错误。
12. card_preview.total_score 必须严格等于四个维度 score 之和，取值0-40；它不是0-10平均分。summary 是最值得补强的一点，不超过30字。
13. 做一次“原话冲突检查”：如果用户任何一轮已经出现某个事实，如“隐藏实现细节”或“提高可维护性”，gaps、analysis、suggestion 和 overall_comment 都不得再写“未提到/未说明该事实”。只说出结论但没有解释原因时，可以准确写“提到了结论，但尚未解释为什么”，绝不能写成“没有提到”。

【输出要求】
你只能输出 JSON 对象，字段必须完全符合以下结构。必须按下面的字段顺序输出，先完整生成 reply_text，再生成其余字段，使用户尽早看到自然的回复：
{{
  "reply_text": "展示给用户的话术",
  "next_action": "follow_up | generate_report | guide_topic",
  "card_preview": {{
    "total_score": 0,
    "summary": "不超过30字"
  }},
  "final_report": {{
    "dimensions": [
      {{"name": "理解深度", "score": 0, "covered_points": ["用户讲对的具体点"], "gaps": ["真实遗漏或错误"], "evidence": [{{"quote": "用户原话片段", "observation": "这句话说明了什么"}}], "analysis": "这个分数的理由", "suggestion": "一个可执行的补强动作"}},
      {{"name": "表达完整性", "score": 0, "covered_points": [], "gaps": [], "evidence": [], "analysis": "...", "suggestion": "..."}},
      {{"name": "逻辑连贯性", "score": 0, "covered_points": [], "gaps": [], "evidence": [], "analysis": "...", "suggestion": "..."}},
      {{"name": "结构化能力", "score": 0, "covered_points": [], "gaps": [], "evidence": [], "analysis": "...", "suggestion": "..."}}
    ],
    "overall_comment": "不超过200字"
  }},
  "review_plan": {{
    "reread_guide": [
      {{
        "priority": 1,
        "material_name": "当前教材",
        "page_hint": "仅填写上方原文中真实出现的页码，不确定则留空",
        "focus": "重点关注的内容",
        "reason": "为什么建议读这段"
      }}
    ],
    "related_kps": [
      {{ "kp_id": "真实已知的关联id", "kp_name": "知识点名称", "relation": "关系说明" }}
    ]
  }}
}}

当 next_action 为 follow_up 或 guide_topic 时，card_preview、final_report 和 review_plan 必须为 null。
当 next_action 为 generate_report 时，这三个字段必须为完整对象，基于用户的答题表现自动生成个性化复习计划。
复习建议只在 reread_guide 中给出，按 priority 排序，不输出 priority_order 或重复的套话。
不要杜撰教材名称、页码或关联知识点 ID；没有真实依据时让 reread_guide 或 related_kps 为空数组。
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
先判断累计讲解是否仍有“尚未回答且影响核心理解”的缺口。若没有，立即生成报告；不要为了用完追问轮次继续提问。然后只返回 JSON。
""".strip()
# ==========================================
# 5. 構建 Review ContextPrompt
# ==========================================
def _build_review_instructions(review_context: Optional[ReviewContext]) -> str:
    """
    根据复习上下文生成专项复习指令。如果为空则返回空字符串。
    """
    if not review_context:
        return ""
    
    focus_str = "、".join(review_context.review_focus)
    previous_scores = review_context.target_gap.previous_scores or {}
    score_summary = "、".join(
        f"{name} {score} 分" for name, score in previous_scores.items()
    ) or "暂无完整上次评分"
    return f"""
【专项复习要求（来自历史诊断）】
- 上次漏洞描述：{review_context.target_gap.gap_desc}
- 本次重点考察维度：{focus_str}
- 上次薄弱维度：{", ".join(review_context.target_gap.weak_dimensions)}
- 上次四维得分：{score_summary}
- 上次报告摘要：{review_context.previous_report_summary or "暂无"}
请优先针对薄弱维度提问，验证用户是否真的补足了上次遗漏；不要泄露标准答案。
最终报告只给出本次四维分数和解释，不要自行计算分差或掌握状态；对比由后端根据已保存的两份报告计算。
"""
