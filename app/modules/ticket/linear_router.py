"""Linear 回调分派（POST /webhook/linear，流程10）。

回写三字段 status/handler/note → 镜像 hub + 所有关联 info；按 status 精确分派：
计划+发版日期(LLM提取)→自动答复关单所有关联info；计划无日期/产研退回空→转回Linear；产研退回非空→转人工。
出站(转回/答复)经 dry_run。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import LINEAR_PLAN_REPLY_TPL
from app.common.enums import TicketStatus
from app.core.response import success
from app.core.security import verify_webhook_token
from app.db.session import get_db
from app.integrations.feishu_client import get_feishu
from app.integrations.linear_client import get_linear
from app.modules.ai.llm_gateway import chat
from app.modules.ticket import repository as ticket_repo
from app.modules.ticket.models import TicketHub, TicketInfo
from app.pipeline import writeback

logger = logging.getLogger("ticket_hub.linear")
router = APIRouter(tags=["linear"])
_DATE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}[-/月]\d{1,2}")


async def _extract_date(note: str) -> str:
    m = _DATE.search(note or "")
    if m:
        return m.group(0)
    try:
        txt, _ = await chat(system="从文本提取发版日期，只回日期字符串，无则回 NONE", user=note or "", max_tokens=20)
        txt = txt.strip()
        return "" if "NONE" in txt.upper() or not txt else txt
    except Exception:  # noqa: BLE001
        return ""


@router.post("/webhook/linear", dependencies=[Depends(verify_webhook_token)])
async def linear_callback(payload: dict[str, Any], session: AsyncSession = Depends(get_db)):
    # 兼容两种来源：
    #  ① 自定义中转报文 {issue_id,status,handler,note} → 走完整工作流(计划自动关单/产研退回转人工)
    #  ② Linear 原生 webhook {type:"Issue", action, data:{id,state:{name},assignee:{name},...}} → 即时镜像状态
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    native = payload.get("status") is None and not (payload.get("issue_id") or payload.get("issueId")) and bool(data.get("state"))
    if native:
        issue_id = data.get("id")
        status = ((data.get("state") or {}).get("name") or "").strip()
        handler = (data.get("assignee") or {}).get("name") or ""
        note = ""
    else:
        issue_id = payload.get("issue_id") or payload.get("issueId") or data.get("id")
        status = (payload.get("status") or "").strip()
        handler = payload.get("handler") or ""
        note = payload.get("note") or ""
    if not issue_id:
        return success({"ok": False, "msg": "缺少 issue_id"})

    hub = (await session.execute(select(TicketHub).where(TicketHub.linear_issue_id == str(issue_id)))).scalar_one_or_none()
    if hub is None:
        logger.warning("Linear 回调未找到 hub issue_id=%s", issue_id)
        return success({"ok": False, "msg": "hub 不存在"})

    # 镜像 hub + 所有关联 info（note/handler 仅在有值时覆盖，避免原生 webhook 把已有说明清空）
    if note:
        hub.rd_status_note = note
    if handler:
        hub.rd_handler = handler
    hub.rd_callback_at = datetime.now(timezone.utc)
    hub.status = status or hub.status
    infos = list((await session.execute(select(TicketInfo).where(TicketInfo.rd_hub_id == hub.id))).scalars())
    for info in infos:
        fields = {"rd_status": status}
        if handler:
            fields["rd_handler"] = handler
        if note:
            fields["rd_status_note"] = note
        await ticket_repo.update_info(session, info, **fields)

    # 原生 webhook 只镜像状态，不触发自动关单/转人工(那些副作用属中转工作流，避免重复处理/刷评论)
    action = "display"
    if not native and status == "计划":
        date = await _extract_date(note)
        if date:
            reply = LINEAR_PLAN_REPLY_TPL.format(date=date)  # 固定模板不脱敏
            for info in infos:
                await writeback.writeback_close(session, info, reply)
                await ticket_repo.update_info(session, info, final_reply=reply, status=TicketStatus.DONE.value,
                                              resolved_at=datetime.now(timezone.utc), writeback_status="success")
            hub.rd_resolved_at = datetime.now(timezone.utc)  # 停 SLA-2
            action = "auto_close"
        else:
            await get_linear().create_comment(str(issue_id), "未有具体发版日期")
            action = "return_linear_no_date"
    elif not native and status == "产研退回":
        if note.strip():
            await get_feishu().send_text(f"【研发退回转人工】hub {hub.hub_no}: {note}")
            for info in infos:
                await ticket_repo.update_info(session, info, status=TicketStatus.PENDING_MANUAL.value)
            action = "to_manual"
        else:
            await get_linear().create_comment(str(issue_id), "未有退回原因")
            action = "return_linear_no_reason"

    await session.commit()
    logger.info("Linear 回调 hub=%s status=%s action=%s", hub.hub_no, status, action)
    return success({"ok": True, "action": action})
