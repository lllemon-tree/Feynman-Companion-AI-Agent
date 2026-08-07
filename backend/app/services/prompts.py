import json
from typing import Any, Dict, Sequence

from backend.app.models.feynman import ChatMessage
from backend.app.models.rag import RetrievedChunk

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
