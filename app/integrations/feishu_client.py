"""飞书客户端：SSO OAuth（登录）+ 群机器人 webhook 通知。

通知发送经 dry_run 守卫（开发期不真发群）。OAuth 端点按飞书 v1 OIDC；联调按实际微调。
"""
from __future__ import annotations

import time
from typing import Optional

from app.core.config import settings
from app.core.exceptions import IntegrationException
from app.integrations.base import HttpClient

_client: Optional["FeishuClient"] = None
_BASE = "https://open.feishu.cn"


class FeishuClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(_BASE, integration="feishu", default_timeout=30.0)
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self._app_token: Optional[str] = None
        self._app_token_exp: float = 0.0

    # ---------- OAuth / SSO ----------
    async def app_access_token(self, force: bool = False) -> str:
        now = time.time()
        if not force and self._app_token and now < self._app_token_exp:
            return self._app_token
        data = await self.post("/open-apis/auth/v3/app_access_token/internal",
                               json={"app_id": self.app_id, "app_secret": self.app_secret})
        if data.get("code") != 0:
            raise IntegrationException(f"app_access_token 失败: {data.get('msg')}", integration="feishu")
        self._app_token = data["app_access_token"]
        self._app_token_exp = now + int(data.get("expire", 7200)) - 300
        return self._app_token

    def authorize_url(self, state: str = "") -> str:
        redirect = settings.feishu_sso_redirect_uri
        return (f"{_BASE}/open-apis/authen/v1/index?app_id={self.app_id}"
                f"&redirect_uri={redirect}&response_type=code&state={state}")

    async def exchange_code(self, code: str) -> dict:
        """code → user_access_token → user_info。返回飞书用户信息(name/open_id/email/mobile/avatar)。"""
        app_token = await self.app_access_token()
        tok = await self.post("/open-apis/authen/v1/oidc/access_token",
                              headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
                              json={"grant_type": "authorization_code", "code": code})
        if tok.get("code") != 0:
            raise IntegrationException(f"oidc access_token 失败: {tok.get('msg')}", integration="feishu")
        user_token = tok["data"]["access_token"]
        info = await self.get("/open-apis/authen/v1/user_info",
                              headers={"Authorization": f"Bearer {user_token}"})
        if info.get("code") != 0:
            raise IntegrationException(f"user_info 失败: {info.get('msg')}", integration="feishu")
        return info["data"]

    # ---------- 群机器人通知 ----------
    async def send_text(self, text: str, *, webhook: Optional[str] = None) -> dict:
        """发文本到群机器人。webhook 默认取 FEISHU_BOT_WEBHOOKS 第一个。dry_run 时不真发。"""
        url = webhook or (settings.feishu_bot_webhooks.split(",")[0].strip() if settings.feishu_bot_webhooks else "")
        payload = {"msg_type": "text", "content": {"text": text}}
        if self.dry_run or not url:
            return self.dry_run_stub("feishu.send_text", {"text": text[:200], "webhook": url[:60]})
        return await self.post(url, json=payload)


def get_feishu() -> "FeishuClient":
    global _client
    if _client is None:
        _client = FeishuClient()
    return _client
