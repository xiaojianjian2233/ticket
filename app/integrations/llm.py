"""OpenAI 兼容 chat 客户端（Claude 网关 + DeepSeek 共用）。"""
from __future__ import annotations

from typing import Optional

from app.integrations.base import HttpClient


class ChatClient(HttpClient):
    """OpenAI 兼容 /v1/chat/completions 客户端。"""

    def __init__(self, base_url: str, api_key: str, model: str, *, integration: str) -> None:
        super().__init__(base_url, integration=integration, default_timeout=60.0, default_retries=1)
        self.api_key = api_key
        self.model = model

    async def chat(
        self,
        *,
        system: Optional[str] = None,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = await self.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=body,
        )
        return data["choices"][0]["message"]["content"]
