"""全局枚举 + 来源系统状态映射。

枚举值与 DDL varchar 注释一致；存库用 .value 字符串（线上可加值）。
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """字符串枚举基类（兼容 Py3.9，序列化为 .value）。"""

    def __str__(self) -> str:  # noqa: D401
        return self.value


# ---------------- 工单来源 / 状态 ----------------
class Source(StrEnum):
    KSM = "ksm"
    ZHICHI = "zhichi"
    ASSISTANT = "assistant"


class TicketStatus(StrEnum):
    PENDING = "pending"            # 待处理
    RETURNED = "returned"          # 已退回(不接管)
    PENDING_MANUAL = "pending_manual"  # 待人工
    SUPPLEMENT = "supplement"      # 补充资料(C 退回客户等待补料)
    PENDING_RD = "pending_rd"      # 待研发
    DONE = "done"                  # 已处理
    CLOSED = "closed"              # 已关闭(本地, 观察期满)


class RouteAction(StrEnum):
    ROUTABLE = "可流转"
    NOT_TAKEOVER_MULTI = "不接管-多问题"
    NOT_TAKEOVER_INVALID = "不接管-不可流转"


class AnswerBranch(StrEnum):
    A_BUG = "A"
    B_REQUIREMENT = "B"
    C_SUPPLEMENT = "C"
    D_NORMAL = "D"


class TransferResult(StrEnum):
    NO_ACTION = "NO_ACTION"
    TRANSFER = "TRANSFER"


class WritebackStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class SlaState(StrEnum):
    NORMAL = "normal"
    BREACHED = "breached"


# ---------------- 研发单(hub) / Linear ----------------
class HubStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class LinearSyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


# ---------------- FAQ ----------------
class ReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------- 去重 / 合并 ----------------
class MergeType(StrEnum):
    DEDUP_REUSE = "dedup_reuse"      # info 短路复用
    DEDUP_MARKED = "dedup_marked"    # 仅标记重复来源
    HUB_MERGE = "hub_merge"          # 关联已有 hub


# ---------------- 任务队列 ----------------
class TaskType(StrEnum):
    KSM_INTAKE = "ksm_intake"
    SYNC_TICKET = "sync_ticket"
    RUN_PIPELINE = "run_pipeline"
    WRITEBACK = "writeback"
    SLA_SCAN = "sla_scan"
    OBSERVE_SCAN = "observe_scan"
    QUEUE_MONITOR = "queue_monitor"


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    ABANDONED = "abandoned"      # 重试耗尽 → 自动转人工
    SUSPENDED = "suspended"      # 关键依赖全挂 → 挂起不消费


# ---------------- 权限 / 派单 ----------------
class Role(StrEnum):
    ADMIN = "admin"
    HANDLER = "handler"
    VISITOR = "visitor"


class DispatchTier(StrEnum):
    MAIN = "main"
    OVERFLOW = "overflow"
    DEFAULT = "default"          # 兜底单点(仅 dispatch_log.tier_hit 用)
    BROADCAST = "broadcast"      # 群发(仅 dispatch_log.tier_hit 用)


# ---------------- 附件 / SKILL / 节假日 ----------------
class AttachmentScope(StrEnum):
    TICKET = "ticket"
    FAQ = "faq"
    HUB = "hub"


class DownloadStatus(StrEnum):
    PENDING = "pending"
    STORED = "stored"
    FAILED = "failed"


class SkillType(StrEnum):
    LLM = "llm"      # 可页面热改
    CODE = "code"    # 只读展示


class HolidayDayType(StrEnum):
    HOLIDAY = "holiday"      # 法定休
    WORKDAY = "workday"      # 调休补班(周末上班)


# ---------------- SLA 日志维度 ----------------
class SlaType(StrEnum):
    MANUAL = "manual"
    RD = "rd"


class RefType(StrEnum):
    INFO = "info"
    HUB = "hub"


# ---------------- 通用 Skill 步骤状态 ----------------
class StepStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
