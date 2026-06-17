"""异常分层 + FastAPI 全局异常处理器。对外不泄露堆栈。"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ticket_hub")


class BizException(Exception):
    """业务可预期异常。"""

    def __init__(self, message: str, code: int = 400):
        self.code = code
        self.message = message
        super().__init__(message)


class IntegrationException(Exception):
    """第三方集成异常。"""

    def __init__(self, message: str, integration: str = ""):
        self.integration = integration
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizException)
    async def _biz(request: Request, exc: BizException):
        logger.warning("BizException: %s", exc.message)
        return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})

    @app.exception_handler(IntegrationException)
    async def _integration(request: Request, exc: IntegrationException):
        logger.error("IntegrationException[%s]: %s", exc.integration, exc.message)
        return JSONResponse(status_code=200, content={"code": 502, "message": "外部服务异常", "data": None})

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=200, content={"code": 422, "message": "参数校验失败", "data": exc.errors()})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=200, content={"code": exc.status_code, "message": str(exc.detail), "data": None})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(status_code=200, content={"code": 500, "message": "系统繁忙，请重试", "data": None})
