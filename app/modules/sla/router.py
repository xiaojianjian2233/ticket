"""SLA 监控路由：超时列表/概览/通报历史/系统告警/abandoned 重入队。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TaskStatus
from app.core.response import page, success
from app.core.security import get_current_user, require_role
from app.db import queue
from app.db.queue import TaskQueue
from app.db.session import get_db
from app.modules.sla.models import SlaLog

router = APIRouter(prefix="/api/v1/sla", tags=["sla"])


@router.get("")
async def sla_list(sla_type: Optional[str] = None, owner: Optional[str] = None, page_no: int = 1, page_size: int = 20,
                   _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(SlaLog).where(SlaLog.is_deleted.is_(False))
    if sla_type:
        stmt = stmt.where(SlaLog.sla_type == sla_type)
    if owner:
        stmt = stmt.where(SlaLog.owner == owner)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(SlaLog.id.desc()).offset((page_no - 1) * page_size).limit(page_size))).scalars()
    items = [{"slaType": r.sla_type, "refType": r.ref_type, "refId": r.ref_id, "owner": r.owner,
              "notifyDate": r.notify_date, "overdueHours": float(r.overdue_hours) if r.overdue_hours else None,
              "notifyMark": r.notify_mark} for r in rows]
    return success(page(items, total, page_no, page_size))


@router.get("/overview")
async def overview(_: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    total = (await session.execute(select(func.count()).select_from(SlaLog))).scalar_one()
    by_owner = (await session.execute(
        select(SlaLog.owner, func.count()).group_by(SlaLog.owner).order_by(func.count().desc()).limit(10)
    )).all()
    return success({"breachTotal": total, "topOwners": [{"owner": o, "count": c} for o, c in by_owner]})


@router.get("/notify-log")
async def notify_log(date: Optional[str] = None, owner: Optional[str] = None, page_no: int = 1, page_size: int = 20,
                     _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(SlaLog).where(SlaLog.notified.is_(True))
    if owner:
        stmt = stmt.where(SlaLog.owner == owner)
    rows = (await session.execute(stmt.order_by(SlaLog.id.desc()).offset((page_no - 1) * page_size).limit(page_size))).scalars()
    return success({"items": [{"owner": r.owner, "notifyMark": r.notify_mark, "slaType": r.sla_type} for r in rows]})


@router.get("/system-alerts")
async def system_alerts(_: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    pending = (await session.execute(select(func.count()).select_from(TaskQueue).where(TaskQueue.status == TaskStatus.PENDING.value))).scalar_one()
    abandoned = (await session.execute(select(TaskQueue).where(TaskQueue.status == TaskStatus.ABANDONED.value).limit(100))).scalars()
    return success({"pending": pending,
                    "abandoned": [{"id": t.id, "taskType": t.task_type, "lastError": t.last_error} for t in abandoned]})


@router.post("/requeue-abandoned/{task_id}")
async def requeue_abandoned(task_id: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    await queue.requeue(session, task_id)
    await session.commit()
    return success({"ok": True})
