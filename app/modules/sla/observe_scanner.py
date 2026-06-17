"""观察期扫描：resolved_at + N 天(可配14) 且未退回 → 本地 status=closed（不回写来源系统）。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TicketStatus
from app.core.config import settings
from app.modules.ticket.models import TicketInfo

logger = logging.getLogger("ticket_hub.observe")


async def scan(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.observe_days)
    rows = (await session.execute(select(TicketInfo).where(
        TicketInfo.resolved_at.is_not(None),
        TicketInfo.resolved_at <= cutoff,
        TicketInfo.status.notin_([TicketStatus.CLOSED.value, TicketStatus.RETURNED.value]),
        TicketInfo.is_deleted.is_(False),
    ))).scalars()
    n = 0
    for info in rows:
        info.status = TicketStatus.CLOSED.value
        info.closed_at = now
        n += 1
    await session.flush()
    if n:
        logger.info("观察期到期本地关闭 %d 单", n)
    return n
