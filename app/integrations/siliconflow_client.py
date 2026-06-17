"""硅基流动 embedding 客户端（bge-m3，OpenAI 兼容 /embeddings）。"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.integrations.base import HttpClient

_client: Optional["SiliconFlowClient"] = None


class SiliconFlowClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            settings.siliconflow_base_url,
            integration="siliconflow",
            default_timeout=30.0,
            default_retries=settings.global_max_retry,
        )
        self.api_key = settings.siliconflow_api_key
        self.model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = await self.post(
            "/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": texts},
        )
        return [d["embedding"] for d in data["data"]]

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


def get_siliconflow() -> "SiliconFlowClient":
    global _client
    if _client is None:
        _client = SiliconFlowClient()
    return _client
