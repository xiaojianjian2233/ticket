"""FastAPI 入口：装配中间件 / 异常处理 / 路由。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import TraceMiddleware
from app.core.response import success


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ticket-hub", version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    app.add_middleware(TraceMiddleware)
    register_exception_handlers(app)

    @app.get("/health")
    async def health():
        return success({"status": "ok", "env": settings.app_env})

    # 业务路由（阶段三逐模块接入）
    _register_routers(app)
    return app


def _register_routers(app: FastAPI) -> None:
    """逐模块 router 在此装配。"""
    from app.modules.intake.router import router as intake_router
    from app.modules.feishu.router import router as feishu_router
    from app.modules.ticket.router import router as ticket_router

    from app.modules.knowledge.router import router as knowledge_router
    from app.modules.sla.router import router as sla_router
    from app.modules.assistant.router import router as assistant_router
    from app.modules.skill.router import router as skill_router
    from app.modules.dispatch.router import router as dispatch_router
    from app.modules.ticket.module_owner_router import router as module_owner_router
    from app.modules.ticket.linear_router import router as linear_router

    app.include_router(intake_router)     # /webhook/ksm,zhichi
    app.include_router(feishu_router)     # /api/v1/auth/* + /api/v1/users
    app.include_router(ticket_router)     # /api/v1/tickets + /hubs + /workbench
    app.include_router(knowledge_router)  # /api/v1/faq
    app.include_router(sla_router)        # /api/v1/sla
    app.include_router(assistant_router)  # /api/v1/assistant
    app.include_router(skill_router)      # /api/v1/skills
    app.include_router(dispatch_router)   # /api/v1/dispatch
    app.include_router(module_owner_router)  # /api/v1/module-owners
    app.include_router(linear_router)     # /webhook/linear


app = create_app()
