"""智能助手：只读 NL2SQL 统计 + 对话提单。

NL→SQL 提示词在 assistant-nl2sql SKILL(可热改)；护栏在 sql_guard(py)。
提单：校验(非空/≥15字/5分钟防重)→建 source=assistant 工单→入队 run_pipeline。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import ASSISTANT_DEDUP_WINDOW_SEC, MIN_DESC_LEN
from app.common.enums import Source, TaskType
from app.core.exceptions import BizException
from app.core.logging import new_trace_id
from app.db import queue
from app.modules.ai.skill_runner import run_skill
from app.modules.assistant import sql_guard
from app.modules.assistant.models import AssistantLog
from app.modules.ticket import repository as ticket_repo
from app.modules.ticket.models import TicketInfo

logger = logging.getLogger("ticket_hub.assistant")

# 给 LLM 的库表 schema 提示（核心可查表）
SCHEMA_HINT = (
    "可查表(PostgreSQL): "
    "t_ticket_info(id,ticket_no,source,status,ai_product_tag,ai_func_module,ai_dev_owner,answer_branch,"
    "is_returned,return_count,sla_state,created_at,resolved_at); "
    "t_ticket_hub(id,hub_no,dev_owner,status,rd_sla_state,created_at); "
    "t_faq(id,faq_no,title,product_tag,review_status,hit_count,created_at); "
    "t_sla_log(sla_type,owner,notify_date,overdue_hours); "
    "t_users(id,name,role,is_active). "
    "status枚举: pending/returned/pending_manual/pending_rd/done/closed。source: ksm/zhichi/assistant。"
)


async def nl2sql_query(session: AsyncSession, *, nl: str, role: str, user_uid: str, session_id: str = "") -> dict:
    res = await run_skill("assistant-nl2sql", {"question": nl, "schema": SCHEMA_HINT})
    sql_raw = res.get("fields", {}).get("sql") or res.get("fields", {}).get("generated_sql") or ""
    log = AssistantLog(user_uid=user_uid, user_role=role, session_id=session_id, nl_query=nl,
                       generated_sql=sql_raw, op_type="query", created_by=user_uid)
    try:
        guarded = sql_guard.guard_sql(sql_raw)
    except BizException as e:
        log.sql_guard_pass = False
        log.error_msg = e.message
        session.add(log)
        await session.flush()
        raise
    log.sql_guard_pass = True
    try:
        result = await session.execute(text(guarded))
        rows = [dict(r._mapping) for r in result]
    except Exception as e:  # noqa: BLE001
        log.error_msg = str(e)[:500]
        session.add(log)
        await session.flush()
        raise BizException("查询执行失败，请换种问法", code=400)
    masked = sql_guard.mask_rows(rows, role)
    pii = role not in ("admin", "handler")
    log.result_rows = len(masked)
    log.pii_masked = pii
    session.add(log)
    await session.flush()
    return {"type": "query", "sql": guarded if role == "admin" else None,
            "result": masked, "rowCount": len(masked), "explain": res.get("evidence", "")}


async def submit_ticket(session: AsyncSession, *, title: str, description: str, submitter_uid: str) -> dict:
    if not title.strip() or not description.strip():
        raise BizException("标题和描述不能为空", code=422)
    if len(description.strip()) < MIN_DESC_LEN:
        raise BizException(f"描述至少 {MIN_DESC_LEN} 字", code=422)
    # 防重复：同人 + 相同标题描述 + 5 分钟内
    since = datetime.now(timezone.utc) - timedelta(seconds=ASSISTANT_DEDUP_WINDOW_SEC)
    dup = (await session.execute(select(TicketInfo).where(
        TicketInfo.source == Source.ASSISTANT.value, TicketInfo.assistant_submitter_uid == submitter_uid,
        TicketInfo.title == title, TicketInfo.created_at >= since, TicketInfo.is_deleted.is_(False),
    ))).scalar_one_or_none()
    if dup is not None:
        raise BizException("疑似重复提单（5分钟内相同标题）", code=400)
    source_id = f"AST-{submitter_uid}-{int(datetime.now(timezone.utc).timestamp())}"
    info = await ticket_repo.create_ticket(
        session, source=Source.ASSISTANT.value, source_id=source_id, has_attachment=False,
        info_fields={"title": title, "description": description, "assistant_submitter_uid": submitter_uid},
        detail_fields={}, org_fields={"source": Source.ASSISTANT.value})
    await queue.enqueue(session, TaskType.RUN_PIPELINE, {"info_id": info.id, "trace_id": new_trace_id()},
                        dedup_key=f"run_pipeline:{info.id}")
    session.add(AssistantLog(user_uid=submitter_uid, nl_query=title, op_type="submit", created_by=submitter_uid))
    await session.flush()
    return {"type": "submit", "ticketNo": info.ticket_no, "ticketId": info.id}
