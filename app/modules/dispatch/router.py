"""派单配置路由（admin）：配额名单 CRUD + 默认兜底人。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.response import success
from app.core.security import require_role
from app.db.session import get_db
from app.modules.dispatch.models import DispatchAssignee, DispatchConfig, DispatchRule

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])


def _rule_view(r: DispatchRule) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "ruleType": r.rule_type, "isActive": r.is_active,
            "sla": r.sla or [], "sources": r.sources or [], "products": r.products or [], "modules": r.modules or [],
            "dispatchMode": r.dispatch_mode, "assignees": r.assignees or [], "fallback": r.fallback,
            "overflowRuleId": r.overflow_rule_id}


def _pairs(products, modules):
    return {(p, m) for p in (products or []) for m in (modules or [])}


async def _check_conflict(session: AsyncSession, rule_type: str, products, modules, exclude_id=None) -> None:
    """同类型规则下，(产品线,模块) 不可重复。冲突则报错。"""
    want = _pairs(products, modules)
    if not want:
        return
    stmt = select(DispatchRule).where(DispatchRule.rule_type == rule_type, DispatchRule.is_deleted.is_(False))
    if exclude_id:
        stmt = stmt.where(DispatchRule.id != exclude_id)
    for r in (await session.execute(stmt)).scalars():
        dup = want & _pairs(r.products, r.modules)
        if dup:
            sample = "、".join(f"{p}/{m}" for p, m in list(dup)[:3])
            raise BizException(f"以下产品线+模块已被同类型规则「{r.name}」占用：{sample}", code=409)


class RuleIn(BaseModel):
    name: str
    rule_type: str = "正式规则"
    is_active: bool = True
    sla: list = []
    sources: list = []
    products: list = []
    modules: list = []
    dispatch_mode: str = "按数量"
    assignees: list = []
    fallback: Optional[str] = None
    overflow_rule_id: Optional[int] = None


@router.get("/rules")
async def list_rules(_: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    rows = (await session.execute(select(DispatchRule).where(DispatchRule.is_deleted.is_(False))
            .order_by(DispatchRule.sort_order, DispatchRule.id))).scalars()
    return success({"items": [_rule_view(r) for r in rows]})


@router.get("/rules/taken")
async def rules_taken(rule_type: str, exclude_id: Optional[int] = None,
                      _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    """某类型规则已占用的 产品线→模块[]（前端据此过滤问题模块选项）。"""
    stmt = select(DispatchRule).where(DispatchRule.rule_type == rule_type, DispatchRule.is_deleted.is_(False))
    if exclude_id:
        stmt = stmt.where(DispatchRule.id != exclude_id)
    taken: dict = {}
    for r in (await session.execute(stmt)).scalars():
        for p in (r.products or []):
            taken.setdefault(p, set()).update(r.modules or [])
    return success({p: sorted(ms) for p, ms in taken.items()})


@router.post("/rules")
async def create_rule(body: RuleIn, user: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    await _check_conflict(session, body.rule_type, body.products, body.modules)
    seq = (await session.execute(select(func.count()).select_from(DispatchRule))).scalar_one() + 1
    r = DispatchRule(code=f"RULE_{seq:03d}", name=body.name, rule_type=body.rule_type, is_active=body.is_active,
                     sla=body.sla, sources=body.sources, products=body.products, modules=body.modules,
                     dispatch_mode=body.dispatch_mode, assignees=body.assignees, fallback=body.fallback,
                     overflow_rule_id=body.overflow_rule_id, sort_order=seq, created_by=user.get("name", ""))
    session.add(r)
    await session.commit()
    return success({"id": r.id, "code": r.code})


@router.put("/rules/{rid}")
async def update_rule(rid: int, body: RuleIn, user: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    r = await session.get(DispatchRule, rid)
    if r is None:
        raise BizException("规则不存在", code=404)
    await _check_conflict(session, body.rule_type, body.products, body.modules, exclude_id=rid)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    r.updated_by = user.get("name", "")
    await session.commit()
    return success({"ok": True})


@router.delete("/rules/{rid}")
async def delete_rule(rid: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    r = await session.get(DispatchRule, rid)
    if r:
        r.is_deleted = True
        await session.commit()
    return success({"ok": True})


@router.get("/assignees")
async def list_assignees(_: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    rows = (await session.execute(select(DispatchAssignee).where(DispatchAssignee.is_deleted.is_(False)).order_by(DispatchAssignee.tier, DispatchAssignee.sort_order))).scalars()
    return success({"items": [{"id": a.id, "assigneeName": a.assignee_name, "feishuUid": a.feishu_uid,
                               "allocValue": a.alloc_value, "tier": a.tier, "isActive": a.is_active} for a in rows]})


class AssigneeIn(BaseModel):
    assignee_name: str
    feishu_uid: Optional[str] = None
    alloc_value: int = 1
    tier: str = "main"
    is_active: bool = True


@router.post("/assignees")
async def create_assignee(body: AssigneeIn, user: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    a = DispatchAssignee(assignee_name=body.assignee_name, feishu_uid=body.feishu_uid, alloc_value=body.alloc_value,
                         tier=body.tier, is_active=body.is_active, created_by=str(user.get("sub")))
    session.add(a)
    await session.commit()
    return success({"id": a.id})


@router.put("/assignees/{aid}")
async def update_assignee(aid: int, body: AssigneeIn, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    a = await session.get(DispatchAssignee, aid)
    if a is None:
        return success(None, message="不存在")
    a.assignee_name, a.feishu_uid, a.alloc_value, a.tier, a.is_active = body.assignee_name, body.feishu_uid, body.alloc_value, body.tier, body.is_active
    await session.commit()
    return success({"ok": True})


@router.delete("/assignees/{aid}")
async def delete_assignee(aid: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    a = await session.get(DispatchAssignee, aid)
    if a:
        a.is_deleted = True
        await session.commit()
    return success({"ok": True})


class ConfigIn(BaseModel):
    default_assignee: str


@router.put("/config")
async def set_config(body: ConfigIn, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    cfg = (await session.execute(select(DispatchConfig).where(DispatchConfig.config_key == "default_assignee"))).scalar_one_or_none()
    if cfg is None:
        cfg = DispatchConfig(config_key="default_assignee", config_value=body.default_assignee, created_by="admin")
        session.add(cfg)
    else:
        cfg.config_value = body.default_assignee
    await session.commit()
    return success({"ok": True})
