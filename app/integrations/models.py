"""集成域 ORM：t_integration_log（第三方接口调用留痕，高写入）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class IntegrationLog(IdMixin, AuditMixin, Base):
    """KSM/智齿/agent/硅基流动/DeepSeek/飞书/Linear 等出站调用审计。"""

    __tablename__ = "t_integration_log"

    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    integration: Mapped[str] = mapped_column(String(32), nullable=False)     # ksm/zhichi/agent/...
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_summary: Mapped[Optional[str]] = mapped_column(Text)                # 脱敏+截断
    response_summary: Mapped[Optional[str]] = mapped_column(Text)
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    biz_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    error_msg: Mapped[Optional[str]] = mapped_column(String(512))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    retry_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
