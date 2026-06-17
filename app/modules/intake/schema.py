"""入站 webhook 报文模型。

KSM 仅推送 noticeNum（worker 再 subscribeCallback 拉全量）；
智齿推送完整工单 raw（结构联调补，此处宽松接收并透传）。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class KsmWebhookIn(BaseModel):
    """KSM 工单推送：noticeNum(通知编号) + subscribeNum(订阅编号) + billId(单据ID)。"""

    model_config = ConfigDict(populate_by_name=True)

    notice_num: str = Field(..., alias="noticeNum", description="KSM 通知编号")
    subscribe_num: Optional[str] = Field(None, alias="subscribeNum", description="KSM 订阅编号")
    bill_id: Optional[str] = Field(None, alias="billId", description="KSM 单据ID")


# 智齿 webhook = 完整工单 raw dict（字段联调补），路由层直接以 dict 接收并透传入队。

# 智齿 raw 中可能承载工单编号的候选键（用于入队幂等 dedup_key；命中其一即可）。
ZHICHI_TICKET_ID_KEYS: tuple[str, ...] = ("ticketid", "ticket_id", "ticketId", "ticket_code", "ticketCode")


def extract_zhichi_source_id(raw: dict[str, Any]) -> Optional[str]:
    """尽力从智齿 raw 提取工单编号作为 dedup_key；取不到返回 None（仍可入队）。"""
    for key in ZHICHI_TICKET_ID_KEYS:
        val = raw.get(key)
        if val:
            return str(val)
    return None
