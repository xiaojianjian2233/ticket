"""节假日同步：国务院节假日 API → t_holiday（降级用本地数据）。

API 地址走配置（L11 联调）；不可达时不报错，依赖已有 t_holiday + 周末兜底。
常见免费源 timor.tech: GET https://timor.tech/api/holiday/year/{year} → {holiday:{"01-01":{holiday:true,name,..}}}
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import HolidayDayType
from app.integrations.base import HttpClient
from app.modules.sla.models import Holiday

logger = logging.getLogger("ticket_hub.holiday")
_API = "https://timor.tech/api/holiday/year"


async def sync_year(session: AsyncSession, year: int) -> int:
    """拉取某年节假日写入 t_holiday（幂等）。失败返回 0（降级周末兜底）。"""
    client = HttpClient(integration="holiday", default_timeout=15.0, default_retries=1)
    try:
        data = await client.get(f"{_API}/{year}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("节假日 API 不可达，降级本地/周末兜底: %s", exc)
        return 0
    finally:
        await client.aclose()
    holidays = (data or {}).get("holiday") or {}
    n = 0
    for _key, v in holidays.items():
        try:
            d = date.fromisoformat(v["date"]) if "date" in v else None
        except Exception:  # noqa: BLE001
            d = None
        if d is None:
            continue
        day_type = HolidayDayType.HOLIDAY.value if v.get("holiday") else HolidayDayType.WORKDAY.value
        exists = (await session.execute(select(Holiday).where(Holiday.holiday_date == d))).scalar_one_or_none()
        if exists:
            exists.day_type = day_type
            exists.name = v.get("name")
        else:
            session.add(Holiday(holiday_date=d, day_type=day_type, name=v.get("name"), year=year, source="gov_api"))
            n += 1
    await session.flush()
    return n
