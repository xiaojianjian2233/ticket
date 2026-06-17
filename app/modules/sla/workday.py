"""工作日计时：排除周末 + 法定节假日（t_holiday），支持调休补班。

is_workday: t_holiday 命中 holiday→休、workday→补班上班；否则按周末判断。
add_workday_hours: 从 start 起累加 N 小时，只在工作日消耗（非工作日不计时）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import HolidayDayType
from app.modules.sla.models import Holiday

BEIJING = timezone(timedelta(hours=8))


async def is_workday(session: AsyncSession, d: date) -> bool:
    row = (await session.execute(
        select(Holiday).where(Holiday.holiday_date == d, Holiday.is_deleted.is_(False))
    )).scalar_one_or_none()
    if row:
        return row.day_type == HolidayDayType.WORKDAY.value
    return d.weekday() < 5  # 周一~周五


async def add_workday_hours(session: AsyncSession, start: datetime, hours: float) -> datetime:
    """从 start 累加 hours 个"工作日小时"，跳过非工作日。"""
    cur = start.astimezone(BEIJING)
    remaining = float(hours)
    guard = 0
    while remaining > 0 and guard < 3650:
        guard += 1
        if await is_workday(session, cur.date()):
            next_midnight = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            avail = (next_midnight - cur).total_seconds() / 3600
            if avail >= remaining:
                return cur + timedelta(hours=remaining)
            remaining -= avail
            cur = next_midnight
        else:
            cur = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return cur
