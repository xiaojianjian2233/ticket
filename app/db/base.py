"""ORM Base + 公共审计字段 mixin（每表统一 5 字段）。"""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdMixin:
    """统一 BIGSERIAL 主键。"""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class AuditMixin:
    """统一审计 5 字段：is_deleted / created_at / updated_at / created_by / updated_by。"""

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
