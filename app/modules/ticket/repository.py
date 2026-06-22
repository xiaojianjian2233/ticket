"""工单仓储：单号生成 + 幂等查询 + 建单 + 退回更新。

只在此层读写 t_ticket_info/detail/org（service/pipeline 经此访问 DB）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import timedelta

from app.common.constants import TICKET_NO_PREFIX
from app.common.enums import TicketStatus
from app.core.config import settings
from app.modules.ticket.models import ModuleOwner, TicketDetail, TicketHub, TicketInfo, TicketOrg

_BEIJING = timezone(timedelta(hours=8))


async def next_ticket_no(session: AsyncSession) -> str:
    """FPY + 北京日期 + 序列值（PG sequence 防并发重号）。"""
    seq = (await session.execute(text("SELECT nextval('seq_ticket_no')"))).scalar_one()
    today = datetime.now(_BEIJING).strftime("%Y%m%d")
    return f"{TICKET_NO_PREFIX}{today}{int(seq):06d}"


async def get_by_source(session: AsyncSession, source: str, source_id: str) -> Optional[TicketInfo]:
    """幂等键 (source, source_id) 查现存工单。"""
    return (
        await session.execute(
            select(TicketInfo).where(
                TicketInfo.source == source,
                TicketInfo.source_id == source_id,
                TicketInfo.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()


async def create_ticket(
    session: AsyncSession,
    *,
    source: str,
    source_id: str,
    has_attachment: bool,
    info_fields: dict[str, Any],
    detail_fields: dict[str, Any],
    org_fields: dict[str, Any],
) -> TicketInfo:
    """建新单：插 info + detail + org，启动 SLA-1 时钟。"""
    now = datetime.now(timezone.utc)
    info = TicketInfo(
        ticket_no=await next_ticket_no(session),
        source=source,
        source_id=source_id,
        has_attachment=has_attachment,
        status=TicketStatus.PENDING.value,
        sla_start_at=now,
        # TODO(SLA): 改为 workday 计时（排除周末+节假日）；暂用自然 +N 小时占位
        sla_due_at=now + timedelta(hours=settings.sla_manual_hours),
        **info_fields,
    )
    session.add(info)
    await session.flush()  # 取 info.id

    session.add(TicketDetail(ticket_id=info.id, **detail_fields))
    session.add(TicketOrg(ticket_id=info.id, **org_fields))
    await session.flush()
    return info


async def mark_returned(
    session: AsyncSession,
    existing: TicketInfo,
    *,
    info_fields: dict[str, Any],
    detail_fields: dict[str, Any],
) -> TicketInfo:
    """退回单（FR-01）：编号已存在 → 更新原单内容(不变号) + return_count+1 + is_returned。

    末端转人工由 pipeline 依据 is_returned 强制处理（此处只标记 + 更新内容）。
    """
    existing.is_returned = True
    existing.return_count += 1
    for k, v in info_fields.items():
        setattr(existing, k, v)

    detail = (
        await session.execute(
            select(TicketDetail).where(
                TicketDetail.ticket_id == existing.id,
                TicketDetail.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if detail is not None:
        for k, v in detail_fields.items():
            setattr(detail, k, v)
    await session.flush()
    return existing


async def get_detail(session: AsyncSession, info_id: int) -> Optional[TicketDetail]:
    return (
        await session.execute(
            select(TicketDetail).where(TicketDetail.ticket_id == info_id, TicketDetail.is_deleted.is_(False))
        )
    ).scalar_one_or_none()


async def update_info(session: AsyncSession, info: TicketInfo, **fields) -> None:
    for k, v in fields.items():
        setattr(info, k, v)
    await session.flush()


async def update_detail(session: AsyncSession, info_id: int, **fields) -> None:
    detail = await get_detail(session, info_id)
    if detail:
        for k, v in fields.items():
            setattr(detail, k, v)
        await session.flush()


async def lookup_dev_owner(session: AsyncSession, func_module: str,
                           product_tag: Optional[str] = None) -> Optional[str]:
    """按 产品线+问题模块 查 t_module_owner 得责任人（责任田负责人，严格查表）。

    product_tag 给定时按 产品线+模块 精确匹配（同一模块名可能跨产品线，须带产品线约束）。
    """
    if not func_module:
        return None
    stmt = select(ModuleOwner).where(
        ModuleOwner.func_module == func_module, ModuleOwner.row_type == "module",
        ModuleOwner.is_active.is_(True), ModuleOwner.is_deleted.is_(False),
    )
    if product_tag:
        stmt = stmt.where(ModuleOwner.product_tag == product_tag)
    row = (await session.execute(stmt)).scalars().first()
    return row.dev_owner if row else None


async def module_candidates(session: AsyncSession) -> list[dict]:
    """打标候选：产品线/模块/触发词（喂 LLM；责任人不进 prompt）。"""
    rows = (await session.execute(
        select(ModuleOwner).where(ModuleOwner.is_active.is_(True), ModuleOwner.is_deleted.is_(False))
    )).scalars()
    return [{"product_tag": r.product_tag, "func_module": r.func_module, "trigger_words": r.trigger_words} for r in rows]


async def dedup_candidates(session: AsyncSession, *, product_tag: str, exclude_id: int, days: int = 120, limit: int = 50) -> list[TicketInfo]:
    """info-dedup 候选：同产品线、近 N 天、已成功答复(有 final_reply 且 done/closed)。"""
    if not product_tag:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await session.execute(
        select(TicketInfo).where(
            TicketInfo.ai_product_tag == product_tag,
            TicketInfo.id != exclude_id,
            TicketInfo.created_at >= since,
            TicketInfo.final_reply.is_not(None),
            TicketInfo.status.in_([TicketStatus.DONE.value, TicketStatus.CLOSED.value]),
            TicketInfo.is_deleted.is_(False),
        ).order_by(TicketInfo.created_at.desc()).limit(limit)
    )).scalars()
    return list(rows)


async def hub_candidates(session: AsyncSession, *, product_tag: str) -> list[TicketHub]:
    """hub-dedup 候选：同产品线、有 embedding 的【全量】研发单（含已关闭，应用层算余弦）。

    不再按时间窗/条数/状态截断——对该产品线历史 hub 全量比对，避免漏召回而重复建单。
    （量级很大时再切换 pgvector ANN 索引检索以保持性能。）
    """
    if not product_tag:
        return []
    rows = (await session.execute(
        select(TicketHub).where(
            TicketHub.product_tag == product_tag,
            TicketHub.embedding.is_not(None),
            TicketHub.is_deleted.is_(False),
        ).order_by(TicketHub.created_at.desc())
    )).scalars()
    return list(rows)
