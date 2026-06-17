"""工单域 ORM 模型：t_ticket_info / detail / tag / merge / hub / org + t_module_owner。

字段严格对照 docs/ddl.sql；枚举列存 varchar，取值见 app/common/enums。
跨表关联用应用层维护（DDL 默认不建外键），故此处不声明 relationship。
"""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, IdMixin


class TicketInfo(IdMixin, AuditMixin, Base):
    """工单主表 = 处理单元（前端只展示本表归一字段）。"""

    __tablename__ = "t_ticket_info"

    ticket_no: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)           # ksm/zhichi/assistant
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)        # 幂等/退回键
    source_bill_no: Mapped[Optional[str]] = mapped_column(String(64))
    assistant_submitter_uid: Mapped[Optional[str]] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    customer_company: Mapped[Optional[str]] = mapped_column(String(255))
    has_attachment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 流转
    routable: Mapped[Optional[bool]] = mapped_column(Boolean)
    route_action: Mapped[Optional[str]] = mapped_column(String(32))
    route_reason: Mapped[Optional[str]] = mapped_column(String(512))
    is_returned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    return_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 打标（冗余高频）
    ai_product_tag: Mapped[Optional[str]] = mapped_column(String(64))
    ai_func_module: Mapped[Optional[str]] = mapped_column(String(128))
    ai_dev_owner: Mapped[Optional[str]] = mapped_column(String(64))
    dev_owner_missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ticket_type: Mapped[Optional[str]] = mapped_column(String(16))                # 工单类型(人工选)：需求/bug/应用技术类/其他
    # 去重
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reused_from_ticket_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    # 答复
    answer_branch: Mapped[Optional[str]] = mapped_column(String(4))              # A/B/C/D
    transfer_result: Mapped[Optional[str]] = mapped_column(String(16))           # NO_ACTION/TRANSFER
    final_reply: Mapped[Optional[str]] = mapped_column(Text)
    rd_hub_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    rd_status: Mapped[Optional[str]] = mapped_column(String(20))                 # 研发状态镜像
    rd_handler: Mapped[Optional[str]] = mapped_column(String(64))
    rd_status_note: Mapped[Optional[str]] = mapped_column(Text)
    # 派单
    dispatch_assignee: Mapped[Optional[str]] = mapped_column(String(64))
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # 回写
    writeback_status: Mapped[Optional[str]] = mapped_column(String(16))         # pending/success/failed
    writeback_retry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # SLA-1 人工 + 关闭生命周期
    sla_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sla_state: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    sla_notified_marks: Mapped[Optional[dict]] = mapped_column(JSONB)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 观察期起点
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class TicketDetail(IdMixin, AuditMixin, Base):
    """工单详情 1:1（含 PII / 原始报文，不上前端）。"""

    __tablename__ = "t_ticket_detail"

    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_contact: Mapped[Optional[str]] = mapped_column(String(64))
    customer_mobile: Mapped[Optional[str]] = mapped_column(String(32))
    customer_email: Mapped[Optional[str]] = mapped_column(String(128))
    customer_tel: Mapped[Optional[str]] = mapped_column(String(32))
    customer_tax_no: Mapped[Optional[str]] = mapped_column(String(64))
    customer_no: Mapped[Optional[str]] = mapped_column(String(64))
    product_name_raw: Mapped[Optional[str]] = mapped_column(String(128))
    module_raw: Mapped[Optional[str]] = mapped_column(String(128))
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB)                       # 全量报文留底
    ai_reply: Mapped[Optional[str]] = mapped_column(Text)                         # agent 原文
    full_reply: Mapped[Optional[str]] = mapped_column(Text)
    humanized_reply: Mapped[Optional[str]] = mapped_column(Text)                  # 去AI化后
    supply_note: Mapped[Optional[str]] = mapped_column(Text)                      # C 分支需补信息
    writeback_error: Mapped[Optional[str]] = mapped_column(Text)


class TicketTag(IdMixin, AuditMixin, Base):
    """打标历史 1:N（重打标旧行 is_current=false）。"""

    __tablename__ = "t_ticket_tag"

    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_tag: Mapped[Optional[str]] = mapped_column(String(64))
    func_module: Mapped[Optional[str]] = mapped_column(String(128))
    dev_owner: Mapped[Optional[str]] = mapped_column(String(64))
    dev_owner_missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    tag_source: Mapped[str] = mapped_column(String(16), nullable=False, default="llm")  # llm/manual/fallback
    model_used: Mapped[Optional[str]] = mapped_column(String(32))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revised_by: Mapped[Optional[str]] = mapped_column(String(64))
    evidence: Mapped[Optional[str]] = mapped_column(Text)


class TicketMerge(IdMixin, AuditMixin, Base):
    """合并/去重记录 1:N。"""

    __tablename__ = "t_ticket_merge"

    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    merge_type: Mapped[str] = mapped_column(String(16), nullable=False)       # dedup_reuse/dedup_marked/hub_merge
    target_ticket_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    target_hub_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    similarity: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    threshold: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    llm_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    evidence: Mapped[Optional[str]] = mapped_column(Text)


