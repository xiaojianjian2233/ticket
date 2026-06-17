"""工单路由：列表/详情/未接管/工作台/处理/关单/改判/重入队/改标签 + 研发单。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TicketStatus
from app.core.response import page, success
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.modules.ticket import service
from app.modules.ticket.models import TicketHub, TicketInfo

router = APIRouter(prefix="/api/v1", tags=["ticket"])


@router.get("/tickets")
async def list_tickets(source: Optional[str] = None, sources: Optional[str] = None, status: Optional[str] = None,
                       product_tag: Optional[str] = None, dev_owner: Optional[str] = None,
                       is_returned: Optional[bool] = None, sla_state: Optional[str] = None,
                       service_level: Optional[str] = None, keyword: Optional[str] = None,
                       ticket_nos: Optional[str] = None, created_from: Optional[str] = None,
                       created_to: Optional[str] = None, page_no: int = 1, page_size: int = 20,
                       _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    # sources / service_level / ticket_nos 支持多选（逗号分隔）
    items, total = await service.list_tickets(session, source=source, sources=sources, status=status,
                                              product_tag=product_tag, dev_owner=dev_owner, is_returned=is_returned,
                                              sla_state=sla_state, service_level=service_level, keyword=keyword,
                                              ticket_nos=ticket_nos, created_from=created_from, created_to=created_to,
                                              page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


class BatchCloseIn(BaseModel):
    ids: list[int]


@router.post("/tickets/batch-close")
async def batch_close(body: BatchCloseIn, user: dict = Depends(require_role("handler")),
                      session: AsyncSession = Depends(get_db)):
    result = await service.batch_close(session, body.ids, user.get("name", ""))
    await session.commit()
    return success(result)


@router.get("/service-levels")
async def service_levels(_: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """服务等级基础数据（编码+名称），供派单规则等下拉用。"""
    m = await service._service_level_map(session)
    return success([{"code": c, "name": n} for c, n in m.items()])


@router.get("/overview/stats")
async def overview_stats(personal: bool = False, user: dict = Depends(get_current_user),
                         session: AsyncSession = Depends(get_db)):
    """概览统计（数据源=工单列表）。personal=true 看自己（处理人=当前用户）。"""
    data = await service.overview_stats(session, personal=personal, assignee=user.get("name", ""))
    return success(data)


@router.get("/tickets/unhandled")
async def unhandled(keyword: Optional[str] = None, created_from: Optional[str] = None, created_to: Optional[str] = None,
                    page_no: int = 1, page_size: int = 50, _: dict = Depends(get_current_user),
                    session: AsyncSession = Depends(get_db)):
    items, total = await service.list_tickets(session, status=TicketStatus.RETURNED.value, keyword=keyword,
                                              created_from=created_from, created_to=created_to,
                                              page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


@router.get("/workbench/my-tickets")
async def my_tickets(page_no: int = 1, page_size: int = 20, user: dict = Depends(require_role("handler")),
                     session: AsyncSession = Depends(get_db)):
    items, total = await service.workbench(session, user.get("name", ""), page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


# 处理中状态集合（待我处理）
_MY_PENDING_STATUSES = ",".join([TicketStatus.PENDING_MANUAL.value, TicketStatus.SUPPLEMENT.value, TicketStatus.PENDING_RD.value])


@router.get("/workbench/my-pending")
async def my_pending(sources: Optional[str] = None, status: Optional[str] = None, sla_state: Optional[str] = None,
                     service_level: Optional[str] = None, keyword: Optional[str] = None,
                     created_from: Optional[str] = None, created_to: Optional[str] = None,
                     page_no: int = 1, page_size: int = 20, user: dict = Depends(require_role("handler")),
                     session: AsyncSession = Depends(get_db)):
    """待我处理的工单：处理人=当前登录用户 且 状态为处理中(待人工/补充资料/待研发)。status 再过滤取交集。"""
    items, total = await service.list_tickets(
        session, dispatch_assignee=user.get("name", ""), statuses=_MY_PENDING_STATUSES, status=status,
        sources=sources, sla_state=sla_state, service_level=service_level, keyword=keyword,
        created_from=created_from, created_to=created_to, page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


@router.get("/tickets/{info_id}")
async def ticket_detail(info_id: int, _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return success(await service.detail(session, info_id))


class HandleIn(BaseModel):
    action: str
    reply_content: Optional[str] = None


@router.post("/tickets/{info_id}/handle")
async def handle(info_id: int, body: HandleIn, user: dict = Depends(require_role("handler")),
                 session: AsyncSession = Depends(get_db)):
    await service.handle_ticket(session, info_id, body.action, body.reply_content, user.get("name", ""))
    await session.commit()
    return success({"ok": True})


class CloseIn(BaseModel):
    reply_content: Optional[str] = None


@router.post("/tickets/{info_id}/close")
async def close(info_id: int, body: CloseIn, user: dict = Depends(require_role("handler")),
                session: AsyncSession = Depends(get_db)):
    await service.close_ticket(session, info_id, body.reply_content, user.get("name", ""))
    await session.commit()
    return success({"ok": True})


@router.post("/tickets/{info_id}/takeover")
async def takeover(info_id: int, user: dict = Depends(require_role("handler")), session: AsyncSession = Depends(get_db)):
    """接管未接管工单 → 转人工待办。"""
    await service.takeover(session, info_id, user.get("name", ""))
    await session.commit()
    return success({"ok": True})


@router.post("/tickets/{info_id}/rejudge")
async def rejudge(info_id: int, user: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    await service.rejudge(session, info_id, user.get("name", ""))
    await session.commit()
    return success({"ok": True})


class RequeueIn(BaseModel):
    task_type: str = "run_pipeline"


@router.post("/tickets/{info_id}/requeue")
async def requeue(info_id: int, body: RequeueIn, _: dict = Depends(require_role("admin")),
                  session: AsyncSession = Depends(get_db)):
    await service.requeue(session, info_id, body.task_type)
    await session.commit()
    return success({"ok": True})


class TagIn(BaseModel):
    product_tag: Optional[str] = None
    func_module: Optional[str] = None
    dev_owner: Optional[str] = None
    ticket_type: Optional[str] = None


@router.put("/tickets/{info_id}/tag")
async def update_tag(info_id: int, body: TagIn, user: dict = Depends(require_role("handler")),
                     session: AsyncSession = Depends(get_db)):
    await service.update_tag(session, info_id, product_tag=body.product_tag, func_module=body.func_module,
                             dev_owner=body.dev_owner, ticket_type=body.ticket_type, operator=user.get("name", ""))
    await session.commit()
    return success({"ok": True})


@router.get("/hubs")
async def list_hubs(keyword: Optional[str] = None, status: Optional[str] = None,
                    created_from: Optional[str] = None, created_to: Optional[str] = None,
                    rd_resolved_from: Optional[str] = None, rd_resolved_to: Optional[str] = None,
                    ticket_no: Optional[str] = None, page_no: int = 1, page_size: int = 20,
                    _: dict = Depends(require_role("handler")), session: AsyncSession = Depends(get_db)):
    items, total = await service.list_hubs(session, keyword=keyword, status=status,
                                           created_from=created_from, created_to=created_to,
                                           rd_resolved_from=rd_resolved_from, rd_resolved_to=rd_resolved_to,
                                           ticket_no=ticket_no, page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


@router.get("/hubs/{hub_id}")
async def hub_detail(hub_id: int, _: dict = Depends(require_role("handler")), session: AsyncSession = Depends(get_db)):
    hub = await session.get(TicketHub, hub_id)
    if hub is None:
        return success(None, message="研发单不存在")
    infos = (await session.execute(select(TicketInfo.id, TicketInfo.ticket_no).where(TicketInfo.rd_hub_id == hub_id))).all()
    return success({"id": hub.id, "hubNo": hub.hub_no, "title": hub.title, "problemSummary": hub.problem_summary,
                    "productTag": hub.product_tag, "devOwner": hub.dev_owner, "linearUrl": hub.linear_url,
                    "linearSyncStatus": hub.linear_sync_status, "rdStatus": hub.status, "rdHandler": hub.rd_handler,
                    "rdStatusNote": hub.rd_status_note, "linkedTickets": [{"id": i, "ticketNo": n} for i, n in infos]})


@router.post("/hubs/{hub_id}/sync-status")
async def sync_hub_status(hub_id: int, _: dict = Depends(require_role("handler")), session: AsyncSession = Depends(get_db)):
    """手动从 Linear 拉取该 hub 当前状态并回写（push 兜底，供「立即同步」按钮）。"""
    from app.modules.ticket import linear_sync
    hub = await session.get(TicketHub, hub_id)
    if hub is None:
        return success(None, message="研发单不存在")
    changed = await linear_sync.sync_hub(session, hub)
    await session.commit()
    return success({"changed": changed, "status": hub.status})


@router.post("/hubs/{hub_id}/resync-linear")
async def resync_linear(hub_id: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    """重新同步 Linear（linear_sync_status=failed 时重建 issue，责任人固定李志坚）。"""
    from app.integrations.linear_client import get_linear
    hub = await session.get(TicketHub, hub_id)
    if hub is None:
        return success(None, message="研发单不存在")
    issue = await get_linear().create_issue(title=f"[{hub.hub_no}] {hub.title}", description=hub.full_reply or hub.problem_summary or hub.title)
    hub.linear_issue_id = issue.get("id") or hub.linear_issue_id
    hub.linear_url = issue.get("url") or hub.linear_url
    hub.linear_sync_status = "synced" if not issue.get("dry_run") else "pending"
    hub.linear_sync_retry = (hub.linear_sync_retry or 0) + 1
    await session.commit()
    return success({"ok": True, "linearSyncStatus": hub.linear_sync_status})
