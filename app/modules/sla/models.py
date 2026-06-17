"""SLA 域 ORM：t_sla_log（双SLA超时留痕）/ t_holiday（工作日计时）。"""
from __future__ import annotations

from typing import Optional

from datetime import date

from sqlalchemy import Boolean, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class SlaLog(IdMixin, AuditMixin, Base):
    """SLA 超时通报记录（按 ref + notify_mark 去重）。"""

    __tablename__ = "t_sla_log"

    sla_type: Mapped[str] = mapped_column(String(8), nullable=False)         # manual/rd
    ref_type: Mapped[str] = mapped_column(String(8), nullable=False)         # info/hub
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(64))
    notify_date: Mapped[date] = mapped_column(Date, nullable=False)
    notify_mark: Mapped[str] = mapped_column(String(16), nullable=False)     # 2026-06-10-08:00
    overdue_hours: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Holiday(IdMixin, AuditMixin, Base):
    """节假日（国务院 API 同步 + 手动兜底）；day_type 同时标法定休与调休补班。"""

    __tablename__ = "t_holiday"

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_type: Mapped[str] = mapped_column(String(12), nullable=False)        # holiday/workday(调休补班)
    name: Mapped[Optional[str]] = mapped_column(String(64))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="gov_api")  # gov_api/manual
