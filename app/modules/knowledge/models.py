"""知识库域 ORM：t_faq / t_faq_review。"""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class Faq(IdMixin, AuditMixin, Base):
    """FAQ 检索主库（pgvector）。检索过滤 rejected。"""

    __tablename__ = "t_faq"

    faq_no: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)            # 应用层限 ≤20
    content: Mapped[str] = mapped_column(String(512), nullable=False)         # 应用层限 ≤300
    product_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ticket_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    embedding: Mapped[Optional[list]] = mapped_column(JSONB)  # bge-m3 float数组(应用层算余弦)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending_review")
    review_reason: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FaqReview(IdMixin, AuditMixin, Base):
    """FAQ 审核记录 1:N（四维 + 结果）。"""

    __tablename__ = "t_faq_review"

    faq_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)           # approved/rejected
    dim_sensitive: Mapped[Optional[bool]] = mapped_column(Boolean)               # 敏感信息残留
    dim_factual: Mapped[Optional[bool]] = mapped_column(Boolean)                 # 事实性
    dim_internal: Mapped[Optional[bool]] = mapped_column(Boolean)                # 内部细节泄露
    dim_quality: Mapped[Optional[bool]] = mapped_column(Boolean)                 # 表达质量
    reject_dims: Mapped[Optional[str]] = mapped_column(String(128))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False, default="deepseek")
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
