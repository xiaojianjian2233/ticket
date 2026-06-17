"""入站归一：来源 raw → 归一字段（info / detail / org 三层）。

本期实现智齿（webhook 自带全量）；KSM 归一待 subscribeCallback 拉全量后接入。
PII（联系人/手机/邮箱）只落 detail/org，不进 info（前端只展示 info）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.common.enums import Source

_BEIJING = timezone(timedelta(hours=8))


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """解析智齿 'YYYY-MM-DD HH:MM:SS'（北京时间）→ aware datetime。"""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BEIJING)
    except (ValueError, AttributeError):
        return None


def _parse_extends(lst: Optional[list[dict[str, Any]]]) -> dict[str, str]:
    """智齿 extend_fields_list → {field_name: value}；field_type=6 取 field_text，其余取 field_value。"""
    out: dict[str, str] = {}
    for f in lst or []:
        name = f.get("field_name")
        if not name:
            continue
        val = f.get("field_text") if str(f.get("field_type")) == "6" else f.get("field_value")
        if val:
            out[name] = val
    return out


@dataclass
class NormalizedTicket:
    """归一结果：分三层落库。"""

    source: str
    source_id: str
    has_attachment: bool
    attachment_urls: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)     # t_ticket_info 归一字段
    detail: dict[str, Any] = field(default_factory=dict)   # t_ticket_detail（含 PII / raw_json）
    org: dict[str, Any] = field(default_factory=dict)      # t_ticket_org 原始结构化


def normalize_zhichi(raw: dict[str, Any]) -> NormalizedTicket:
    """智齿 raw → NormalizedTicket（字段映射见 工单参数.txt / 智齿接口速查.md）。"""
    ext = _parse_extends(raw.get("extend_fields_list"))
    source_id = str(raw.get("ticketid") or "")
    file_str = raw.get("file_str") or ""
    attachment_urls = [u for u in file_str.replace("；", ";").split(";") if u.strip()]
    product = ext.get("产品分类")

    info = {
        "source_bill_no": raw.get("ticket_code"),
        "title": raw.get("ticket_title") or "",
        "description": raw.get("ticket_content") or "",
        "customer_company": raw.get("enterprise_name"),
    }
    detail = {
        "customer_contact": ext.get("联系人"),
        "customer_mobile": ext.get("联系手机"),
        "customer_email": raw.get("user_emails"),
        "product_name_raw": product,
        "module_raw": product,  # 智齿无独立模块，产品分类即模块
        "raw_json": raw,
    }
    org = {
        "source": Source.ZHICHI.value,
        "org_bill_id": source_id,
        "org_bill_no": raw.get("ticket_code"),
        "org_title": raw.get("ticket_title"),
        "org_content": raw.get("ticket_content"),
        "org_status": str(raw.get("ticket_status")) if raw.get("ticket_status") is not None else None,
        "org_urgency": str(raw.get("ticket_level")) if raw.get("ticket_level") is not None else None,
        "org_create_time": _parse_dt(raw.get("create_time")),
        "org_update_time": _parse_dt(raw.get("update_time")),
        "org_customer_name": raw.get("enterprise_name"),
        "org_email": raw.get("user_emails"),
        "org_assign_user": raw.get("deal_agent_name"),
        "org_product_name": product,
        "org_module_name": product,
        "zhichi_deal_agent": raw.get("deal_agent_name"),
        "zhichi_erp": ext.get("对接ERP"),
        "zhichi_project_name": ext.get("公司/项目名称"),
        "zhichi_extend_fields": raw.get("extend_fields_list"),
    }
    return NormalizedTicket(
        source=Source.ZHICHI.value,
        source_id=source_id,
        has_attachment=bool(attachment_urls),
        attachment_urls=attachment_urls,
        info=info,
        detail=detail,
        org=org,
    )


def normalize_ksm(raw: dict[str, Any]) -> NormalizedTicket:
    """KSM raw → NormalizedTicket（字段映射见 工单参数.txt / KSM接口速查.md）。"""
    ci = raw.get("customerInfo") or {}
    prod = raw.get("product") or {}
    ver = raw.get("version") or {}
    mod = raw.get("module") or {}
    node = raw.get("node") or {}
    assign = raw.get("assignUser") or {}
    sponsor = raw.get("sponser") or {}
    source_id = str(raw.get("billId") or raw.get("billNumber") or "")
    atts = [a.get("url") for a in (raw.get("attachment") or []) if a.get("url")]

    info = {
        "source_bill_no": raw.get("billNumber"),
        "title": raw.get("title") or "",
        "description": raw.get("problem") or "",
        "customer_company": ci.get("customerName"),
    }
    detail = {
        "customer_contact": ci.get("linkman"),
        "customer_mobile": ci.get("mobile") or raw.get("feedbackPhone"),
        "customer_email": ci.get("email") or raw.get("feedbackEmail"),
        "customer_tel": ci.get("phone") or raw.get("feedbackTel"),
        "customer_no": ci.get("customerNumber"),
        "product_name_raw": prod.get("name"),
        "module_raw": mod.get("name"),
        "raw_json": raw,
    }
    org = {
        "source": Source.KSM.value,
        "org_bill_id": source_id,
        "org_bill_no": raw.get("billNumber"),
        "org_title": raw.get("title"),
        "org_content": raw.get("problem"),
        "org_status": str(raw.get("status")) if raw.get("status") is not None else None,
        "org_urgency": str(raw.get("urgency")) if raw.get("urgency") is not None else None,
        "org_create_time": _parse_dt(raw.get("createDateTime")),
        "org_update_time": _parse_dt(raw.get("updateDateTime")),
        "org_customer_name": ci.get("customerName"),
        "org_linkman": ci.get("linkman"),
        "org_mobile": ci.get("mobile"),
        "org_email": ci.get("email"),
        "org_product_name": prod.get("name"),
        "org_module_name": mod.get("name"),
        "org_assign_user": assign.get("realname"),
        "ksm_feedback_type": str(raw.get("feedbackType")) if raw.get("feedbackType") is not None else None,
        "ksm_product_id": prod.get("id"),
        "ksm_module_id": mod.get("id"),
        "ksm_version_id": ver.get("id"),
        "ksm_node_id": node.get("id"),
        "ksm_node_name": node.get("name"),
        "ksm_customer_no": ci.get("customerNumber"),
        "ksm_service_level": ci.get("serviceLevel"),
        "ksm_sponsor": sponsor.get("realname"),
        "ksm_main_product": ver.get("mainproductname"),
        "ksm_handle_steps": raw.get("handleSteps"),
        "ksm_evaluate_info": raw.get("evaluateInfo"),
    }
    return NormalizedTicket(source=Source.KSM.value, source_id=source_id, has_attachment=bool(atts),
                            attachment_urls=atts, info=info, detail=detail, org=org)
