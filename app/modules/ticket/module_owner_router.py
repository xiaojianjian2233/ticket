"""模块责任人映射 CRUD（admin）：t_module_owner（打标权威源）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.security import require_role
from app.db.session import get_db
from app.modules.ticket.models import ModuleOwner

router = APIRouter(prefix="/api/v1/module-owners", tags=["module-owner"])


@router.get("/options")
async def owner_options(_: dict = Depends(require_role("handler")), session: AsyncSession = Depends(get_db)):
    """打标下拉参考数据：仅启用的 module 行（产品线/问题模块/责任人），供工单详情手动改标联动用（handler 可读）。"""
    rows = (await session.execute(select(ModuleOwner).where(
        ModuleOwner.is_deleted.is_(False), ModuleOwner.is_active.is_(True),
        ModuleOwner.row_type == "module").order_by(ModuleOwner.product_tag, ModuleOwner.sort_order))).scalars()
    return success({"items": [{"productTag": m.product_tag, "funcModule": m.func_module,
                               "devOwner": m.dev_owner} for m in rows]})


@router.get("")
async def list_owners(product_tag: Optional[str] = None, _: dict = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_db)):
    stmt = select(ModuleOwner).where(ModuleOwner.is_deleted.is_(False))
    if product_tag:
        stmt = stmt.where(ModuleOwner.product_tag == product_tag)
    rows = (await session.execute(stmt.order_by(ModuleOwner.product_tag, ModuleOwner.sort_order))).scalars()
    return success({"items": [{"id": m.id, "productTag": m.product_tag, "funcModule": m.func_module,
                               "rowType": m.row_type, "triggerWords": m.trigger_words, "devOwner": m.dev_owner,
                               "devOwnerUid": m.dev_owner_uid, "isActive": m.is_active} for m in rows]})


class OwnerIn(BaseModel):
    product_tag: str
    func_module: str
    row_type: str = "module"
    trigger_words: Optional[str] = None
    dev_owner: Optional[str] = None
    dev_owner_uid: Optional[str] = None


@router.post("")
async def create_owner(body: OwnerIn, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    m = ModuleOwner(**body.model_dump(), created_by="admin")
    session.add(m)
    await session.commit()
    return success({"id": m.id})


@router.put("/{mid}")
async def update_owner(mid: int, body: OwnerIn, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    m = await session.get(ModuleOwner, mid)
    if m is None:
        return success(None, message="不存在")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    await session.commit()
    return success({"ok": True})


@router.post("/{mid}/toggle")
async def toggle_owner(mid: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    """启用/禁用切换。"""
    m = await session.get(ModuleOwner, mid)
    if m is None:
        return success(None, message="不存在")
    m.is_active = not m.is_active
    await session.commit()
    return success({"ok": True, "isActive": m.is_active})


@router.delete("/{mid}")
async def delete_owner(mid: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    m = await session.get(ModuleOwner, mid)
    if m:
        m.is_deleted = True
        await session.commit()
    return success({"ok": True})
