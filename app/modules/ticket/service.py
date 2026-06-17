"""工单业务编排：查询视图 + 人工动作（关单/处理/改判/重入队/改标签）。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import Source, TaskType, TicketStatus
from app.core.config import settings
from app.core.exceptions import BizException, IntegrationException
from app.db import queue
from app.core.logging import new_trace_id
from app.integrations.ksm_client import get_ksm
from app.modules.ticket import repository as repo
from app.modules.ticket.models import ServiceLevel, TicketDetail, TicketHub, TicketInfo, TicketOrg, TicketTag
from app.pipeline import writeback

logger = logging.getLogger("ticket_hub.ticket")


def _now():
    return datetime.now(timezone.utc)


def _dt(s):
    """日期/时间字符串 → tz-aware datetime（asyncpg 的 timestamptz 参数需 datetime，不能传字符串）。"""
    if not s or isinstance(s, datetime):
        return s or None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# 工单类型：由 answer_branch 派生（配置类/运维类 待 KSM feedbackType 等来源补充）
_BRANCH_TYPE = {"A": "bug类", "B": "需求类", "C": "问题资料缺失", "D": "其它"}


def _ticket_type(i: TicketInfo) -> Optional[str]:
    # 人工选定的工单类型优先；否则按 answer_branch 派生
    return i.ticket_type or (_BRANCH_TYPE.get(i.answer_branch) if i.answer_branch else None)


async def _service_level_map(session: AsyncSession) -> dict:
    """t_service_level 编码→名称（每次查询，基础数据小）。"""
    rows = (await session.execute(select(ServiceLevel.code, ServiceLevel.name)
            .where(ServiceLevel.is_deleted.is_(False)))).all()
    return {str(c): n for c, n in rows}


def list_item(i: TicketInfo, d: Optional[TicketDetail] = None, o: "Optional[TicketOrg]" = None,
              sl_map: Optional[dict] = None) -> dict:
    sl_raw = (o.ksm_service_level if o else None)
    service_level = (sl_map or {}).get(str(sl_raw), sl_raw) if sl_raw else None  # 编码→名称(查不到回退原值)
    return {
        "id": i.id, "ticketNo": i.ticket_no, "source": i.source,
        "sourceBillNo": i.source_bill_no,                         # 工单来源编号
        "title": i.title, "problemContent": i.description,        # 问题内容
        "hasAttachment": i.has_attachment,                        # 是否有附件
        "routeAction": i.route_action, "routeReason": i.route_reason,  # 不接管原因
        "productTag": i.ai_product_tag, "funcModule": i.ai_func_module,  # 问题模块
        "devOwner": i.ai_dev_owner, "devOwnerMissing": i.dev_owner_missing,  # 责任田负责人
        "dispatchAssignee": i.dispatch_assignee,                  # 处理人
        "customerCompany": i.customer_company,                    # 提单企业名称
        "status": i.status, "answerBranch": i.answer_branch,
        "ticketType": _ticket_type(i),                  # 工单类型(bug/需求/资料缺失/其它)
        "handleNote": i.final_reply,                     # 处理说明(最终解决方案)
        "isReturned": i.is_returned, "returnCount": i.return_count, "slaState": i.sla_state,
        # 剩余处理时间(小时)=SLA截止-当前(逻辑后续细化)；超时为负
        "remainingHours": (round((i.sla_due_at - _now()).total_seconds() / 3600, 1) if i.sla_due_at else None),
        "serviceLevel": service_level,                            # 服务等级名称(由编码映射)
        "createdAt": i.created_at,                                # 创建时间
        "resolvedAt": i.resolved_at,                              # 处理完成时间
        "closedAt": i.closed_at,                                  # 处理关闭时间
        # 联系人 / 税号 / 归属租户(来自 detail，PII)
        "customerContact": d.customer_contact if d else None,
        "customerMobile": (d.customer_mobile or d.customer_tel) if d else None,
        "customerEmail": d.customer_email if d else None,
        "customerTaxNo": d.customer_tax_no if d else None,
        "customerTenant": d.customer_no if d else None,
    }


def _as_list(v):
    if v is None:
        return None
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()] or None
    return list(v) or None


async def list_tickets(session: AsyncSession, *, source=None, sources=None, status=None, statuses=None,
                       product_tag=None, dev_owner=None, dispatch_assignee=None,
                       is_returned=None, sla_state=None, service_level=None, keyword=None, ticket_nos=None,
                       created_from=None, created_to=None, page=1, page_size=20) -> tuple[list[dict], int]:
    base = (select(TicketInfo, TicketDetail, TicketOrg)
            .join(TicketDetail, TicketDetail.ticket_id == TicketInfo.id, isouter=True)
            .join(TicketOrg, TicketOrg.ticket_id == TicketInfo.id, isouter=True)
            .where(TicketInfo.is_deleted.is_(False)))
    cnt = (select(func.count()).select_from(TicketInfo)
           .join(TicketOrg, TicketOrg.ticket_id == TicketInfo.id, isouter=True)
           .where(TicketInfo.is_deleted.is_(False)))

    def both(clause):
        nonlocal base, cnt
        base = base.where(clause); cnt = cnt.where(clause)

    sla_list = _as_list(sla_state)              # 支持多选(逗号分隔)
    if sla_list:
        both(TicketInfo.sla_state.in_(sla_list))
    src_list = _as_list(sources) or ([source] if source else None)
    if src_list:
        both(TicketInfo.source.in_(src_list))
    status_list = _as_list(status)             # 支持多选(逗号分隔)
    if status_list:
        both(TicketInfo.status.in_(status_list))
    st_list = _as_list(statuses)               # 与 status 取交集(my-pending 用，保证仍受处理中约束)
    if st_list:
        both(TicketInfo.status.in_(st_list))
    if product_tag:
        both(TicketInfo.ai_product_tag == product_tag)
    if dev_owner:
        both(TicketInfo.ai_dev_owner == dev_owner)
    if dispatch_assignee:
        both(TicketInfo.dispatch_assignee == dispatch_assignee)
    if is_returned is not None:
        both(TicketInfo.is_returned.is_(is_returned))
    sl_map = await _service_level_map(session)
    sl_list = _as_list(service_level)
    if sl_list:
        # 筛选传的是名称 → 反查编码（兼容直接传编码）
        name2code = {n: c for c, n in sl_map.items()}
        codes = [name2code.get(x, x) for x in sl_list]
        both(TicketOrg.ksm_service_level.in_(codes))
    if keyword:
        both(TicketInfo.ticket_no.ilike(f"%{keyword}%") | TicketInfo.title.ilike(f"%{keyword}%"))
    tn_list = _as_list(ticket_nos)
    if tn_list:
        both(TicketInfo.ticket_no.in_(tn_list))
    cf, ct = _dt(created_from), _dt(created_to)
    if cf:
        both(TicketInfo.created_at >= cf)
    if ct:
        both(TicketInfo.created_at <= ct)
    total = (await session.execute(cnt)).scalar_one()
    rows = (await session.execute(base.order_by(TicketInfo.id.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return [list_item(info, detail, org, sl_map) for info, detail, org in rows], total


async def batch_close(session: AsyncSession, ids: list[int], operator: str) -> dict:
    """批量关闭：状态为 done(处理完成)/closed(已关闭) 的不执行，其余置 closed。"""
    success, skipped, failed, details = 0, 0, 0, []
    for tid in ids:
        info = await session.get(TicketInfo, tid)
        if info is None:
            failed += 1; details.append({"id": tid, "result": "failed", "reason": "工单不存在"}); continue
        if info.status in (TicketStatus.DONE.value, TicketStatus.CLOSED.value):
            skipped += 1
            details.append({"id": tid, "ticketNo": info.ticket_no, "result": "skipped",
                            "reason": "工单状态已为处理完成" if info.status == TicketStatus.DONE.value else "工单已关闭"})
            continue
        info.status = TicketStatus.CLOSED.value
        info.closed_at = _now()
        info.updated_by = operator
        success += 1
        details.append({"id": tid, "ticketNo": info.ticket_no, "result": "success"})
    await session.flush()
    return {"total": len(ids), "success": success, "failed": failed, "skipped": skipped, "details": details}


async def takeover(session: AsyncSession, info_id: int, operator: str) -> None:
    """接管未接管(returned)工单：转人工待办、指派操作人、移出未接管列表。"""
    info = await session.get(TicketInfo, info_id)
    if info is None:
        raise BizException("工单不存在", code=404)
    await repo.update_info(session, info, status=TicketStatus.PENDING_MANUAL.value, is_returned=False,
                           dispatch_assignee=operator, dispatched_at=_now(),
                           route_action="人工接管", updated_by=operator)


_SKILL_LABEL = {
    "intake": "接入解析", "routable": "流转判定", "tagging": "智能打标", "dispatch": "自动派单",
    "answer": "AI 答复", "answer_router": "答复分支判定", "humanize": "话术润色", "writeback": "回写来源",
    "dedup": "重复检测", "embed": "向量化", "faq_match": "知识库匹配", "sla": "SLA 计算",
}


async def detail(session: AsyncSession, info_id: int) -> dict:
    info = await session.get(TicketInfo, info_id)
    if info is None or info.is_deleted:
        raise BizException("工单不存在", code=404)
    d = await repo.get_detail(session, info_id)
    org = (await session.execute(select(TicketOrg).where(TicketOrg.ticket_id == info_id))).scalar_one_or_none()
    tags = (await session.execute(select(TicketTag).where(TicketTag.ticket_id == info_id).order_by(TicketTag.id.desc()))).scalars()

    # 反馈附件（scope=ticket）
    from app.modules.storage.models import Attachment
    atts = (await session.execute(select(Attachment).where(Attachment.scope == "ticket", Attachment.ref_id == info_id))).scalars().all()
    attachments = [{"name": a.file_name or a.minio_key or "附件", "url": a.public_url, "isImage": a.is_image} for a in atts]

    # 处理历史节点（创建 + 流水线每步 + 答复/关单），正序组装，前端倒序展示
    from app.modules.ai.models import SkillLog
    logs = (await session.execute(select(SkillLog).where(SkillLog.ticket_id == info_id).order_by(SkillLog.id.asc()))).scalars().all()
    src_label = {"ksm": "KSM", "zhichi": "智齿", "assistant": "内部提单"}.get(info.source, info.source)
    timeline = [{"op": "创建工单", "operator": info.created_by or src_label, "time": info.created_at,
                 "note": info.description, "status": "ok", "attachments": attachments}]
    for lg in logs:
        timeline.append({"op": _SKILL_LABEL.get(lg.skill_name, lg.skill_name),
                         "operator": lg.model_used or lg.created_by or "系统", "time": lg.created_at,
                         "note": lg.evidence or "", "status": lg.status, "attachments": []})
    if info.final_reply:
        timeline.append({"op": "答复", "operator": info.dispatch_assignee or info.updated_by or "系统",
                         "time": info.resolved_at or info.updated_at, "note": info.final_reply, "status": "ok", "attachments": []})
    if info.closed_at:
        timeline.append({"op": "关单", "operator": info.updated_by or "系统", "time": info.closed_at,
                         "note": "工单已关闭", "status": "ok", "attachments": []})

    view = list_item(info, d, org, await _service_level_map(session))
    view.update({
        "attachments": attachments,
        "timeline": timeline,
        "description": info.description,           # ★问题描述
        "sourceBillNo": info.source_bill_no,
        "routable": info.routable, "routeAction": info.route_action, "routeReason": info.route_reason,
        "transferResult": info.transfer_result, "finalReply": info.final_reply,
        "rdHubId": info.rd_hub_id, "rdStatus": info.rd_status, "rdHandler": info.rd_handler,
        "isDuplicate": info.is_duplicate, "reusedFrom": info.reused_from_ticket_id,
        "slaStartAt": info.sla_start_at, "slaDueAt": info.sla_due_at, "resolvedAt": info.resolved_at, "closedAt": info.closed_at,
        "detail": ({"aiReply": d.ai_reply, "fullReply": d.full_reply, "humanizedReply": d.humanized_reply,
                    "supplyNote": d.supply_note, "productNameRaw": d.product_name_raw, "moduleRaw": d.module_raw} if d else None),
        "tags": [{"productTag": t.product_tag, "funcModule": t.func_module, "devOwner": t.dev_owner,
                  "tagSource": t.tag_source, "isCurrent": t.is_current, "createdAt": t.created_at} for t in tags],
    })
    return view


async def _ksm_prepare_write(session: AsyncSession, info: TicketInfo) -> None:
    """KSM 人工写操作前置：确保接管(已接管忽略) + 重拉刷新节点（避免"未锁定/已流转至其他节点"）。"""
    if info.source != Source.KSM.value:
        return
    try:
        await get_ksm().lock_order(bill_id=info.source_id, account=settings.ksm_handler_name,
                                   account_name=settings.ksm_handler_name, account_number=settings.ksm_handler_number)
    except IntegrationException as e:  # 已被接管等→视为已接管，继续
        logger.info("人工写前接管(忽略已接管) ticket=%s: %s", info.ticket_no, e)
    from app.pipeline.runner import _refresh_after_lock
    await _refresh_after_lock(session, info)


async def close_ticket(session: AsyncSession, info_id: int, reply: Optional[str], operator: str) -> None:
    info = await session.get(TicketInfo, info_id)
    if info is None:
        raise BizException("工单不存在", code=404)
    final = reply or info.final_reply or ""
    # 关单前置校验：产品线/问题模块/责任田负责人/工单类型/处理说明 均不可为空
    missing = []
    if not (info.ai_product_tag or "").strip() or info.ai_product_tag == "无法判断":
        missing.append("产品线")
    if not (info.ai_func_module or "").strip():
        missing.append("问题模块")
    if not (info.ai_dev_owner or "").strip() or info.ai_dev_owner == settings.default_dev_owner:
        missing.append("责任田负责人")
    if not (info.ticket_type or "").strip():
        missing.append("工单类型")
    if not (final or "").strip():
        missing.append("处理说明")
    if missing:
        raise BizException(f"以下内容不能为空，无法关单：{('、'.join(missing))}", code=400)
    await _ksm_prepare_write(session, info)                       # 接管+刷新节点
    await writeback.writeback_close(session, info, final)         # handleKsmOrder is_deal=True 结案
    await repo.update_info(session, info, final_reply=final, status=TicketStatus.DONE.value,
                           resolved_at=_now(), writeback_status="success", updated_by=operator)
    # FAQ 收录改由 C/B 人工关单触发（失败不阻断）
    from app.pipeline.runner import faq_record_on_close
    await faq_record_on_close(session, info)


async def handle_ticket(session: AsyncSession, info_id: int, action: str, reply: Optional[str], operator: str) -> None:
    info = await session.get(TicketInfo, info_id)
    if info is None:
        raise BizException("工单不存在", code=404)
    if action in ("confirm_reply", "edit_reply"):
        await close_ticket(session, info_id, reply, operator)
    elif action == "supply":
        # 补充资料：退回客户补料（supplyKsmOrder），状态置「补充资料」
        await _ksm_prepare_write(session, info)
        await writeback.writeback_supply(session, info, reply or info.final_reply or "")
        await repo.update_info(session, info, status=TicketStatus.SUPPLEMENT.value, updated_by=operator)
    elif action == "to_rd":
        # 转研发：生成/关联 hub + 推 Linear（责任人李志坚）→ pending_rd
        from app.pipeline.runner import _branch_to_rd
        from app.pipeline.context import RunContext
        ctx = RunContext(trace_id=new_trace_id(), ticket_id=info.id, source=info.source)
        await repo.update_info(session, info, answer_branch=(info.answer_branch or "A"), updated_by=operator)
        await _branch_to_rd(session, ctx, info, info.ai_product_tag or "无法判断",
                            info.ai_func_module or "", info.final_reply or info.description or "",
                            info.answer_branch or "A")
    elif action == "return":
        # 退回工单：returnKsmOrder 退回 KSM；先接管+刷新节点
        await _ksm_prepare_write(session, info)
        await writeback.writeback_return(session, info, reply or "退回")
        await repo.update_info(session, info, status=TicketStatus.RETURNED.value, is_returned=True,
                               route_action="不接管-人工退回", updated_by=operator)
    else:
        raise BizException(f"未知动作: {action}", code=422)


async def rejudge(session: AsyncSession, info_id: int, operator: str) -> None:
    info = await session.get(TicketInfo, info_id)
    if info is None:
        raise BizException("工单不存在", code=404)
    if info.status != TicketStatus.RETURNED.value:
        raise BizException("仅未接管(returned)工单可改判重跑", code=400)
    await repo.update_info(session, info, status=TicketStatus.PENDING.value, routable=True, updated_by=operator)
    await queue.enqueue(session, TaskType.RUN_PIPELINE, {"info_id": info_id, "trace_id": new_trace_id()},
                        dedup_key=f"run_pipeline:{info_id}")


async def requeue(session: AsyncSession, info_id: int, task_type: str) -> None:
    payload = {"info_id": info_id, "trace_id": new_trace_id()} if task_type == TaskType.RUN_PIPELINE.value else {"info_id": info_id}
    await queue.enqueue(session, task_type, payload, dedup_key=f"{task_type}:{info_id}")


async def update_tag(session: AsyncSession, info_id: int, *, product_tag, func_module, dev_owner,
                     operator: str, ticket_type=None) -> None:
    info = await session.get(TicketInfo, info_id)
    if info is None:
        raise BizException("工单不存在", code=404)
    # 责任田负责人：未显式指定时，按 产品线+问题模块 查模块责任人表自动补全
    if not dev_owner and product_tag and func_module:
        dev_owner = await repo.lookup_dev_owner(session, func_module, product_tag=product_tag)
    await session.execute(
        TicketTag.__table__.update().where(TicketTag.ticket_id == info_id).values(is_current=False)
    )
    session.add(TicketTag(ticket_id=info_id, product_tag=product_tag, func_module=func_module, dev_owner=dev_owner,
                          tag_source="manual", is_current=True, revised_by=operator, created_by=operator))
    fields = {"ai_product_tag": product_tag, "ai_func_module": func_module, "ai_dev_owner": dev_owner,
              "dev_owner_missing": not bool(dev_owner), "updated_by": operator}
    if ticket_type is not None:
        fields["ticket_type"] = ticket_type or None
    await repo.update_info(session, info, **fields)


async def workbench(session: AsyncSession, assignee_name: str, *, page=1, page_size=20) -> tuple[list[dict], int]:
    stmt = select(TicketInfo).where(TicketInfo.dispatch_assignee == assignee_name,
                                    TicketInfo.status == TicketStatus.PENDING_MANUAL.value,
                                    TicketInfo.is_deleted.is_(False))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(TicketInfo.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars()
    return [list_item(i) for i in rows], total


_PROCESSING_ST = [TicketStatus.PENDING.value, TicketStatus.PENDING_MANUAL.value,
                  TicketStatus.SUPPLEMENT.value, TicketStatus.PENDING_RD.value]
_CLOSED_ST = [TicketStatus.DONE.value, TicketStatus.CLOSED.value]
# 来源 → 概览折线分组（外部提单暂无对应来源，置0）
_SRC_GROUP = {"ksm": "ksm", "zhichi": "zhichi", "assistant": "internal"}


async def overview_stats(session: AsyncSession, *, personal: bool = False, assignee: str = "") -> dict:
    """概览统计（数据源=工单列表 t_ticket_info + 研发单 t_ticket_hub）。personal=按处理人=assignee。"""
    def tw(*extra):
        c = [TicketInfo.is_deleted.is_(False), *extra]
        if personal and assignee:
            c.append(TicketInfo.dispatch_assignee == assignee)
        return c

    async def cnt(*extra):
        return (await session.execute(select(func.count()).select_from(TicketInfo).where(*tw(*extra)))).scalar_one()

    now = _now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = week_start - timedelta(days=7)
    ticket = {
        "total": await cnt(),
        "processing": await cnt(TicketInfo.status.in_(_PROCESSING_ST)),
        "closed": await cnt(TicketInfo.status.in_(_CLOSED_ST)),
        "thisWeek": await cnt(TicketInfo.created_at >= week_start),
        "lastWeek": await cnt(TicketInfo.created_at >= last_week_start, TicketInfo.created_at < week_start),
    }
    # 关单率 = 已关闭/总数；及时关单率 = SLA内关闭/已关闭
    timely = await cnt(TicketInfo.status.in_(_CLOSED_ST), TicketInfo.resolved_at.is_not(None),
                       TicketInfo.sla_due_at.is_not(None), TicketInfo.resolved_at <= TicketInfo.sla_due_at)
    ticket["closeRate"] = round(ticket["closed"] / ticket["total"] * 100, 1) if ticket["total"] else 0
    ticket["timelyCloseRate"] = round(timely / ticket["closed"] * 100, 1) if ticket["closed"] else 0

    # 近30天 按天×来源
    since = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    drows = (await session.execute(
        select(func.date(TicketInfo.created_at).label("d"), TicketInfo.source, func.count())
        .where(*tw(TicketInfo.created_at >= since)).group_by("d", TicketInfo.source))).all()
    day_map = {}
    for dval, src, c in drows:
        key = str(dval)
        e = day_map.setdefault(key, {"ksm": 0, "zhichi": 0, "internal": 0, "external": 0})
        g = _SRC_GROUP.get(src)
        if g:
            e[g] += int(c)
    trend = []
    for i in range(30):
        day = (since + timedelta(days=i)).date()
        e = day_map.get(str(day), {"ksm": 0, "zhichi": 0, "internal": 0, "external": 0})
        trend.append({"date": f"{day.month:02d}-{day.day:02d}", **e,
                      "total": e["ksm"] + e["zhichi"] + e["internal"] + e["external"]})

    # 个人关单走势：近30天按天关单数(resolved_at)
    crows = (await session.execute(
        select(func.date(TicketInfo.resolved_at).label("d"), func.count())
        .where(*tw(TicketInfo.status.in_(_CLOSED_ST), TicketInfo.resolved_at >= since)).group_by("d"))).all()
    cmap = {str(dv): int(c) for dv, c in crows}
    close_trend = [{"date": f"{(since + timedelta(days=i)).date().month:02d}-{(since + timedelta(days=i)).date().day:02d}",
                    "closed": cmap.get(str((since + timedelta(days=i)).date()), 0)} for i in range(30)]

    # 个人监控指标
    soon = now + timedelta(hours=2)
    yest_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    green_q = (select(func.count()).select_from(TicketInfo)
               .join(TicketOrg, TicketOrg.ticket_id == TicketInfo.id, isouter=True)
               .where(*tw(TicketInfo.status.in_(_PROCESSING_ST), TicketOrg.ksm_service_level == "50")))
    metrics = {
        "greenStrategic": (await session.execute(green_q)).scalar_one(),       # 绿色战略客户(编码50)且处理中
        "overdueUnclosed": await cnt(TicketInfo.status.in_(_PROCESSING_ST), TicketInfo.sla_state == "breached"),
        "soonOverdue": await cnt(TicketInfo.status.in_(_PROCESSING_ST), TicketInfo.sla_due_at.is_not(None),
                                 TicketInfo.sla_due_at > now, TicketInfo.sla_due_at <= soon),
        "pendingManual": await cnt(TicketInfo.status == TicketStatus.PENDING_MANUAL.value),
        "yesterdayNew": await cnt(TicketInfo.dispatched_at >= yest_start, TicketInfo.dispatched_at < today_start),
    }

    # 产研任务（t_ticket_hub）
    hrows = (await session.execute(select(TicketHub.status, func.count())
             .where(TicketHub.is_deleted.is_(False)).group_by(TicketHub.status))).all()
    hmap = {str(s): int(c) for s, c in hrows}
    rd = {"total": sum(hmap.values()),
          "pending": hmap.get("pending_follow", 0) + hmap.get("待处理", 0),
          "developing": hmap.get("developing", 0) + hmap.get("in_progress", 0),
          "testing": hmap.get("testing", 0),
          "released": hmap.get("released", 0) + hmap.get("resolved", 0) + hmap.get("closed", 0)}

    # 各产品线 问题模块 top5（按工单数）
    mrows = (await session.execute(
        select(TicketInfo.ai_product_tag, TicketInfo.ai_func_module, func.count(), func.max(TicketInfo.ai_dev_owner))
        .where(*tw(TicketInfo.ai_product_tag.is_not(None), TicketInfo.ai_func_module.is_not(None)))
        .group_by(TicketInfo.ai_product_tag, TicketInfo.ai_func_module))).all()
    by_prod = {}
    for pt, fm, c, owner in mrows:
        by_prod.setdefault(pt, []).append({"m": fm, "c": int(c), "owner": owner or "-"})
    product_modules = []
    for pt, items in by_prod.items():
        items.sort(key=lambda x: x["c"], reverse=True)
        product_modules.append({"product": pt, "items": items[:5]})
    product_modules.sort(key=lambda p: sum(i["c"] for i in p["items"]), reverse=True)

    return {"ticket": ticket, "trend": trend, "closeTrend": close_trend, "rd": rd,
            "metrics": metrics, "productModules": product_modules}


async def list_hubs(session: AsyncSession, *, keyword=None, status=None, created_from=None, created_to=None,
                    rd_resolved_from=None, rd_resolved_to=None, ticket_no=None, page=1, page_size=20) -> tuple[list[dict], int]:
    stmt = select(TicketHub).where(TicketHub.is_deleted.is_(False))
    if keyword:
        stmt = stmt.where(TicketHub.hub_no.ilike(f"%{keyword}%"))
    if status:
        stmt = stmt.where(TicketHub.status == status)
    if _dt(created_from):
        stmt = stmt.where(TicketHub.created_at >= _dt(created_from))
    if _dt(created_to):
        stmt = stmt.where(TicketHub.created_at <= _dt(created_to))
    if _dt(rd_resolved_from):
        stmt = stmt.where(TicketHub.rd_resolved_at >= _dt(rd_resolved_from))
    if _dt(rd_resolved_to):
        stmt = stmt.where(TicketHub.rd_resolved_at <= _dt(rd_resolved_to))
    if ticket_no:
        sub = select(TicketInfo.rd_hub_id).where(TicketInfo.ticket_no.ilike(f"%{ticket_no}%"))
        stmt = stmt.where(TicketHub.id.in_(sub))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = list((await session.execute(stmt.order_by(TicketHub.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars())
    # 关联工单号（反查 t_ticket_info.rd_hub_id）
    links: dict = {}
    hub_ids = [h.id for h in rows]
    if hub_ids:
        for hid, tno in (await session.execute(
                select(TicketInfo.rd_hub_id, TicketInfo.ticket_no).where(TicketInfo.rd_hub_id.in_(hub_ids)))).all():
            links.setdefault(hid, []).append(tno)
    items = [{"id": h.id, "hubNo": h.hub_no, "title": h.title,
              "problemSummary": h.problem_summary,                 # 产研任务说明
              "rdNote": h.rd_status_note,                          # 产研处理说明
              "productTag": h.product_tag, "funcModule": h.func_module, "devOwner": h.dev_owner,
              "linearUrl": h.linear_url, "linearSyncStatus": h.linear_sync_status,
              "rdStatus": h.status, "rdSlaState": h.rd_sla_state,
              "createdAt": h.created_at, "rdResolvedAt": h.rd_resolved_at,   # 研发完成时间
              "releaseAt": getattr(h, "release_at", None),         # 发版上线时间(待数据源)
              "releaseVersion": getattr(h, "release_version", None),  # 上线版本号(待数据源)
              "ticketNos": links.get(h.id, [])} for h in rows]      # 关联工单号
    return items, total
