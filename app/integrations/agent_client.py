"""ask agent 客户端（本期：现有旧单步契约 POST {agent_url} {question, cid}）。

设计目标是四步 open-api-channel，但仅有旧单步凭证（INTERNAL_AGENT_URL, cid=test）。
故本期单步实现；字段防御性解析（answer / transfer_result），失败→由 answer-router 兜底转 C。
★只调同步接口（单步阻塞返回），超时 500s；不重试（retries=0）避免对同一问题重复提问。
提问 question 必须带产品线标签：「{产品线}-{功能模块}：{原始问题}」(由 harness 拼装)。
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.integrations.base import HttpClient

_client: Optional["AgentClient"] = None


class AgentClient(HttpClient):
    def __init__(self) -> None:
        # 超时 60s：单步端点不可用时快速失败→分支C，不阻塞流水线（L2 联调正式四步凭证后再调）
        super().__init__(integration="agent", default_timeout=500.0, default_retries=0)
        self.url = settings.agent_url
        self.cid = settings.agent_cid
        self.token = settings.agent_token

    async def ask(self, question: str, *, images: Optional[list[str]] = None) -> dict:
        """提问 agent。返回 {answer, transfer_result, raw}。"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["token"] = self.token
        body: dict = {"question": question, "ai_agent_cid": self.cid}
        if images:
            body["images"] = images
        data = await self.post(self.url, headers=headers, json=body, timeout=500.0)
        # 防御性提取（兼容 data 包裹；真实字段为 llm_answer / answer_type）
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        answer = (inner.get("llm_answer") or inner.get("answer") or inner.get("reply")
                  or data.get("llm_answer") or data.get("answer") or "")
        transfer = inner.get("transfer_result") or data.get("transfer_result")
        if not transfer:
            # 无答复 / success=false / answer_type 含 TRANSFER → 视为需转人工
            atype = str(inner.get("answer_type") or "").upper()
            transfer = "TRANSFER" if (inner.get("success") is False or "TRANSFER" in atype) else "NO_ACTION"
        return {"answer": answer, "transfer_result": transfer, "raw": data}


def get_agent() -> "AgentClient":
    global _client
    if _client is None:
        _client = AgentClient()
    return _client
