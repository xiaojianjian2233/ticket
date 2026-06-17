"""第三方 HTTP 集成基类：统一超时 / 退避重试 / dry-run / 错误归一。

约定：
- 每个外部系统一个 client 子类，复用本基类的 request()；不反向依赖业务模块。
- 重试次数按 client 配置：KSM=settings.ksm_max_retry(默认 3)，其余默认 settings.global_max_retry。
- 写操作（回写/建单/通知）经 dry_run 守卫：settings.writeback_dry_run=True 时只记日志返回桩，不真发。
- 失败抛 IntegrationException；t_integration_log 由调用方（service/harness）按需落库。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationException

logger = logging.getLogger("ticket_hub.integration")


class HttpClient:
    """异步 HTTP 客户端基类（懒加载 httpx.AsyncClient）。"""

    def __init__(
        self,
        base_url: str = "",
        *,
        integration: str = "http",
        default_timeout: float = 30.0,
        default_retries: Optional[int] = None,
        backoff_base: float = 1.0,
    ) -> None:
        self.base_url = base_url
        self.integration = integration
        self.default_timeout = default_timeout
        self.default_retries = settings.global_max_retry if default_retries is None else default_retries
        self.backoff_base = backoff_base
        self._client: Optional[httpx.AsyncClient] = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.default_timeout)
        return self._client

    @property
    def dry_run(self) -> bool:
        return settings.writeback_dry_run

    async def request(
        self,
        method: str,
        url: str,
        *,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
        expect_json: bool = True,
        raise_for_status: bool = True,
        **kwargs: Any,
    ) -> Any:
        """带退避重试的请求。返回 json（expect_json）或 httpx.Response。失败抛 IntegrationException。"""
        client = self._ensure()
        n = self.default_retries if retries is None else retries
        to = timeout or self.default_timeout
        attempt = 0
        last_err: Optional[str] = None
        while attempt <= n:
            t0 = time.perf_counter()
            try:
                resp = await client.request(method, url, timeout=to, **kwargs)
                if raise_for_status:
                    resp.raise_for_status()
                cost = int((time.perf_counter() - t0) * 1000)
                logger.info("[%s] %s %s -> %s (%dms, try%d)", self.integration, method, url, resp.status_code, cost, attempt)
                return resp.json() if expect_json else resp
            except Exception as exc:  # noqa: BLE001
                last_err = f"{type(exc).__name__}: {exc}"
                logger.warning("[%s] %s %s 失败(try%d/%d): %s", self.integration, method, url, attempt, n, last_err)
                attempt += 1
                if attempt > n:
                    break
                await asyncio.sleep(self.backoff_base * (2 ** (attempt - 1)))
        raise IntegrationException(last_err or "request failed", integration=self.integration)

    async def get(self, url: str, **kw: Any) -> Any:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> Any:
        return await self.request("POST", url, **kw)

    def dry_run_stub(self, op: str, payload: dict) -> dict:
        """写操作 dry-run：记日志并返回模拟成功信封（不真发）。"""
        logger.info("[%s] DRY_RUN %s payload=%s", self.integration, op, _truncate(payload))
        return {"dry_run": True, "op": op, "ok": True}

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _truncate(obj: Any, limit: int = 500) -> str:
    s = str(obj)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"
