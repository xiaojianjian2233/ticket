"""智齿(Sobot)工单客户端：get_token(md5签名,缓存) + 回写 save_ticket_reply + 查询。

依据 智齿接口速查.md：业务成功 ret_code=='000000'；token 失效(100001/100002)刷新重试。
回写经 dry_run 守卫（开发期只组装不真发）。
"""
from __future__ import annotations

import hashlib
import time
from typing import Optional

from app.common.constants import ZHICHI_STATUS_RESOLVED
from app.core.config import settings
from app.core.exceptions import IntegrationException
from app.integrations.base import HttpClient

_client: Optional["ZhichiClient"] = None


class ZhichiClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(settings.zhichi_base_url, integration="zhichi", default_timeout=30.0)
        self.appid = settings.zhichi_appid
        self.app_key = settings.zhichi_app_key
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    async def _get_token(self, force: bool = False) -> str:
        now = time.time()
        if not force and self._token and now < self._token_exp:
            return self._token
        create_time = str(int(now))
        sign = hashlib.md5((self.appid + create_time + self.app_key).encode()).hexdigest()
        data = await self.get("/api/get_token", params={"appid": self.appid, "create_time": create_time, "sign": sign})
        if data.get("ret_code") != "000000":
            raise IntegrationException(f"get_token 失败: {data.get('ret_msg')}", integration="zhichi")
        item = data["item"]
        self._token = item["token"]
        self._token_exp = now + int(item.get("expires_in", 86400)) - 300
        return self._token

    async def _biz_post(self, path: str, payload: dict) -> dict:
        """业务 POST：带 token，token 失效自动刷新重试一次。"""
        for attempt in range(2):
            token = await self._get_token(force=(attempt == 1))
            data = await self.post(path, headers={"token": token, "content-type": "application/json"}, json=payload)
            rc = data.get("ret_code")
            if rc == "000000":
                return data
            if rc in ("100001", "100002") and attempt == 0:
                continue  # token 失效，刷新重试
            raise IntegrationException(f"{path} 失败: ret_code={rc} {data.get('ret_msg')}", integration="zhichi")
        raise IntegrationException(f"{path} 重试后仍失败", integration="zhichi")

    async def get_ticket_by_id(self, ticketid: str) -> dict:
        data = await self._biz_post("/api/ws/5/ticket/get_ticket_by_id", {"ticketid": ticketid})
        return data.get("item", {})

    async def save_ticket_reply(
        self,
        *,
        ticketid: str,
        ticket_title: str,
        ticket_content: str,
        reply_content: str,
        ticket_status: int,
        reply_agentid: str = "",
        reply_agent_name: str = "",
        ticket_level: int = 1,
        reply_file_str: str = "",
    ) -> dict:
        """回写工单（关单 ticket_status=3 / 补料=2 / 不接管话术=3）。dry_run 时不真发。"""
        payload = {
            "ticketid": ticketid,
            "ticket_title": ticket_title,
            "ticket_content": ticket_content,
            "get_ticket_datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reply_content": reply_content,
            "reply_type": 0,
            "reply_agentid": reply_agentid,
            "reply_agent_name": reply_agent_name,
            "ticket_status": ticket_status,
            "ticket_level": ticket_level,
            "reply_file_str": reply_file_str,
        }
        if self.dry_run:
            return self.dry_run_stub("save_ticket_reply", payload)
        return await self._biz_post("/api/ws/5/ticket/save_ticket_reply", payload)

    async def close_with_reply(self, *, ticketid: str, title: str, content: str, reply: str) -> dict:
        """关单（已解决 3）。"""
        return await self.save_ticket_reply(
            ticketid=ticketid, ticket_title=title, ticket_content=content,
            reply_content=reply, ticket_status=ZHICHI_STATUS_RESOLVED,
        )


def get_zhichi() -> "ZhichiClient":
    global _client
    if _client is None:
        _client = ZhichiClient()
    return _client
