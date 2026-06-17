"""入站 webhook 路由：只做鉴权 + 入队，重活交 worker（避免阻塞来源系统回调）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TaskType
from app.core.response import success
from app.core.security import verify_webhook_token
from app.db import queue
from app.db.session import get_db
from app.modules.intake.schema import KsmWebhookIn, extract_zhichi_source_id

router = APIRouter(tags=["intake"])


@router.post("/webhook/ksm", dependencies=[Depends(verify_webhook_token)])
async def ksm_webhook(body: KsmWebhookIn, session: AsyncSession = Depends(get_db)):
    """KSM 推送：存 noticeNum/subscribeNum/billId → 入队 ksm_intake → 立即返回（worker 再拉全量）。"""
    await queue.enqueue(
        session,
        TaskType.KSM_INTAKE,
        {"notice_num": body.notice_num, "subscribe_num": body.subscribe_num, "bill_id": body.bill_id},
        dedup_key=f"ksm_intake:{body.notice_num}",
    )
    await session.commit()
    return success({"queued": True})


@router.post("/webhook/zhichi", dependencies=[Depends(verify_webhook_token)])
async def zhichi_webhook(raw: dict[str, Any], session: AsyncSession = Depends(get_db)):
    """智齿推送完整工单 → 入队 sync_ticket（worker 归一+幂等+入库）。"""
    source_id = extract_zhichi_source_id(raw)
    dedup_key = f"sync_ticket:zhichi:{source_id}" if source_id else None
    await queue.enqueue(session, TaskType.SYNC_TICKET, {"raw": raw}, dedup_key=dedup_key)
    await session.commit()
    return success({"queued": True})
