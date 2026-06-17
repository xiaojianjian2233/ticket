"""AI 域 ORM：t_skill_log（流水线每步审计，harness 统一写）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class SkillLog(IdMixin, AuditMixin, Base):
    """每步 Skill/流水线执行留痕（可解释/可追溯/可重试/可调优）。"""

    __tablename__ = "t_skill_log"

    trace_id: Mapped[Optional[str]] = mapped_column(String(64))
    ticket_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    hub_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    skill_name: Mapped[str] = mapped_column(String(64), nullable=False)      # routable/tagging/...
    step_no: Mapped[Optional[str]] = mapped_column(String(16))                  # S1/S2...
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")  # ok/failed/skipped
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB)                  # 信封 fields
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(32))               # claude/deepseek/-
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_msg: Mapped[Optional[str]] = mapped_column(String(1024))
