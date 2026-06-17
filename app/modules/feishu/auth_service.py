"""飞书 SSO 登录：OAuth 授权码 → user_info → 同步 t_users → 签发 JWT。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.security import issue_jwt
from app.integrations.feishu_client import get_feishu
from app.modules.feishu import repository as user_repo


def login_url(state: str = "") -> str:
    return get_feishu().authorize_url(state=state)


async def callback(session: AsyncSession, code: str) -> dict:
    """code 换 JWT + 同步用户。新用户默认 visitor；禁用拒登。"""
    info = await get_feishu().exchange_code(code)
    feishu_uid = info.get("open_id") or info.get("union_id") or info.get("user_id")
    if not feishu_uid:
        raise BizException("飞书未返回用户标识", code=502)
    user = await user_repo.get_or_create(
        session, feishu_uid=feishu_uid, name=info.get("name", ""),
        email=info.get("email", ""), mobile=info.get("mobile", ""), avatar_url=info.get("avatar_url", ""))
    if not user.is_active:
        raise BizException("账号已禁用", code=403)
    token, ttl = issue_jwt(sub=str(user.id), name=user.name, role=user.role)
    return {"access_token": token, "expires_in": ttl, "user": _user_view(user)}


def _user_view(user) -> dict:
    return {"id": user.id, "feishuUid": user.feishu_uid, "name": user.name,
            "email": user.email, "role": user.role, "avatarUrl": user.avatar_url}
