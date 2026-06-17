"""中间件：trace_id 注入 + 请求日志。"""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import new_trace_id, set_trace_id

logger = logging.getLogger("ticket_hub.access")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tid = request.headers.get("X-Trace-Id") or new_trace_id()
        set_trace_id(tid)
        start = time.perf_counter()
        response = await call_next(request)
        cost = (time.perf_counter() - start) * 1000
        logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, cost)
        response.headers["X-Trace-Id"] = tid
        return response
