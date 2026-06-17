"""worker 进程：消费 t_task_queue 跑流水线。

设计要点：
- 抢锁与处理分两个事务：先 claim+commit（任务置 processing，防其他 worker 重复抢），
  再独立事务处理；失败时另开事务 mark_failed，保证状态不丢。
- 未实现的 handler 抛 NotImplementedError → 记 warning 后 noop-done（不耗重试变 abandoned）。
- 其它异常 → mark_failed（退避重试 ≤ max_retry；超限 abandoned，TODO 自动转人工+飞书告警）。
- 依赖全挂（agent+DeepSeek）→ 挂起不消费（TODO：探活开关），不在此实现。
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import traceback
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.enums import TaskType
from app.core.logging import new_trace_id, set_trace_id, setup_logging
from app.core.config import settings
from app.db import queue
from app.db.queue import TaskQueue
from app.db.session import get_sessionmaker

logger = logging.getLogger("ticket_hub.worker")

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
POLL_INTERVAL_SEC = 2.0

TaskHandler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


# ----------------------- 任务 handler（业务实现待接入） -----------------------
async def handle_ksm_intake(session: AsyncSession, payload: dict[str, Any]) -> None:
    """KSM：subscribeCallback(单次) → normalize_ksm → 幂等/退回 → 入库 → 入队 run_pipeline。"""
    from app.modules.intake.service import process_ksm_intake

    await process_ksm_intake(session, payload["notice_num"],
                             subscribe_num=payload.get("subscribe_num"), bill_id=payload.get("bill_id"))


async def handle_sync_ticket(session: AsyncSession, payload: dict[str, Any]) -> None:
    """智齿：normalize(raw) → 幂等/退回 → 入库 t_ticket_info/detail/org → 入队 run_pipeline。"""
    from app.modules.intake.service import process_zhichi_intake  # 延迟导入避免循环依赖

    await process_zhichi_intake(session, payload["raw"])


async def handle_run_pipeline(session: AsyncSession, payload: dict[str, Any]) -> None:
    """跑主流水线 S1~S13。"""
    from app.pipeline.runner import run_pipeline  # 延迟导入，避免循环依赖

    info_id = int(payload["info_id"])
    set_trace_id(payload.get("trace_id") or new_trace_id())
    await run_pipeline(session, info_id, payload.get("trace_id") or new_trace_id())


async def handle_writeback(session: AsyncSession, payload: dict[str, Any]) -> None:
    """回写来源系统（KSM handleKsmOrder / 智齿 save_ticket_reply）失败重试通道。"""
    # TODO(writeback): 接入 writeback_service。
    raise NotImplementedError("handle_writeback")


HANDLERS: dict[str, TaskHandler] = {
    TaskType.KSM_INTAKE.value: handle_ksm_intake,
    TaskType.SYNC_TICKET.value: handle_sync_ticket,
    TaskType.RUN_PIPELINE.value: handle_run_pipeline,
    TaskType.WRITEBACK.value: handle_writeback,
}


# ----------------------- 消费循环 -----------------------
async def process_once(sm: async_sessionmaker[AsyncSession]) -> bool:
    """处理一个任务。返回 True 表示取到并处理了任务，False 表示当前队列为空。"""
    # 事务1：抢锁 + 提交（置 processing，防重复抢）
    async with sm() as session:
        task = await queue.claim_next(session, WORKER_ID, task_types=list(HANDLERS))
        if task is None:
            await session.commit()
            return False
        task_id, task_type, payload = task.id, task.task_type, dict(task.payload)
        await session.commit()

    handler = HANDLERS.get(task_type)
    # 事务2：处理
    try:
        async with sm() as session:
            await handler(session, payload)
            t = await session.get(TaskQueue, task_id)
            await queue.mark_done(session, t)
            await session.commit()
        logger.info("task done: id=%s type=%s", task_id, task_type)
    except NotImplementedError as exc:
        # 桩 handler：记 warning 后 noop-done，不耗重试
        async with sm() as session:
            t = await session.get(TaskQueue, task_id)
            await queue.mark_done(session, t)
            await session.commit()
        logger.warning("task handler not implemented, noop-done: id=%s type=%s (%s)", task_id, task_type, exc)
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
        async with sm() as session:
            t = await session.get(TaskQueue, task_id)
            abandoned = await queue.mark_failed(session, t, err)
            await session.commit()
        if abandoned:
            # TODO(IF-03): abandoned → 自动 pending_manual + 飞书告警
            logger.error("task ABANDONED: id=%s type=%s\n%s", task_id, task_type, err)
        else:
            logger.error("task failed, will retry: id=%s type=%s", task_id, task_type)
    return True


async def main_loop() -> None:
    setup_logging(settings.log_level)
    sm = get_sessionmaker()
    logger.info("worker started: %s", WORKER_ID)
    while True:
        try:
            had_task = await process_once(sm)
        except Exception:  # noqa: BLE001 — 循环自身永不退出
            logger.exception("worker loop error")
            had_task = False
        if not had_task:
            await asyncio.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    asyncio.run(main_loop())
