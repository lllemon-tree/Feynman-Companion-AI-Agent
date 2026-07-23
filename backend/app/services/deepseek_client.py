import json
from typing import Any, Sequence

import httpx

from backend.app.core.config import Settings
from backend.app.models.feynman import ChatMessage, FeynmanChatData
from backend.app.models.knowledge import KPExtractionResponse
from backend.app.models.rag import RetrievedChunk
from backend.app.services.kp_provider import KnowledgePoint
from backend.app.services.prompts import (
    KP_EXTRACTION_SYSTEM_PROMPT,
    RUBRIC_GENERATION_SYSTEM_PROMPT,
    build_kp_user_prompt,
    build_rubric_user_prompt,
    build_system_prompt,
    build_user_prompt,
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
    ) -> FeynmanChatData:
        parsed = await self._request_json(
            system_prompt=build_system_prompt(
                kp_name=knowledge_point.name,
                rubric=knowledge_point.rubric,
                grounding_chunks=grounding_chunks,
            ),
            user_prompt=build_user_prompt(
                messages=messages,
                user_input=user_input,
                follow_up_count=follow_up_count,
                max_follow_ups=max_follow_ups,
            ),
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

    async def _request_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
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


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])
