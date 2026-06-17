"""入站编排：归一 → 幂等/退回(FR-01) → 建单/更新原单 → 入队 run_pipeline。

智齿 webhook 自带全量；KSM 先 subscribeCallback(单次)拉全量再归一。调用方(worker handler)提交事务。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import Source, TaskType
from app.core.logging import new_trace_id
from app.db import queue
from app.integrations.ksm_client import get_ksm
from app.modules.intake.normalize import NormalizedTicket, normalize_ksm, normalize_zhichi
from app.modules.ticket import repository as ticket_repo

logger = logging.getLogger("ticket_hub.intake")


async def _persist_and_enqueue(session: AsyncSession, norm: NormalizedTicket) -> int:
    """幂等/退回 → 建单或更新 → 入队 run_pipeline。返回 info_id。"""
    if not norm.source_id:
        raise ValueError(f"{norm.source} raw 缺少工单编号，无法入库")
    existing = await ticket_repo.get_by_source(session, norm.source, norm.source_id)
    if existing is not None:
        await ticket_repo.mark_returned(session, existing, info_fields=norm.info, detail_fields=norm.detail)
        info_id = existing.id
        logger.info("%s 退回单(编号已存在): source_id=%s info_id=%s 第%d次", norm.source, norm.source_id, info_id, existing.return_count)
    else:
        info = await ticket_repo.create_ticket(
            session, source=norm.source, source_id=norm.source_id, has_attachment=norm.has_attachment,
            info_fields=norm.info, detail_fields=norm.detail, org_fields=norm.org)
        info_id = info.id
        logger.info("%s 新建工单: source_id=%s info_id=%s no=%s", norm.source, norm.source_id, info_id, info.ticket_no)
    # TODO(storage): norm.attachment_urls → 转存 MinIO → t_attachment(scope=ticket)
    trace_id = new_trace_id()
    await queue.enqueue(session, TaskType.RUN_PIPELINE, {"info_id": info_id, "trace_id": trace_id},
                        dedup_key=f"run_pipeline:{info_id}")
    return info_id


async def process_zhichi_intake(session: AsyncSession, raw: dict) -> int:
    """智齿 sync_ticket：webhook 自带全量 raw。"""
    return await _persist_and_enqueue(session, normalize_zhichi(raw))


async def process_ksm_intake(session: AsyncSession, notice_num: str, *,
                             subscribe_num: Optional[str] = None, bill_id: Optional[str] = None) -> int:
    """KSM ksm_intake：subscribeCallback(noticeNum+subscribeNum+billId)拉全量 → 归一 → 入库。"""
    raw = await get_ksm().subscribe_callback(notice_num, subscribe_num=subscribe_num, bill_id=bill_id)
    if not raw:
        raise ValueError(f"KSM subscribeCallback 空返回 notice_num={notice_num}")
    norm = normalize_ksm(raw)
    norm.org["ksm_notice_num"] = notice_num          # 存通知编号，接管后重拉详情用
    return await _persist_and_enqueue(session, norm)
