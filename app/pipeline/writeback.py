"""回写服务：按来源不对称回写（KSM handleKsmOrder / 智齿 save_ticket_reply / assistant 飞书私信）。

全程经各 client 的 dry_run 守卫（settings.writeback_dry_run=True 时只组装不真发）。
KSM 生产：client retries=0 单次。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import CUSTOMER_REPLY_FOOTER, ZHICHI_STATUS_WAITING
from app.common.enums import Source
from app.core.config import settings
from app.integrations.feishu_client import get_feishu
from app.integrations.ksm_client import get_ksm
from app.integrations.zhichi_client import get_zhichi
from app.modules.ticket.models import TicketInfo, TicketOrg

logger = logging.getLogger("ticket_hub.writeback")


async def _org(session: AsyncSession, info_id: int) -> Optional[TicketOrg]:
    return (await session.execute(
        select(TicketOrg).where(TicketOrg.ticket_id == info_id, TicketOrg.is_deleted.is_(False))
    )).scalar_one_or_none()


async def writeback_close(session: AsyncSession, info: TicketInfo, reply: str) -> dict:
    """关单回写（KSM 处理完成4 / 智齿 已解决3 / assistant 飞书私信）。

    对客答复统一追加客服尾注（自动答复 / 人工答复 均经此处）。仅作用于对外文本，不改库内 final_reply。
    """
    src = info.source
    reply = f"{reply or ''}{CUSTOMER_REPLY_FOOTER}"
    if src == Source.ZHICHI.value:
        return await get_zhichi().close_with_reply(
            ticketid=info.source_id, title=info.title, content=info.description, reply=reply)
    if src == Source.KSM.value:
        org = await _org(session, info.id)
        return await get_ksm().handle_order(
            bill_id=(org.org_bill_id if org else info.source_id),
            account=settings.ksm_handler_name, account_name=settings.ksm_handler_name, account_number=settings.ksm_handler_number,
            linkman=(org.org_linkman if org else "") or settings.ksm_user,
            email=(org.org_email if org else "") or "", mobile=(org.org_mobile if org else "") or "",
            product_id=(org.ksm_product_id if org else "") or "", version_id=(org.ksm_version_id if org else "") or "",
            module_id=(org.ksm_module_id if org else "") or "", back_type=str(org.ksm_feedback_type if org else "0"),
            current_node_id=(org.ksm_node_id if org else "") or "", reply=reply, is_deal=True)  # 答复关单=结案模式
    # assistant
    return await get_feishu().send_text(f"【工单 {info.ticket_no} 已答复】\n{reply}")


async def writeback_supply(session: AsyncSession, info: TicketInfo, supply_note: str) -> dict:
    """补料回写（KSM supplyKsmOrder / 智齿 等待回复2 / assistant 私信）。"""
    src = info.source
    if src == Source.ZHICHI.value:
        return await get_zhichi().save_ticket_reply(
            ticketid=info.source_id, ticket_title=info.title, ticket_content=info.description,
            reply_content=supply_note, ticket_status=ZHICHI_STATUS_WAITING)
    if src == Source.KSM.value:
        org = await _org(session, info.id)
        return await get_ksm().supply_order(
            bill_id=(org.org_bill_id if org else info.source_id), account=settings.ksm_handler_name,
            account_name=settings.ksm_handler_name, account_number=settings.ksm_handler_number,
            current_node_id=(org.ksm_node_id if org else "") or "", deal_opinion=supply_note)
    return await get_feishu().send_text(f"【工单 {info.ticket_no} 需要您提供】\n{supply_note}")


async def writeback_return(session: AsyncSession, info: TicketInfo, reason: str) -> dict:
    """人工退回工单：KSM 调 returnKsmOrder(dry_run)；智齿/assistant 仅本地标记+通知。"""
    src = info.source
    if src == Source.KSM.value:
        org = await _org(session, info.id)
        steps = (org.ksm_handle_steps if org else None) or []
        oper = ""
        for s in sorted(steps, key=lambda x: x.get("handleDateTime", ""), reverse=True):
            if s.get("nodeName") and s.get("nodeName") != "协同处理":
                oper = s.get("opercacheId", "")
                break
        return await get_ksm().return_order(
            bill_id=(org.org_bill_id if org else info.source_id), account=settings.ksm_handler_name,
            account_name=settings.ksm_handler_name, account_number=settings.ksm_handler_number,
            current_node_id=(org.ksm_node_id if org else "") or "", opercache_id=oper, deal_opinion=reason)
    await get_feishu().send_text(f"【工单退回】{info.ticket_no} {reason}")
    return {"returned": True}


async def writeback_not_takeover(session: AsyncSession, info: TicketInfo, talk: str) -> dict:
    """不接管：KSM 零回写 / 智齿 固定话术+已解决3 / assistant 私信。"""
    src = info.source
    if src == Source.ZHICHI.value:
        return await get_zhichi().close_with_reply(
            ticketid=info.source_id, title=info.title, content=info.description, reply=talk)
    if src == Source.KSM.value:
        logger.info("KSM 不接管=对客户零回写 ticket=%s", info.ticket_no)
        return {"no_writeback": True}
    return await get_feishu().send_text(f"【工单 {info.ticket_no}】{talk}")
