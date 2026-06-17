"""faq-retrieve（py）：硅基流动 embed(query) + 应用层余弦比对候选 t_faq，>阈值命中。

候选由 harness 查库传入（同产品线、过滤 rejected）。query 须由 harness 预先脱敏。
硅基流动不可用 → 视为未命中（hit=False），由 harness 走 agent。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.common.utils.vector import cosine
from app.core.config import settings
from app.integrations.siliconflow_client import get_siliconflow

logger = logging.getLogger("ticket_hub.faq")


async def faq_retrieve(query: str, candidates: list[dict], *, threshold: Optional[float] = None) -> dict:
    """candidates: [{id, content, embedding(list[float])}]。返回 {hit, faq_hit_id, faq_score, faq_content}。"""
    thr = settings.faq_hit_threshold if threshold is None else threshold
    if not candidates:
        return {"hit": False, "faq_score": 0.0}
    try:
        q_emb = await get_siliconflow().embed_one(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("FAQ 检索 embedding 失败，视为未命中: %s", exc)
        return {"hit": False, "faq_score": 0.0}
    best_id = None
    best_content = None
    best_score = -1.0
    for c in candidates:
        s = cosine(q_emb, c.get("embedding"))
        if s > best_score:
            best_score, best_id, best_content = s, c.get("id"), c.get("content")
    hit = best_score >= thr
    return {"hit": hit, "faq_hit_id": best_id if hit else None,
            "faq_score": round(best_score, 4), "faq_content": best_content if hit else None}
