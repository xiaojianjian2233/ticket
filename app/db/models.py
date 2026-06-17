"""模型聚合入口：import 此模块即把全部 ORM 注册到 Base.metadata。

用途：Alembic env.py 的 target_metadata、`Base.metadata.create_all`、跨模块单点导入。
新增模型时在此追加一行 import。
"""
from __future__ import annotations

from app.db.base import Base  # noqa: F401  re-export
from app.db.queue import TaskQueue  # noqa: F401
from app.integrations.models import IntegrationLog  # noqa: F401
from app.modules.ai.models import SkillLog  # noqa: F401
from app.modules.assistant.models import AssistantLog  # noqa: F401
from app.modules.dispatch.models import (  # noqa: F401
    DispatchAssignee,
    DispatchConfig,
    DispatchLog,
)
from app.modules.feishu.models import User  # noqa: F401
from app.modules.knowledge.models import Faq, FaqReview  # noqa: F401
from app.modules.skill.models import (  # noqa: F401
    OperationLog,
    SkillMd,
    SkillMdHistory,
)
from app.modules.sla.models import Holiday, SlaLog  # noqa: F401
from app.modules.storage.models import Attachment  # noqa: F401
from app.modules.ticket.models import (  # noqa: F401
    ModuleOwner,
    TicketDetail,
    TicketHub,
    TicketInfo,
    TicketMerge,
    TicketOrg,
    TicketTag,
)

__all__ = [
    "Base",
    "TaskQueue",
    "IntegrationLog",
    "SkillLog",
    "AssistantLog",
    "DispatchAssignee",
    "DispatchConfig",
    "DispatchLog",
    "User",
    "Faq",
    "FaqReview",
    "OperationLog",
    "SkillMd",
    "SkillMdHistory",
    "Holiday",
    "SlaLog",
    "Attachment",
    "ModuleOwner",
    "TicketDetail",
    "TicketHub",
    "TicketInfo",
    "TicketMerge",
    "TicketOrg",
    "TicketTag",
]
