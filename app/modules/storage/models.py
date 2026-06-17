"""附件域 ORM：t_attachment（统一存 MinIO）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class Attachment(IdMixin, AuditMixin, Base):
    """附件/图片：scope=ticket/faq/hub，回写一律给 public_url 链接。"""

    __tablename__ = "t_attachment"

    scope: Mapped[str] = mapped_column(String(8), nullable=False)             # ticket/faq/hub
    ref_id: Mapped[int] = mapped_column(BigInteger, nullable=False)           # info/faq/hub 主键
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))             # 原始下载源
    minio_bucket: Mapped[Optional[str]] = mapped_column(String(64))
    minio_key: Mapped[Optional[str]] = mapped_column(String(512))
    public_url: Mapped[Optional[str]] = mapped_column(String(1024))            # 对外访问 URL
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    mime: Mapped[Optional[str]] = mapped_column(String(128))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    is_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    download_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error: Mapped[Optional[str]] = mapped_column(String(512))
