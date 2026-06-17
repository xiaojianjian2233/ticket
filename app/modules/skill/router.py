"""Skill 管理路由（仅 admin）：列表/取/编辑/回滚/预览。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.security import require_role
from app.db.session import get_db
from app.modules.skill import service

router = APIRouter(prefix="/api/v1/skills", tags=["skill"])


@router.get("")
async def list_skills(_: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    return success({"items": await service.list_skills(session)})


@router.get("/{name}")
async def get_skill(name: str, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    return success(await service.get_skill(session, name))


class EditIn(BaseModel):
    content_md: str


@router.put("/{name}")
async def edit_skill(name: str, body: EditIn, user: dict = Depends(require_role("admin")),
                     session: AsyncSession = Depends(get_db)):
    data = await service.edit_skill(session, name, body.content_md, str(user.get("sub")))
    await session.commit()
    return success(data)


class RollbackIn(BaseModel):
    version: int


@router.post("/{name}/rollback")
async def rollback(name: str, body: RollbackIn, user: dict = Depends(require_role("admin")),
                   session: AsyncSession = Depends(get_db)):
    data = await service.rollback(session, name, body.version, str(user.get("sub")))
    await session.commit()
    return success(data)


class PreviewIn(BaseModel):
    sample_ticket: dict


@router.post("/{name}/preview")
async def preview(name: str, body: PreviewIn, _: dict = Depends(require_role("admin"))):
    return success(await service.preview(name, body.sample_ticket))
