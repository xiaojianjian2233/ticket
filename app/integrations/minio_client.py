"""MinIO 客户端：附件/图片转存 + public_url 生成。

MinIO SDK 同步，异步层用 asyncio.to_thread 包装（见 storage service）。
对外访问统一拼 settings.minio_public_base（经 nginx 代理）。
本地 9000 未放通——storage 相关测试在服务器跑。
"""
from __future__ import annotations

import io
from typing import Optional

from app.core.config import settings

_client = None


def _minio():
    global _client
    if _client is None:
        from minio import Minio  # 延迟导入
        host = settings.minio_endpoint
        secure = host.startswith("https") or settings.app_env == "prod"
        _client = Minio(
            host.replace("https://", "").replace("http://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
    return _client


def ensure_bucket() -> None:
    c = _minio()
    if not c.bucket_exists(settings.minio_bucket):
        c.make_bucket(settings.minio_bucket)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """上传字节，返回 public_url。"""
    ensure_bucket()
    _minio().put_object(settings.minio_bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return public_url(key)


def public_url(key: str) -> str:
    base = settings.minio_public_base.rstrip("/")
    return f"{base}/{settings.minio_bucket}/{key}"
