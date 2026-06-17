"""Skill 管理域 ORM：t_skill_md / t_skill_md_history + t_operation_log（配置审计）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class SkillMd(IdMixin, AuditMixin, Base):
    """可编辑 SKILL.md（DB 为权威源，runtime 缓存+version 失效热加载）。"""

    __tablename__ = "t_skill_md"

    skill_name: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(8), nullable=False, default="llm")   # llm/code
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frontmatter: Mapped[Optional[dict]] = mapped_column(JSONB)                   # name/description/model/editable
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SkillMdHistory(IdMixin, AuditMixin, Base):
    """SKILL.md 版本历史（回滚）。"""

    __tablename__ = "t_skill_md_history"

    skill_name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    frontmatter: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(String(512))


class OperationLog(IdMixin, AuditMixin, Base):
    """配置审计（SKILL.md 编辑 / 派单 / 用户 / 模块映射 等前后值，长期保留）。"""

    __tablename__ = "t_operation_log"

    operator_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_name: Mapped[Optional[str]] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)      # skill_md/dispatch_assignee/...
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16), nullable=False)           # create/update/delete/rollback
    before_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    after_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    remark: Mapped[Optional[str]] = mapped_column(String(512))
