"""scheduler 进程（单副本）：SLA 扫描(每日北京08:00) / 观察期 / 队列监控 / 节假日同步。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.modules.sla import holiday_service, observe_scanner, queue_monitor, sla_scanner
from app.modules.ticket import linear_sync

logger = logging.getLogger("ticket_hub.scheduler")
BEIJING = timezone(timedelta(hours=8))


async def _run(scan_fn) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            await scan_fn(session)
            await session.commit()
        except Exception:  # noqa: BLE001 — 定时任务不因单次异常退出
            logger.exception("scheduled job failed: %s", getattr(scan_fn, "__module__", scan_fn))
            await session.rollback()


async def sla_job() -> None:
    await _run(sla_scanner.scan)


async def observe_job() -> None:
    await _run(observe_scanner.scan)


async def queue_job() -> None:
    await _run(queue_monitor.scan)


async def linear_sync_job() -> None:
    await _run(linear_sync.poll_open_hubs)


async def holiday_job() -> None:
    sm = get_sessionmaker()
    year = datetime.now(BEIJING).year
    async with sm() as session:
        try:
            await holiday_service.sync_year(session, year)
            await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("holiday sync failed")


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=BEIJING)
    sched.add_job(sla_job, "cron", hour=8, minute=0, id="sla_scan")          # 每日北京08:00 双SLA
    sched.add_job(observe_job, "cron", hour=8, minute=10, id="observe_scan")  # 观察期到期关闭
    sched.add_job(queue_job, "interval", minutes=5, id="queue_monitor")       # 队列健康
    sched.add_job(linear_sync_job, "interval", minutes=10, id="linear_sync")  # Linear 状态拉取兜底
    sched.add_job(holiday_job, "cron", hour=3, minute=0, id="holiday_sync")   # 每日刷新节假日
    return sched


async def main() -> None:
    setup_logging(settings.log_level)
    await holiday_job()  # 启动先同步当年节假日
    sched = build_scheduler()
    sched.start()
    logger.info("scheduler started (Asia/Shanghai +8): sla@08:00 observe@08:10 queue@5m holiday@03:00 linear@10m")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