class TicketHub(IdMixin, AuditMixin, Base):
    """研发单（N info : 1 hub）。"""

    __tablename__ = "t_ticket_hub"

    hub_no: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    problem_summary: Mapped[Optional[str]] = mapped_column(Text)
    full_reply: Mapped[Optional[str]] = mapped_column(Text)
    product_tag: Mapped[Optional[str]] = mapped_column(String(64))
    func_module: Mapped[Optional[str]] = mapped_column(String(128))
    dev_owner: Mapped[Optional[str]] = mapped_column(String(64))
    embedding: Mapped[Optional[list]] = mapped_column(JSONB)  # float数组(应用层算余弦)
    linear_issue_id: Mapped[Optional[str]] = mapped_column(String(64))
    linear_url: Mapped[Optional[str]] = mapped_column(String(512))
    linear_sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    linear_sync_retry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rd_handler: Mapped[Optional[str]] = mapped_column(String(64))                # Linear 回调:处理人
    rd_status_note: Mapped[Optional[str]] = mapped_column(Text)
    rd_callback_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rd_sla_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # =hub.created_at
    rd_sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rd_sla_state: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    rd_resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))   # SLA-2 停表
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="待处理")  # 建单初始值


class TicketOrg(IdMixin, AuditMixin, Base):
    """来源原始工单字段 1:1 宽表（只存库不上前端，供回写/排障）。"""

    __tablename__ = "t_ticket_org"

    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)           # ksm/zhichi
    org_bill_id: Mapped[Optional[str]] = mapped_column(String(64))               # KSM billId / 智齿 ticketid
    org_bill_no: Mapped[Optional[str]] = mapped_column(String(64))
    org_title: Mapped[Optional[str]] = mapped_column(String(512))
    org_content: Mapped[Optional[str]] = mapped_column(Text)
    org_status: Mapped[Optional[str]] = mapped_column(String(32))
    org_urgency: Mapped[Optional[str]] = mapped_column(String(16))
    org_create_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    org_update_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    org_customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    org_linkman: Mapped[Optional[str]] = mapped_column(String(64))
    org_mobile: Mapped[Optional[str]] = mapped_column(String(32))
    org_email: Mapped[Optional[str]] = mapped_column(String(128))
    org_product_name: Mapped[Optional[str]] = mapped_column(String(128))
    org_module_name: Mapped[Optional[str]] = mapped_column(String(128))
    org_assign_user: Mapped[Optional[str]] = mapped_column(String(64))
    # KSM 特有
    ksm_feedback_type: Mapped[Optional[str]] = mapped_column(String(16))
    ksm_product_id: Mapped[Optional[str]] = mapped_column(String(64))            # 回写用
    ksm_module_id: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_version_id: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_node_id: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_node_name: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_notice_num: Mapped[Optional[str]] = mapped_column(String(64))             # 推送通知编号(接管后重拉详情用)
    ksm_customer_no: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_service_level: Mapped[Optional[str]] = mapped_column(String(32))
    ksm_sponsor: Mapped[Optional[str]] = mapped_column(String(64))
    ksm_main_product: Mapped[Optional[str]] = mapped_column(String(128))
    # 智齿 特有
    zhichi_deal_agent: Mapped[Optional[str]] = mapped_column(String(64))
    zhichi_erp: Mapped[Optional[str]] = mapped_column(String(64))
    zhichi_project_name: Mapped[Optional[str]] = mapped_column(String(255))
    # 嵌套 jsonb
    ksm_handle_steps: Mapped[Optional[list]] = mapped_column(JSONB)
    ksm_evaluate_info: Mapped[Optional[dict]] = mapped_column(JSONB)
    zhichi_extend_fields: Mapped[Optional[list]] = mapped_column(JSONB)


class ModuleOwner(IdMixin, AuditMixin, Base):
    """产品线/功能模块/研发责任人映射（打标权威源，页面 CRUD）。"""

    __tablename__ = "t_module_owner"

    product_tag: Mapped[str] = mapped_column(String(64), nullable=False)      # 13 权威产品线之一
    func_module: Mapped[str] = mapped_column(String(128), nullable=False)     # 157 模块 / 业务域兜底行
    row_type: Mapped[str] = mapped_column(String(16), nullable=False, default="module")  # module/domain_fallback
    trigger_words: Mapped[Optional[str]] = mapped_column(Text)                   # '|' 分隔
    dev_owner: Mapped[Optional[str]] = mapped_column(String(64))
    dev_owner_uid: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ServiceLevel(IdMixin, AuditMixin, Base):
    """KSM 服务等级基础数据：编码 → 名称映射（来源工单传编码，列表展示名称）。"""

    __tablename__ = "t_service_level"

    code: Mapped[str] = mapped_column(String(16), nullable=False)             # KSM 服务等级编码，如 '22'
    name: Mapped[str] = mapped_column(String(64), nullable=False)             # 名称，如 '标准成功服务（2023版）'
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
