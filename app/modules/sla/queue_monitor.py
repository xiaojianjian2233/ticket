"""队列健康监控：积压告警 / abandoned 告警（系统级飞书，独立于责任人 SLA 通报）。

关键依赖全挂的"挂起不消费"在 worker 侧；此处只做积压/卡死告警。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TaskStatus
from app.core.config import settings
from app.db.queue import TaskQueue
from app.integrations.feishu_client import get_feishu

logger = logging.getLogger("ticket_hub.queue")


async def scan(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    pending = (await session.execute(
        select(func.count()).select_from(TaskQueue).where(TaskQueue.status == TaskStatus.PENDING.value)
    )).scalar_one()
    abandoned = (await session.execute(
        select(func.count()).select_from(TaskQueue).where(TaskQueue.status == TaskStatus.ABANDONED.value)
    )).scalar_one()
    oldest = (await session.execute(
        select(func.min(TaskQueue.available_at)).where(TaskQueue.status == TaskStatus.PENDING.value)
    )).scalar_one()
    oldest_min = (now - oldest).total_seconds() / 60 if oldest else 0

    alerts = []
    if pending > settings.queue_backlog_n:
        alerts.append(f"队列积压 {pending} > {settings.queue_backlog_n}")
    if oldest_min > settings.queue_oldest_m:
        alerts.append(f"最老任务等待 {oldest_min:.0f}分 > {settings.queue_oldest_m}分")
    if abandoned > 0:
        alerts.append(f"abandoned 任务 {abandoned} 个待重入队")
    if alerts:
        await get_feishu().send_text("【系统告警】" + "；".join(alerts), webhook=settings.feishu_bot_webhook_system or None)
        logger.warning("队列告警: %s", alerts)
    return {"pending": pending, "abandoned": abandoned, "oldest_min": round(oldest_min, 1), "alerts": alerts}
