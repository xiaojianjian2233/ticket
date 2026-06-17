"""认证 & 用户路由：飞书 SSO 登录 + 当前用户 + 用户管理(admin)。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import page, success
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.modules.feishu import auth_service
from app.modules.feishu import repository as user_repo

router = APIRouter(tags=["auth"])


@router.get("/api/v1/auth/feishu/login")
async def feishu_login(state: str = ""):
    return success({"authorize_url": auth_service.login_url(state)})


@router.get("/api/v1/auth/feishu/callback")
async def feishu_callback(code: str, session: AsyncSession = Depends(get_db)):
    data = await auth_service.callback(session, code)
    await session.commit()
    return success(data)


@router.get("/api/v1/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return success({"id": user.get("sub"), "name": user.get("name"), "role": user.get("role")})


@router.get("/api/v1/users")
async def list_users(role: Optional[str] = None, keyword: Optional[str] = None, page_no: int = 1,
                     page_size: int = 20, _: dict = Depends(require_role("admin")),
                     session: AsyncSession = Depends(get_db)):
    rows, total = await user_repo.list_users(session, role=role, keyword=keyword, page=page_no, page_size=page_size)
    items = [{"id": u.id, "name": u.name, "feishuUid": u.feishu_uid, "email": u.email,
              "role": u.role, "isActive": u.is_active, "lastLoginAt": u.last_login_at} for u in rows]
    return success(page(items, total, page_no, page_size))


class UpdateUserIn(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.put("/api/v1/users/{user_id}")
async def update_user(user_id: int, body: UpdateUserIn, _: dict = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_db)):
    user = await user_repo.update_user(session, user_id, role=body.role, is_active=body.is_active)
    await session.commit()
    if user is None:
        return success(None, message="用户不存在")
    return success({"id": user.id, "role": user.role, "isActive": user.is_active})
