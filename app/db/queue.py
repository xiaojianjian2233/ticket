"""t_task_queue：PG 表队列模型 + 入队 / SKIP LOCKED 抢锁 / 重试封装。

不引 Redis/Celery：用 PG `SELECT ... FOR UPDATE SKIP LOCKED` 实现多 worker 并发抢锁。
重试退避走 available_at；retry_count > max_retry → abandoned（worker 侧自动转人工）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import TaskStatus, TaskType
from app.db.base import AuditMixin, Base, IdMixin


class TaskQueue(IdMixin, AuditMixin, Base):
    __tablename__ = "t_task_queue"

    task_type: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TaskStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retry: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dedup_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue(
    session: AsyncSession,
    task_type: Union[TaskType, str],
    payload: dict[str, Any],
    *,
    priority: int = 0,
    max_retry: int = 3,
    dedup_key: Optional[str] = None,
    delay_sec: int = 0,
) -> TaskQueue:
    """入队一个任务。dedup_key 命中已存在 pending/processing 任务则跳过（返回该任务，幂等）。"""
    if dedup_key:
        existing = (
            await session.execute(
                select(TaskQueue).where(
                    TaskQueue.dedup_key == dedup_key,
                    TaskQueue.status.in_([TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]),
                    TaskQueue.is_deleted.is_(False),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    task = TaskQueue(
        task_type=str(task_type),
        payload=payload,
        status=TaskStatus.PENDING.value,
        priority=priority,
        max_retry=max_retry,
        dedup_key=dedup_key,
        available_at=_now() + timedelta(seconds=delay_sec) if delay_sec else _now(),
    )
    session.add(task)
    await session.flush()
    return task


async def claim_next(
    session: AsyncSession,
    worker_id: str,
    *,
    task_types: Optional[list[str]] = None,
) -> Optional[TaskQueue]:
    """抢占一个可执行任务：FOR UPDATE SKIP LOCKED，置 processing + locked。

    调用方需在同一事务内执行/提交。返回 None 表示当前无可取任务。
    """
    stmt = (
        select(TaskQueue)
        .where(
            TaskQueue.status == TaskStatus.PENDING.value,
            TaskQueue.available_at <= _now(),
            TaskQueue.is_deleted.is_(False),
        )
        .order_by(TaskQueue.priority.desc(), TaskQueue.available_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if task_types:
        stmt = stmt.where(TaskQueue.task_type.in_(task_types))
    task = (await session.execute(stmt)).scalar_one_or_none()
    if task is None:
        return None
    task.status = TaskStatus.PROCESSING.value
    task.locked_at = _now()
    task.locked_by = worker_id
    await session.flush()
    return task


async def mark_done(session: AsyncSession, task: TaskQueue) -> None:
    task.status = TaskStatus.DONE.value
    await session.flush()


async def mark_failed(session: AsyncSession, task: TaskQueue, error: str, *, backoff_base_sec: int = 5) -> bool:
    """失败处置：未超重试上限→退避重排；超限→abandoned。返回 True=已 abandoned。"""
    task.retry_count += 1
    task.last_error = error[:1024]
    if task.retry_count > task.max_retry:
        task.status = TaskStatus.ABANDONED.value
        await session.flush()
        return True
    # 指数退避：base * 2^(retry-1)
    delay = backoff_base_sec * (2 ** (task.retry_count - 1))
    task.status = TaskStatus.PENDING.value
    task.locked_at = None
    task.locked_by = None
    task.available_at = _now() + timedelta(seconds=delay)
    await session.flush()
    return False


async def suspend(session: AsyncSession, task: TaskQueue, reason: str) -> None:
    """关键依赖全挂：挂起不消费，不计重试。探活恢复后由监控重置为 pending。"""
    task.status = TaskStatus.SUSPENDED.value
    task.last_error = reason[:1024]
    task.locked_at = None
    task.locked_by = None
    await session.flush()


async def requeue(session: AsyncSession, task_id: int) -> None:
    """后台手动重入队（abandoned/suspended → pending，重置重试）。"""
    task = await session.get(TaskQueue, task_id)
    if task is None:
        return
    task.status = TaskStatus.PENDING.value
    task.retry_count = 0
    task.locked_at = None
    task.locked_by = None
    task.available_at = _now()
    await session.flush()
