"""流水线上下文：贯穿一次 run_pipeline 的 trace_id / 工单态。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RunContext:
    """一次流水线执行的上下文（harness 写 t_skill_log 时带入）。"""

    trace_id: str
    ticket_id: Optional[int] = None
    hub_id: Optional[int] = None
    source: Optional[str] = None       # ksm/zhichi/assistant
    is_returned: bool = False          # 退回单：末端强制转人工
