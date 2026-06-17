"""Linear→本系统 状态主动同步（拉取）。

push（/webhook/linear）依赖外部中转推送；若在 Linear 界面直接改状态、中转未触发，本系统不会更新。
本模块定时（scheduler）/手动 拉取 Linear issue 当前 state.name 回写 hub.status + 关联 info.rd_status，
作为 push 的兜底，保证最终一致。仅镜像状态，不触发自动关单/转人工等副作用（那些只在 push 路径做，避免重复处理）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.linear_client import get_linear
from app.modules.ticket import repository as ticket_repo
from app.modules.ticket.models import TicketHub, TicketInfo

logger = logging.getLogger("ticket_hub.linear")

# 已终态(完成/取消)不再轮询；其余持续兜底拉取
_TERMINAL_TYPES = {"completed", "canceled"}


async def sync_hub(session: AsyncSession, hub: TicketHub) -> bool:
    """拉取单个 hub 的 Linear 状态并回写。状态有变更返回 True。"""
    if not hub.linear_issue_id:
        return False
    state = await get_linear().get_issue_state(hub.linear_issue_id)
    if not state:
        return False
    name = (state.get("name") or "").strip()
    if not name or name == (hub.status or ""):
        return False
    old = hub.status
    hub.status = name
    hub.rd_callback_at = datetime.now(timezone.utc)
    for info in (await session.execute(select(TicketInfo).where(TicketInfo.rd_hub_id == hub.id))).scalars():
        await ticket_repo.update_info(session, info, rd_status=name)
    logger.info("Linear 拉取同步 hub=%s status %s -> %s", hub.hub_no, old, name)
    return True


async def poll_open_hubs(session: AsyncSession, limit: int = 200) -> int:
    """轮询所有未删除、有 Linear issue、且未到终态的 hub，回写状态。返回更新条数。"""
    rows = list((await session.execute(
        select(TicketHub).where(TicketHub.is_deleted.is_(False), TicketHub.linear_issue_id.is_not(None))
        .order_by(TicketHub.id.desc()).limit(limit))).scalars())
    changed = 0
    for hub in rows:
        try:
            state = await get_linear().get_issue_state(hub.linear_issue_id)
        except Exception:  # noqa: BLE001 — 单条失败不影响其它
            logger.exception("Linear 拉取失败 hub=%s", hub.hub_no)
            continue
        if not state:
            continue
        name = (state.get("name") or "").strip()
        if name and name != (hub.status or ""):
            old = hub.status
            hub.status = name
            hub.rd_callback_at = datetime.now(timezone.utc)
            for info in (await session.execute(select(TicketInfo).where(TicketInfo.rd_hub_id == hub.id))).scalars():
                await ticket_repo.update_info(session, info, rd_status=name)
            logger.info("Linear 拉取同步 hub=%s status %s -> %s", hub.hub_no, old, name)
            changed += 1
    return changed
