import json
from typing import Any, Sequence

import httpx

from backend.app.core.config import Settings
from backend.app.models.feynman import ChatMessage, FeynmanChatData

# 知识点提取相关导入
from backend.app.models.knowledge import KPExtractionResponse
from backend.app.services.prompts import (
    SYSTEM_PROMPT, 
    build_user_prompt,
    KP_EXTRACTION_SYSTEM_PROMPT,
    RUBRIC_GENERATION_SYSTEM_PROMPT,
    build_rubric_user_prompt,
    build_kp_user_prompt
)

class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def evaluate(
        self,
        messages: Sequence[ChatMessage],
        user_input: str,
        follow_up_count: int,
        max_follow_ups: int,
    ) -> FeynmanChatData:
        if not self._settings.deepseek_configured:
            raise RuntimeError("DeepSeek API key is not configured.")

        payload = {
            "model": self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        messages=messages,
                        user_input=user_input,
                        follow_up_count=follow_up_count,
                        max_follow_ups=max_follow_ups,
                    ),
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.deepseek_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        parsed = _parse_json_object(content)
        return FeynmanChatData.model_validate(parsed)

    # 提取知识点方法
    async def extract_knowledge(self, chunk_text: str, page_no: int) -> KPExtractionResponse:
        """
        针对后端 A：解析管线的知识点抽取方法
        """
        if not self._settings.deepseek_configured:
            raise RuntimeError("DeepSeek API key is not configured.")

        # 真正“访问 (access)”并使用了你导入的提示词变量
        payload = {
            "model": self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": KP_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_kp_user_prompt(chunk_text, page_no)},
            ],
            "temperature": 0.2, 
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}", # Bearer是指令牌认证方式
            "Content-Type": "application/json", # Content-Type指定请求体的格式为JSON
        }

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client: # 创建异步 HTTP 客户端
            response = await client.post(
                f"{self._settings.deepseek_base_url}/chat/completions", # chat/completions 是 DeepSeek API 的端点，用于生成聊天响应
                headers=headers,
                json=payload,
            )
            response.raise_for_status() # raise_for_status() 方法会在响应状态码不是 2xx 时抛出异常，确保请求成功
            data = response.json()

        content = data["choices"][0]["message"]["content"] # 从响应中提取生成的内容，DeepSeek API 返回的结构中，choices 是一个列表，包含生成的消息，取第一个消息的内容
        parsed_dict = _parse_json_object(content)
        
        return KPExtractionResponse.model_validate(parsed_dict)

    # 为知识点生成四维Rubric
    async def generate_rubric(self, source_text: str, kp_name: str) -> dict[str, Any]:
            """
            [新增] 为知识点生成四维 Rubric 解析
            """
            if not self._settings.deepseek_configured:
                raise RuntimeError("DeepSeek API key is not configured.")

            # 使用我们之前约定的 RUBRIC_GENERATION_SYSTEM_PROMPT 和 build_rubric_user_prompt
            payload = {
                "model": self._settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": RUBRIC_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": build_rubric_user_prompt(source_text, kp_name)},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }

            headers = {
                "Authorization": f"Bearer {self._settings.deepseek_api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.deepseek_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            # 复用之前的清洗逻辑
            return _parse_json_object(content)

def _parse_json_object(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(content[start : end + 1])

