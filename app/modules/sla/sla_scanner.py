"""双 SLA 扫描（每日北京 08:00，工作日计时）：按责任人计数+单号列表，分群通报。

SLA-1 人工(t_ticket_info, ai_dev_owner, sla_start_at+sla_manual_hours)；
SLA-2 研发(t_ticket_hub, dev_owner, rd_sla_start_at+sla_rd_hours)。
去重：t_sla_log (ref_type, ref_id, notify_mark='YYYY-MM-DD-08:00')。回写/通报 dry_run 经 feishu client。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import RefType, SlaState, SlaType, TicketStatus
from app.core.config import settings
from app.integrations.feishu_client import get_feishu
from app.modules.sla.models import SlaLog
from app.modules.sla.workday import BEIJING, add_workday_hours
from app.modules.ticket.models import TicketHub, TicketInfo

logger = logging.getLogger("ticket_hub.sla")
_UNASSIGNED = "未分配"


def _mark(now: datetime) -> str:
    return now.astimezone(BEIJING).strftime("%Y-%m-%d") + "-08:00"


async def _already_notified(session: AsyncSession, ref_type: str, ref_id: int, mark: str) -> bool:
    return (await session.execute(
        select(SlaLog).where(SlaLog.ref_type == ref_type, SlaLog.ref_id == ref_id, SlaLog.notify_mark == mark)
    )).scalar_one_or_none() is not None


async def scan(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    mark = _mark(now)
    notify_date = now.astimezone(BEIJING).date()

    # ---- SLA-1 人工 ----
    infos = (await session.execute(select(TicketInfo).where(
        TicketInfo.status.notin_([TicketStatus.DONE.value, TicketStatus.CLOSED.value, TicketStatus.RETURNED.value]),
        TicketInfo.resolved_at.is_(None), TicketInfo.sla_start_at.is_not(None), TicketInfo.is_deleted.is_(False),
    ))).scalars()
    manual: dict[str, list[str]] = {}
    for info in infos:
        due = await add_workday_hours(session, info.sla_start_at, settings.sla_manual_hours)
        if now <= due:
            continue
        info.sla_state = SlaState.BREACHED.value
        owner = info.ai_dev_owner if (info.ai_dev_owner and not info.dev_owner_missing) else _UNASSIGNED
        if await _already_notified(session, RefType.INFO.value, info.id, mark):
            continue
        overdue_h = round((now - due).total_seconds() / 3600, 2)
        session.add(SlaLog(sla_type=SlaType.MANUAL.value, ref_type=RefType.INFO.value, ref_id=info.id,
                           owner=owner, notify_date=notify_date, notify_mark=mark, overdue_hours=overdue_h, notified=True))
        manual.setdefault(owner, []).append(info.ticket_no)

    # ---- SLA-2 研发 ----
    hubs = (await session.execute(select(TicketHub).where(
        TicketHub.status.notin_(["resolved", "closed"]), TicketHub.rd_resolved_at.is_(None),
        TicketHub.rd_sla_start_at.is_not(None), TicketHub.is_deleted.is_(False),
    ))).scalars()
    rd: dict[str, list[str]] = {}
    for hub in hubs:
        due = await add_workday_hours(session, hub.rd_sla_start_at, settings.sla_rd_hours)
        if now <= due:
            continue
        hub.rd_sla_state = SlaState.BREACHED.value
        owner = hub.dev_owner or _UNASSIGNED
        if await _already_notified(session, RefType.HUB.value, hub.id, mark):
            continue
        overdue_h = round((now - due).total_seconds() / 3600, 2)
        session.add(SlaLog(sla_type=SlaType.RD.value, ref_type=RefType.HUB.value, ref_id=hub.id,
                           owner=owner, notify_date=notify_date, notify_mark=mark, overdue_hours=overdue_h, notified=True))
        rd.setdefault(owner, []).append(hub.hub_no)

    await session.flush()
    await _notify(manual, settings.feishu_bot_webhook_sla_manual, "人工SLA")
    await _notify(rd, settings.feishu_bot_webhook_sla_rd, "研发SLA")
    logger.info("SLA 扫描完成: 人工%d人 研发%d人", len(manual), len(rd))
    return {"manual": {k: len(v) for k, v in manual.items()}, "rd": {k: len(v) for k, v in rd.items()}}


async def _notify(by_owner: dict[str, list[str]], webhook: str, label: str) -> None:
    for owner, nos in by_owner.items():
        text = f"【{label}超时通报】{owner} 名下 {len(nos)} 个超时未关闭：\n" + "、".join(nos[:50])
        await get_feishu().send_text(text, webhook=webhook or None)
