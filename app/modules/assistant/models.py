"""智能助手域 ORM：t_assistant_log（NL2SQL 查询 / 对话提单记录）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class AssistantLog(IdMixin, AuditMixin, Base):
    """助手记录：含生成 SQL / 护栏结果 / PII 脱敏标记（90 天保留）。"""

    __tablename__ = "t_assistant_log"

    user_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    user_role: Mapped[Optional[str]] = mapped_column(String(16))
    session_id: Mapped[Optional[str]] = mapped_column(String(64))
    nl_query: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[Optional[str]] = mapped_column(Text)
    sql_guard_pass: Mapped[Optional[bool]] = mapped_column(Boolean)
    result_rows: Mapped[Optional[int]] = mapped_column(Integer)
    pii_masked: Mapped[Optional[bool]] = mapped_column(Boolean)
    op_type: Mapped[str] = mapped_column(String(16), nullable=False, default="query")  # query/submit
    error_msg: Mapped[Optional[str]] = mapped_column(String(512))
