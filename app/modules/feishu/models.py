"""认证域 ORM：t_users（飞书 SSO 用户 + RBAC 三级）。"""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class User(IdMixin, AuditMixin, Base):
    """飞书 SSO 用户；新用户默认 visitor，禁用拒登。"""

    __tablename__ = "t_users"

    feishu_uid: Mapped[Optional[str]] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(128))
    mobile: Mapped[Optional[str]] = mapped_column(String(32))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    employee_no: Mapped[Optional[str]] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="visitor")  # admin/handler/visitor
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
