"""流水线 harness：唯一读写 DB 的编排层。run_step 包裹每步统一写 t_skill_log。

Skill 纯函数(入payload出信封)；harness 负责取数/落库/分支。
铁律：退回单(is_returned)末端强制转人工 pending_manual，不自动回写客户。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import ZHICHI_NOT_TAKEOVER_REPLY, HUB_NO_PREFIX
from app.common.enums import AnswerBranch, Source, StepStatus, TicketStatus, TransferResult
from app.common.utils.vector import cosine
from app.core.config import settings
from app.core.logging import new_trace_id
from app.integrations.agent_client import get_agent
from app.integrations.feishu_client import get_feishu
from app.integrations.ksm_client import get_ksm
from app.integrations.linear_client import get_linear
from app.integrations.siliconflow_client import get_siliconflow
from app.modules.ai.models import SkillLog
from app.modules.ai.skill_runner import run_skill
from app.modules.ai.skills.answer_extract import extract_answer
from app.modules.knowledge import repository as kb_repo
from app.modules.ticket import repository as ticket_repo
from app.modules.ticket.models import TicketHub, TicketInfo, TicketOrg
from app.pipeline import writeback
from app.pipeline.context import RunContext

logger = logging.getLogger("ticket_hub.pipeline")

StepFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_step(session: AsyncSession, ctx: RunContext, name: str, fn: StepFn,
                   payload: dict[str, Any], *, step_no: Optional[str] = None) -> dict[str, Any]:
    """执行一步并落 t_skill_log。返回信封；失败不抛(harness 兜底)。"""
    start = time.perf_counter()
    status = StepStatus.OK.value
    result: dict[str, Any] = {}
    error: Optional[str] = None
    try:
        result = await fn(payload) or {}
        status = result.get("status", StepStatus.OK.value)
    except Exception as exc:  # noqa: BLE001
        status = StepStatus.FAILED.value
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("step %s failed (ticket=%s)", name, ctx.ticket_id)
    session.add(SkillLog(
        trace_id=ctx.trace_id, ticket_id=ctx.ticket_id, hub_id=ctx.hub_id, skill_name=name, step_no=step_no,
        status=status, result_json=result.get("fields") if isinstance(result, dict) else None,
        evidence=result.get("evidence") if isinstance(result, dict) else None,
        model_used=result.get("model_used") if isinstance(result, dict) else None,
        duration_ms=int((time.perf_counter() - start) * 1000), error_msg=error))
    await session.flush()
    if error is not None:
        return {"status": StepStatus.FAILED.value, "error": error, "fields": {}}
    return result


# ---- 非 LLM 步骤包成信封以便 run_step 落日志 ----
def _wrap(coro_factory: Callable[[dict], Awaitable[dict]]) -> StepFn:
    async def _fn(payload: dict) -> dict:
        fields = await coro_factory(payload)
        return {"status": "ok", "fields": fields, "model_used": fields.pop("_model", "")}
    return _fn


async def _refresh_after_lock(session, info) -> None:
    """接管成功后重拉 subscribeCallback，刷新 org 的节点/产品/版本/模块（KSM 文档：handle 取最新详情 node.id）。"""
    org = (await session.execute(select(TicketOrg).where(TicketOrg.ticket_id == info.id))).scalar_one_or_none()
    if org is None or not org.ksm_notice_num:
        logger.warning("接管后无 notice_num，跳过重拉 ticket=%s（handle 可能用旧节点）", info.ticket_no)
        return
    try:
        raw = await get_ksm().subscribe_callback(org.ksm_notice_num, subscribe_num="ksm_feedback_change",
                                                 bill_id=org.org_bill_id or info.source_id)
    except Exception:  # noqa: BLE001 重拉失败用旧节点继续（writeback 失败会转人工）
        logger.exception("接管后重拉详情失败 ticket=%s", info.ticket_no)
        return
    if not raw:
        return
    node = raw.get("node") or {}
    prod = raw.get("product") or {}
    ver = raw.get("version") or {}
    mod = raw.get("module") or {}
    if node.get("id"):
        org.ksm_node_id = node.get("id"); org.ksm_node_name = node.get("name")
    if prod.get("id"):
        org.ksm_product_id = prod.get("id")
    if ver.get("id"):
        org.ksm_version_id = ver.get("id")
    if mod.get("id"):
        org.ksm_module_id = mod.get("id")
    if raw.get("feedbackType") is not None:
        org.ksm_feedback_type = str(raw.get("feedbackType"))
    await session.flush()
    logger.info("接管后刷新节点 ticket=%s node=%s(%s)", info.ticket_no, org.ksm_node_id, org.ksm_node_name)


async def _writeback_failed_to_manual(session, info, what: str, err: str, *, reply: Optional[str] = None) -> None:
    """对外回写失败 → 转人工(pending_manual) + 飞书告警，不卡死整单、不静默置完成。"""
    logger.error("回写失败转人工 ticket=%s %s: %s", info.ticket_no, what, (err or "")[:300])
    try:
        await get_feishu().send_text(f"【回写失败-转人工】{info.ticket_no} {what} 失败：{(err or '')[:200]}")
    except Exception:  # noqa: BLE001 告警失败不阻断
        logger.exception("回写失败告警发送异常 ticket=%s", info.ticket_no)
    fields = {"status": TicketStatus.PENDING_MANUAL.value, "writeback_status": "failed", "updated_by": "system"}
    if reply is not None:
        fields["final_reply"] = reply
    await ticket_repo.update_info(session, info, **fields)


async def _close_done(session: AsyncSession, ctx: RunContext, info: TicketInfo, reply: str) -> bool:
    """回写关单 + 记 resolved_at + status=done。回写失败 → 转人工，返回 False。"""
    r = await run_step(session, ctx, "writeback",
                       _wrap(lambda p: writeback.writeback_close(session, info, reply)), {}, step_no="WB")
    if r.get("status") == StepStatus.FAILED.value:
        await _writeback_failed_to_manual(session, info, "答复关单回写", r.get("error", ""), reply=reply)
        return False
    await ticket_repo.update_info(session, info, final_reply=reply, status=TicketStatus.DONE.value,
                                  writeback_status="success", resolved_at=_now())
    return True


async def run_pipeline(session: AsyncSession, info_id: int, trace_id: str) -> None:
    """v2.1 双源分流：KSM 走完整 AI 流水线，智齿走简化流水线（不走流转判断/agent）。"""
    info = await session.get(TicketInfo, info_id)
    if info is None:
        logger.warning("run_pipeline: info %s 不存在", info_id)
        return
    detail = await ticket_repo.get_detail(session, info_id)
    ctx = RunContext(trace_id=trace_id, ticket_id=info_id, source=info.source, is_returned=info.is_returned)
    desc = info.description or ""

    # 退回单：直接转人工，不跑流水线（KSM/智齿同）
    if info.is_returned:
        await _dispatch(session, info, branch="退回单", reply=desc, status=TicketStatus.PENDING_MANUAL.value)
        return

    if info.source == Source.ZHICHI.value:
        await _run_zhichi(session, ctx, info, detail, desc)
    else:
        await _run_ksm(session, ctx, info, detail, desc)


async def _tagging(session, ctx, info, detail, desc) -> tuple[str, str]:
    """S2 打标：产品线 + 问题模块 + 责任田负责人。

    问题模块：统一由 AI 对客户问题做语义判断，从候选(受产品线约束，数据源=模块责任人列表)中选取，
    不再直接采用来源推送的 module(其颗粒度笼统、常不准，如"开票管理")——来源 module 仅作参考喂给 AI。
    责任田负责人：产品线+问题模块均非空 → 用「产品线+模块」查 t_module_owner 取责任人写入。
    """
    cands = await ticket_repo.module_candidates(session)
    s2 = await run_step(session, ctx, "ticket-tagging", lambda p: run_skill("ticket-tagging", p), {
        "title": info.title, "description": desc, "product_name": detail.product_name_raw if detail else "",
        "module": detail.module_raw if detail else "", "candidates": cands,
    }, step_no="S2")
    f2 = s2.get("fields", {})
    product = f2.get("ai_product_tag") or f2.get("product_tag") or "无法判断"
    module = f2.get("ai_func_module") or f2.get("func_module") or ""  # 统一取 AI 语义判定结果
    # 责任田负责人：产品线+问题模块查表
    dev_owner = None
    if module and product and product != "无法判断":
        dev_owner = await ticket_repo.lookup_dev_owner(session, module, product_tag=product)
    await ticket_repo.update_info(session, info, ai_product_tag=product, ai_func_module=module,
                                  ai_dev_owner=dev_owner or settings.default_dev_owner,
                                  dev_owner_missing=(dev_owner is None))
    return product, module


async def _run_ksm(session, ctx, info, detail, desc) -> None:
    # ---------- S1 流转判断 ----------
    s1 = await run_step(session, ctx, "ticket-routable", lambda p: run_skill("ticket-routable", p), {
        "title": info.title, "description": desc,
        "product_name": detail.product_name_raw if detail else "",
        "module": detail.module_raw if detail else "", "has_attachment": info.has_attachment,
    }, step_no="S1")
    if s1.get("status") == StepStatus.FAILED.value:
        raise RuntimeError("S1 routable 失败 → 任务挂起重试")  # worker mark_failed/退避
    f1 = s1["fields"]
    routable = f1.get("routable")
    route_action = f1.get("route_action") or ""
    await ticket_repo.update_info(session, info, routable=bool(routable), route_action=route_action,
                                  route_reason=f1.get("route_reason"))
    if routable is False or "不接管" in str(route_action):
        await writeback.writeback_not_takeover(session, info, ZHICHI_NOT_TAKEOVER_REPLY)
        await get_feishu().send_text(f"【不接管】{info.ticket_no} {route_action}")
        await ticket_repo.update_info(session, info, status=TicketStatus.RETURNED.value)
        return

    # 可流转 → lockKsmOrder 接管（失败→转人工，不卡死整单）
    lr = await run_step(session, ctx, "writeback-lock", _wrap(lambda p: get_ksm().lock_order(
        bill_id=info.source_id, account=settings.ksm_handler_name,
        account_name=settings.ksm_handler_name, account_number=settings.ksm_handler_number)), {}, step_no="WB-LOCK")
    if lr.get("status") == StepStatus.FAILED.value:
        await _writeback_failed_to_manual(session, info, "接管(lockKsmOrder)", lr.get("error", ""))
        return
    # 接管会让工单节点流转 → 重新拉取最新详情刷新节点/产品/版本/模块(供后续 handle/supply 用最新 node)
    await _refresh_after_lock(session, info)

    # ---------- S2 打标（责任人后置到 A/B）----------
    product, module = await _tagging(session, ctx, info, detail, desc)

    # ---------- S3 info-dedup 短路 ----------
    reuse_reply = await _info_dedup(session, ctx, info, desc, product)
    if reuse_reply is not None:
        await ticket_repo.update_info(session, info, is_duplicate=True)
        await _close_done(session, ctx, info, reuse_reply)   # handleKsmOrder 回写
        return

    # ---------- S6 agent 答复（入参拼装"{产品线}-{功能模块}：{原始问题}"，agent 自处理脱敏）----------
    aq = f"{product}-{module}：{desc}" if module else f"{product}：{desc}"
    s6 = await run_step(session, ctx, "agent-answer", _wrap(lambda p: get_agent().ask(aq)), {}, step_no="S6")
    a6 = s6.get("fields", {})
    answer = a6.get("answer") or ""
    transfer = a6.get("transfer_result") or TransferResult.NO_ACTION.value

    # ---------- S7 分支路由 ----------
    if s6.get("status") == StepStatus.FAILED.value or not answer or transfer == TransferResult.TRANSFER.value:
        branch = AnswerBranch.C_SUPPLEMENT.value
    else:
        s7 = await run_step(session, ctx, "answer-router", lambda p: run_skill("answer-router", p),
                            {"question": desc, "agent_answer": answer}, step_no="S7")
        branch = (s7.get("fields", {}).get("answer_branch") or "C").strip().upper()[:1]
        if branch not in ("A", "B", "C", "D"):
            branch = "C"

    ext = extract_answer(answer)
    await ticket_repo.update_info(session, info, answer_branch=branch, transfer_result=transfer)
    await ticket_repo.update_detail(session, info.id, ai_reply=answer, full_reply=ext["full_reply"], supply_note=ext["supply_note"])

    # ---------- A/B → Linear；C → unlock 退回客户；D → 直接答复关单 ----------
    if branch in ("A", "B"):
        await _branch_to_rd(session, ctx, info, product, module, ext["full_reply"] or answer, branch)
    elif branch == "C":  # 资料缺失：退回客户，状态置「补充资料」(supplement)
        await _branch_c_supplement(session, ctx, info, ext["supply_note"] or ext["full_reply"] or answer)
    else:  # D
        await _branch_d_normal(session, ctx, info, product, ext["final_reply"] or answer)


async def _run_zhichi(session, ctx, info, detail, desc) -> None:
    """智齿简化流水线：打标(含责任田负责人) → info-dedup（命中回写 / 未命中转人工），不走流转判断/agent。"""
    product, module = await _tagging(session, ctx, info, detail, desc)  # _tagging 内已按产品线+模块写责任田负责人
    # info-dedup 短路
    reuse_reply = await _info_dedup(session, ctx, info, desc, product)
    if reuse_reply is not None:
        await ticket_repo.update_info(session, info, is_duplicate=True)
        await _close_done(session, ctx, info, reuse_reply)   # save_ticket_reply 回写(writeback_close 内分流)
        return
    # 未命中 → 转人工
    await _dispatch(session, info, branch="智齿", reply=desc, status=TicketStatus.PENDING_MANUAL.value)


async def _branch_c_supplement(session, ctx, info, supply_note) -> None:
    """C 资料缺失：supplyKsmOrder 补充资料退回客户 → 飞书通知客服；info 状态置「补充资料」。回写失败→转人工。"""
    r = await run_step(session, ctx, "writeback-supply",
                       _wrap(lambda p: writeback.writeback_supply(session, info, supply_note)), {}, step_no="WB-C")
    if r.get("status") == StepStatus.FAILED.value:
        await _writeback_failed_to_manual(session, info, "补充资料(supplyKsmOrder)", r.get("error", ""))
        return
    await get_feishu().send_text(f"【资料缺失C-退回客户补充】{info.ticket_no}\n{(supply_note or '')[:200]}")
    await ticket_repo.update_info(session, info, status=TicketStatus.SUPPLEMENT.value)


async def _info_dedup(session, ctx, info, desc, product) -> Optional[str]:
    """S3：硅基召回+LLM确认，命中且有有效答复→返回复用答复，否则 None。"""
    cands = await ticket_repo.dedup_candidates(session, product_tag=product, exclude_id=info.id)
    if not cands:
        return None
    try:
        embs = await get_siliconflow().embed([f"{info.title} {desc}"] + [f"{c.title} {c.description}" for c in cands])
    except Exception:  # noqa: BLE001 硅基挂→降级非重复
        return None
    q = embs[0]
    scored = sorted(((cosine(q, embs[i + 1]), c) for i, c in enumerate(cands)), key=lambda t: t[0], reverse=True)
    top = [(s, c) for s, c in scored[:8] if s >= settings.info_dedup_threshold]
    if not top:
        return None
    cand_list = [{"id": c.id, "text": f"{c.title} {c.description}", "score": round(s, 3)} for s, c in top]
    r = await run_step(session, ctx, "info-dedup", lambda p: run_skill("info-dedup", p),
                       {"current": f"{info.title} {desc}", "candidates": cand_list}, step_no="S3")
    fields = r.get("fields", {})
    if fields.get("is_duplicate") and fields.get("dup_ticket_ids"):
        dup_id = fields["dup_ticket_ids"][0] if isinstance(fields["dup_ticket_ids"], list) else fields.get("reused_from_ticket_id")
        src = next((c for _, c in top if c.id == dup_id), top[0][1])
        if src.final_reply:
            await ticket_repo.update_info(session, info, reused_from_ticket_id=src.id)
            return src.final_reply
    return None


async def _hub_dedup(session, ctx, info, product, full_reply, emb) -> Optional[int]:
    """S8 hub 查重：硅基召回同产品线历史 hub → hub-dedup 语义确认。命中返回已有 hub_id，否则 None。

    降级（嵌入/召回/LLM 失败）一律 None=新建，宁可重复也不漏单。
    """
    if emb is None:
        return None
    cands = await ticket_repo.hub_candidates(session, product_tag=product)
    if not cands:
        return None
    scored = sorted(((cosine(emb, c.embedding), c) for c in cands if c.embedding), key=lambda t: t[0], reverse=True)
    top = [(s, c) for s, c in scored[:5] if s >= settings.hub_dedup_threshold]
    if not top:
        return None
    cand_list = [{"hub_id": c.id, "title": c.title, "problem_summary": c.problem_summary or "",
                  "similarity": round(s, 3)} for s, c in top]
    r = await run_step(session, ctx, "hub-dedup", lambda p: run_skill("hub-dedup", p), {
        "current_problem": f"{info.title} {full_reply or info.description}",
        "product_tag": product, "func_module": info.ai_func_module or "",
        "candidates": cand_list, "threshold": settings.hub_dedup_threshold,
    }, step_no="S8")
    f = r.get("fields", {})
    if f.get("is_dup") and f.get("dup_hub_id"):
        dup_id = f["dup_hub_id"]
        return dup_id if any(c.id == dup_id for _, c in top) else top[0][1].id
    return None


async def _branch_to_rd(session, ctx, info, product, module, full_reply, branch) -> None:
    """A bug / B 需求：责任人后置查表 → hub 查重(命中关联已有 hub、不新建 Linear) → 否则新建 hub+Linear → pending_rd。

    保证 hub 唯一且与 Linear 一一对应：仅在新建 hub 时创建 Linear issue。
    """
    dev_owner = await ticket_repo.lookup_dev_owner(session, module, product_tag=product)
    dev_missing = dev_owner is None
    if dev_missing:
        dev_owner = settings.default_dev_owner
    await ticket_repo.update_info(session, info, ai_dev_owner=dev_owner, dev_owner_missing=dev_missing)

    # 嵌入一次：既用于查重召回，又在新建时存入 hub.embedding（供后续查重）
    try:
        emb = await get_siliconflow().embed_one(f"{info.title} {full_reply or info.description}")
    except Exception:  # noqa: BLE001
        emb = None

    # hub 查重：命中则关联已有 hub，绝不新建 Linear（一 hub 一 Linear）
    dup_hub_id = await _hub_dedup(session, ctx, info, product, full_reply, emb)
    if dup_hub_id is not None:
        await ticket_repo.update_info(session, info, rd_hub_id=dup_hub_id, is_duplicate=True,
                                      status=TicketStatus.PENDING_RD.value)
        await get_feishu().send_text(f"【转研发{branch}-关联已有hub】{info.ticket_no} → hub#{dup_hub_id}（不重复推 Linear）")
        return

    # 未命中 → 新建唯一 hub（存 embedding）+ 唯一 Linear issue
    seq = (await session.execute(text("SELECT nextval('seq_hub_no')"))).scalar_one()
    hub_no = f"{HUB_NO_PREFIX}{_now().strftime('%Y%m%d')}{int(seq):06d}"
    hub = TicketHub(hub_no=hub_no, title=info.title, problem_summary=info.description, full_reply=full_reply,
                    product_tag=product, func_module=module, dev_owner=dev_owner, embedding=emb,
                    rd_sla_start_at=_now(), status="待处理", created_by="pipeline")
    session.add(hub)
    await session.flush()
    # Linear 建 issue 失败不崩整单：hub 保留、标记 failed 可后续重试同步(resync-linear)
    try:
        issue = await get_linear().create_issue(title=f"[{info.ticket_no}] {info.title}", description=full_reply or info.description)
        hub.linear_issue_id = issue.get("id") or ""
        hub.linear_url = issue.get("url") or ""
        hub.linear_sync_status = "synced" if not issue.get("dry_run") else "pending"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Linear 建 issue 失败 ticket=%s hub=%s", info.ticket_no, hub_no)
        hub.linear_sync_status = "failed"
        try:
            await get_feishu().send_text(f"【Linear 同步失败-待重试】{info.ticket_no} → hub {hub_no}：{str(exc)[:160]}")
        except Exception:  # noqa: BLE001
            pass
    await ticket_repo.update_info(session, info, rd_hub_id=hub.id, status=TicketStatus.PENDING_RD.value)
    await session.flush()
    await get_feishu().send_text(f"【转研发{branch}-新建hub】{info.ticket_no} → hub {hub_no} (责任人{dev_owner})")


async def _branch_d_normal(session, ctx, info, product, final_reply) -> None:
    """D 正常：reply-humanize → 回写关单（agent 已脱敏，不再脱敏）。FAQ 收录改由 C/B 人工关单触发。"""
    h = await run_step(session, ctx, "reply-humanize", lambda p: run_skill("reply-humanize", p),
                       {"reply": final_reply}, step_no="S6.5")
    humanized = h.get("fields", {}).get("humanized_reply") or final_reply  # 失败用原文
    await ticket_repo.update_detail(session, info.id, humanized_reply=humanized)
    await _close_done(session, ctx, info, humanized)


async def faq_record_on_close(session, info) -> None:
    """C/B 工单人工关单后触发 FAQ 收录（失败不阻断）。"""
    if info.answer_branch not in (AnswerBranch.B_REQUIREMENT.value, AnswerBranch.C_SUPPLEMENT.value):
        return
    ctx = RunContext(trace_id=new_trace_id(), ticket_id=info.id, source=info.source, is_returned=info.is_returned)
    try:
        await _faq_record(session, ctx, info, info.ai_product_tag or "无法判断", info.final_reply or "")
    except Exception:  # noqa: BLE001
        logger.exception("FAQ 收录(关单触发)失败 ticket=%s", info.ticket_no)


async def _faq_record(session, ctx, info, product, final) -> None:
    # 收录前去重 0.85
    cands = await kb_repo.dedup_candidates(session, product)
    try:
        emb = await get_siliconflow().embed_one(final)
    except Exception:  # noqa: BLE001
        emb = None
    if emb and cands:
        for c in cands:
            if cosine(emb, c.get("embedding")) >= settings.faq_dedup_threshold:
                return  # 已有类似，不收录
    rec = await run_step(session, ctx, "faq-record", lambda p: run_skill("faq-record", p),
                         {"description": info.description, "final_reply": final}, step_no="S10")
    rf = rec.get("fields", {})
    title = rf.get("faq_title") or rf.get("title")
    content = rf.get("faq_content") or rf.get("content")
    if not (title and content):
        return
    faq = await kb_repo.create_faq(session, title=title, content=content, product_tag=product,
                                   source_ticket_id=info.id, embedding=emb)
    # 审核(不阻断)
    rv = await run_step(session, ctx, "faq-review", lambda p: run_skill("faq-review", p),
                        {"title": title, "content": content}, step_no="S11")
    vf = rv.get("fields", {})
    approved = vf.get("approved")
    if approved is True:
        await kb_repo.set_review(session, faq.id, result="approved", reason=vf.get("reason", ""))
    elif approved is False:
        await kb_repo.set_review(session, faq.id, result="rejected", reason=vf.get("reason", ""),
                                 reject_dims=str(vf.get("reject_dims", "")))
        await get_feishu().send_text(f"【FAQ驳回】{faq.faq_no} {title} 原因:{vf.get('reason','')}")


async def _dispatch(session, info, *, branch, reply, status=None) -> None:
    """转人工派单(简版：默认人 + 飞书@)；完整配额在 dispatch 模块。"""
    from app.modules.dispatch.models import DispatchAssignee, DispatchConfig
    from sqlalchemy import select
    assignee = (await session.execute(
        select(DispatchAssignee).where(DispatchAssignee.tier == "main", DispatchAssignee.is_active.is_(True))
    )).scalars().first()
    name = assignee.assignee_name if assignee else None
    if not name:
        cfg = (await session.execute(select(DispatchConfig).where(DispatchConfig.config_key == "default_assignee"))).scalar_one_or_none()
        name = cfg.config_value if cfg else settings.default_dev_owner
    await ticket_repo.update_info(session, info, dispatch_assignee=name, dispatched_at=_now(),
                                  status=status or TicketStatus.PENDING_MANUAL.value)
    await get_feishu().send_text(f"【转人工{branch}】{info.ticket_no} → @{name}\n{(reply or '')[:200]}")
