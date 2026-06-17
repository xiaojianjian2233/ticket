"""用户仓储：t_users 按 feishu_uid 同步 + 角色管理。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.feishu.models import User


def _is_bootstrap_admin(name: str) -> bool:
    """配置的管理员名单(默认李志坚)登录自动授予 admin。"""
    admins = [n.strip() for n in (settings.admin_names or "").split(",") if n.strip()]
    return bool(name) and name in admins


async def get_by_feishu_uid(session: AsyncSession, feishu_uid: str) -> Optional[User]:
    return (await session.execute(
        select(User).where(User.feishu_uid == feishu_uid, User.is_deleted.is_(False))
    )).scalar_one_or_none()


async def get_or_create(session: AsyncSession, *, feishu_uid: str, name: str,
                        email: str = "", mobile: str = "", avatar_url: str = "") -> User:
    user = await get_by_feishu_uid(session, feishu_uid)
    role = "admin" if _is_bootstrap_admin(name) else "visitor"
    if user is None:
        user = User(feishu_uid=feishu_uid, name=name or feishu_uid, email=email, mobile=mobile,
                    avatar_url=avatar_url, role=role, is_active=True, created_by="sso")
        session.add(user)
    else:
        user.name = name or user.name
        if email:
            user.email = email
        if avatar_url:
            user.avatar_url = avatar_url
        if _is_bootstrap_admin(user.name) and user.role != "admin":
            user.role = "admin"   # 既有李志坚账号登录时也提权
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    return user


async def list_users(session: AsyncSession, *, role: Optional[str] = None, keyword: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> tuple[list[User], int]:
    stmt = select(User).where(User.is_deleted.is_(False))
    if role:
        stmt = stmt.where(User.role == role)
    if keyword:
        stmt = stmt.where(User.name.ilike(f"%{keyword}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars()
    return list(rows), total


async def update_user(session: AsyncSession, user_id: int, *, role: Optional[str] = None,
                      is_active: Optional[bool] = None) -> Optional[User]:
    user = await session.get(User, user_id)
    if user is None:
        return None
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    await session.flush()
    return user
