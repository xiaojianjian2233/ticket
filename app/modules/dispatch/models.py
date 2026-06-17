"""派单域 ORM：t_dispatch_assignee / t_dispatch_config / t_dispatch_log。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class DispatchRule(IdMixin, AuditMixin, Base):
    """派单规则：收到工单后据此判断处理人分配。同一(产品线,模块)在同类型(正式/溢出)规则中唯一。"""

    __tablename__ = "t_dispatch_rule"

    code: Mapped[str] = mapped_column(String(32), nullable=False)             # RULE_001
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(16), nullable=False, default="正式规则")  # 正式规则/溢出规则
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sla: Mapped[Optional[list]] = mapped_column(JSONB)                          # 触发服务等级名称[]
    sources: Mapped[Optional[list]] = mapped_column(JSONB)                      # 工单来源[]
    products: Mapped[Optional[list]] = mapped_column(JSONB)                     # 产品线[]
    modules: Mapped[Optional[list]] = mapped_column(JSONB)                      # 问题模块[]
    dispatch_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="按数量")  # 按数量/按比例
    assignees: Mapped[Optional[list]] = mapped_column(JSONB)                    # [{name,value}]
    fallback: Mapped[Optional[str]] = mapped_column(String(64))                 # 兜底指派人
    overflow_rule_id: Mapped[Optional[int]] = mapped_column(BigInteger)         # 正式规则关联的溢出规则
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DispatchAssignee(IdMixin, AuditMixin, Base):
    """派单配额名单（主+溢出同表，按 alloc_value 配比派单）。"""

    __tablename__ = "t_dispatch_assignee"

    assignee_name: Mapped[str] = mapped_column(String(64), nullable=False)
    feishu_uid: Mapped[Optional[str]] = mapped_column(String(64))               # 群内 @ 用
    alloc_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)   # 配额权重
    tier: Mapped[str] = mapped_column(String(12), nullable=False, default="main")  # main/overflow
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DispatchConfig(IdMixin, AuditMixin, Base):
    """派单兜底配置（key-value，存 default_assignee 单点兜底）。"""

    __tablename__ = "t_dispatch_config"

    config_key: Mapped[str] = mapped_column(String(64), nullable=False)      # default_assignee/default_assignee_uid
    config_value: Mapped[Optional[str]] = mapped_column(String(255))
    remark: Mapped[Optional[str]] = mapped_column(String(255))


class DispatchLog(IdMixin, AuditMixin, Base):
    """派单留痕（配额已分配数统计依据）。"""

    __tablename__ = "t_dispatch_log"

    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    branch: Mapped[Optional[str]] = mapped_column(String(16))                   # B/C/returned/not_takeover
    tier_hit: Mapped[str] = mapped_column(String(12), nullable=False)        # main/overflow/default/broadcast
    assignee_name: Mapped[Optional[str]] = mapped_column(String(64))
    assignee_uid: Mapped[Optional[str]] = mapped_column(String(64))
