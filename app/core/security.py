"""JWT 签发/解析 + RBAC 依赖。"""
from __future__ import annotations

from typing import Optional

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import BizException

ROLE_RANK = {"visitor": 0, "handler": 1, "admin": 2}


def issue_jwt(*, sub: str, name: str, role: str = "visitor") -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=settings.jwt_ttl_seconds)
    payload = {"sub": sub, "name": name, "role": role,
               "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_ttl_seconds


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise BizException(f"Token 无效或已过期: {e}", code=401)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise BizException("未提供认证 Token", code=401)
    return decode_jwt(authorization.removeprefix("Bearer ").strip())


def require_role(min_role: str):
    """依赖工厂：要求角色 >= min_role。"""
    threshold = ROLE_RANK.get(min_role, 0)

    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        if ROLE_RANK.get(user.get("role", "visitor"), 0) < threshold:
            raise BizException("您没有权限执行此操作", code=403)
        return user

    return _dep


async def verify_webhook_token(x_webhook_token: Optional[str] = Header(None),
                               access_token: Optional[str] = None,
                               token: Optional[str] = None) -> None:
    """webhook 鉴权：token 取自 X-Webhook-Token 头 或 查询参数 access_token/token，与配置一致即可。

    未配置 token（settings 为空）时放行——便于联调期来源系统直接推送。
    """
    if not settings.webhook_access_token:
        return
    provided = x_webhook_token or access_token or token
    if provided != settings.webhook_access_token:
        raise BizException("webhook 鉴权失败", code=401)
