import json
import re
from typing import Any, AsyncIterator, Callable, Optional, Sequence

import httpx

from backend.app.core.config import Settings
from backend.app.models.feynman import ChatMessage, FeynmanChatData
from backend.app.models.knowledge import KPExtractionResponse
from backend.app.models.rag import RetrievedChunk
from backend.app.models.review_context import ReviewContext
from backend.app.models.user_profile import UserProfileResponse
from backend.app.services.kp_provider import KnowledgePoint
from backend.app.services.prompt_builder import build_system_prompt, build_user_prompt
from backend.app.services.prompts import (
    KP_EXTRACTION_SYSTEM_PROMPT,
    RUBRIC_GENERATION_SYSTEM_PROMPT,
    build_conversation_system_prompt,
    build_kp_user_prompt,
    build_rubric_user_prompt,
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
        knowledge_point: KnowledgePoint,
        grounding_chunks: Sequence[RetrievedChunk] = (),
        profile: Optional[UserProfileResponse] = None,
        review_context: Optional[ReviewContext] = None,
    ) -> FeynmanChatData:
        parsed = await self._request_json(
            system_prompt=build_system_prompt(
                kp_name=knowledge_point.name,
                rubric=knowledge_point.rubric,
                grounding_chunks=grounding_chunks,
                profile=profile,
                review_context=review_context,
            ),
            user_prompt=build_user_prompt(
                messages=messages,
                user_input=user_input,
                follow_up_count=follow_up_count,
                max_follow_ups=max_follow_ups,
                grounding_chunks=grounding_chunks,
            ),
        )
        return FeynmanChatData.model_validate(parsed)

    async def evaluate_stream(
        self,
        messages: Sequence[ChatMessage],
        user_input: str,
        follow_up_count: int,
        max_follow_ups: int,
        knowledge_point: KnowledgePoint,
        grounding_chunks: Sequence[RetrievedChunk] = (),
        profile: Optional[UserProfileResponse] = None,
        review_context: Optional[ReviewContext] = None,
        on_reply_delta: Callable[[str], None] | None = None,
    ) -> FeynmanChatData:
        parsed = await self._request_json_streaming(
            system_prompt=build_system_prompt(
                kp_name=knowledge_point.name,
                rubric=knowledge_point.rubric,
                grounding_chunks=grounding_chunks,
                profile=profile,
                review_context=review_context,
            ),
            user_prompt=build_user_prompt(
                messages=messages,
                user_input=user_input,
                follow_up_count=follow_up_count,
                max_follow_ups=max_follow_ups,
                grounding_chunks=grounding_chunks,
            ),
            on_reply_delta=on_reply_delta,
        )
        return FeynmanChatData.model_validate(parsed)

    async def extract_knowledge(self, chunk_text: str, page_no: int) -> KPExtractionResponse:
        parsed = await self._request_json(
            system_prompt=KP_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=build_kp_user_prompt(chunk_text, page_no),
        )
        return KPExtractionResponse.model_validate(parsed)

    async def generate_rubric(self, source_text: str, kp_name: str) -> dict[str, Any]:
        return await self._request_json(
            system_prompt=RUBRIC_GENERATION_SYSTEM_PROMPT,
            user_prompt=build_rubric_user_prompt(source_text, kp_name),
        )

    async def respond_in_conversation(self, mode: str, history: str, user_input: str, model: str | None = None) -> str:
        system_prompt = build_conversation_system_prompt(
            mode, structured_output=True
        )
        result = await self._request_json(
            system_prompt=system_prompt,
            user_prompt=f"【已有对话】\n{history}\n【用户本轮输入】\n{user_input}",
            model=model,
        )
        return str(result.get("reply_text", "")).strip()

    async def stream_in_conversation(
        self, mode: str, history: str, user_input: str, model: str
    ) -> AsyncIterator[str]:
        if not self._settings.deepseek_configured:
            raise RuntimeError("DeepSeek API key is not configured.")
        system_prompt = build_conversation_system_prompt(
            mode, structured_output=False
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【已有对话】\n{history}\n【用户本轮输入】\n{user_input}"},
            ],
            "stream": True,
            "thinking": {"type": "disabled"},
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            async with client.stream(
                "POST", f"{self._settings.deepseek_base_url}/chat/completions",
                headers=headers, json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    if not raw:
                        continue
                    event = json.loads(raw)
                    if "error" in event:
                        raise RuntimeError(str(event["error"]))
                    choices = event.get("choices") or []
                    if choices:
                        content = choices[0].get("delta", {}).get("content")
                        if content:
                            yield content

    async def assess_free_explanation(
        self, history: str, user_explanations: str, model: str | None = None
    ) -> dict[str, Any]:
        return await self._request_json(
            system_prompt=(
                "你是费曼伴学的讲解评估器。这里没有指定教材，不要声称和某本教材一致，也不要给数值分数。"
                "只评估用户自己讲过的话，不把助手之前给出的内容当成用户的理解。"
                "输出 JSON，字段必须有 topic、strengths（字符串数组）、gaps（字符串数组）、"
                "evidence（数组，每项含 quote 和 observation）、next_step。"
                "evidence.quote 必须逐字复制用户原话中的一小段；找不到证据就不要编造。"
            ),
            user_prompt=f"【对话上下文】\n{history}\n【仅供评估的用户讲解原话】\n{user_explanations}",
            model=model,
        )

    async def _request_json(
        self, system_prompt: str, user_prompt: str, model: str | None = None
    ) -> dict[str, Any]:
        if not self._settings.deepseek_configured:
            raise RuntimeError("DeepSeek API key is not configured.")

        # ===== 调试：打印是否注入个性化教学策略（痛点/阶段）=====
        if "【个性化教学策略" in system_prompt:
            p_start = system_prompt.find("【个性化教学策略")
            p_end = system_prompt.find("【后台判分基准事实")
            segment = system_prompt[p_start:p_end] if p_end != -1 else system_prompt[p_start:p_start + 300]
            print(f"\n{'='*60}")
            print(f"个性化教学策略已注入:")
            print(segment.strip())
            print(f"{'='*60}\n")
        else:
            print(f"\n（当前无个性化策略注入：游客或未填写学情画像）\n")

        # ===== 调试：打印 Prompt 中是否包含 RAG 检索原文 =====
        if "【单教材 RAG 补充原文" in system_prompt:
            rag_start = system_prompt.find("【单教材 RAG 补充原文")
            print(f"\n{'='*60}")
            print(f"RAG 检索原文已注入 system_prompt:")
            print(f"{system_prompt[rag_start:rag_start+300]}...")
            print(f"{'='*60}\n")
        else:
            print(f"\n（system_prompt 中未包含 RAG 补充原文）\n")
        # =================================================

        payload = {
            "model": model or self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
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
        return _parse_json_object(content)

    async def _request_json_streaming(
        self, system_prompt: str, user_prompt: str,
        on_reply_delta: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        if not self._settings.deepseek_configured:
            raise RuntimeError("DeepSeek API key is not configured.")
        payload = {
            "model": self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "stream": True,
            # 深度思考默认开启时，先输出 reasoning_content；用户端看不到，
            # 会误以为整个知识点回复没有流式输出。
            "thinking": {"type": "disabled"},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        content_parts: list[str] = []
        visible = ""
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            async with client.stream(
                "POST", f"{self._settings.deepseek_base_url}/chat/completions",
                headers=headers, json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    if not raw:
                        continue
                    event = json.loads(raw)
                    if "error" in event:
                        raise RuntimeError(str(event["error"]))
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if not delta:
                        continue
                    content_parts.append(delta)
                    partial = _reply_text_prefix("".join(content_parts))
                    if on_reply_delta and partial.startswith(visible) and len(partial) > len(visible):
                        on_reply_delta(partial[len(visible):])
                    visible = partial
        return _parse_json_object("".join(content_parts))


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def _reply_text_prefix(content: str) -> str:
    """Decode only the completed prefix of the top-level reply_text JSON string."""
    match = re.search(r'(?<!\\)"reply_text"\s*:\s*"', content)
    if match is None:
        return ""
    start = match.end()
    index = start
    while index < len(content):
        char = content[index]
        if char == '"':
            break
        if char == "\\":
            if index + 1 >= len(content):
                break
            if content[index + 1] == "u":
                if index + 6 > len(content):
                    break
                if not re.fullmatch(r"[0-9a-fA-F]{4}", content[index + 2:index + 6]):
                    break
                index += 6
                continue
            index += 2
            continue
        index += 1
    try:
        return json.loads('"' + content[start:index] + '"')
    except json.JSONDecodeError:
        return ""
