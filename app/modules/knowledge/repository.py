"""知识库仓储：t_faq 检索候选 + 收录写入 + 审核状态。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import FAQ_NO_PREFIX
from app.common.enums import ReviewStatus
from app.modules.knowledge.models import Faq, FaqReview

_BEIJING_OFFSET = 8 * 3600


async def next_faq_no(session: AsyncSession) -> str:
    from sqlalchemy import text
    seq = (await session.execute(text("SELECT nextval('seq_faq_no')"))).scalar_one()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{FAQ_NO_PREFIX}{today}{int(seq):06d}"


async def retrieve_candidates(session: AsyncSession, product_tag: str) -> list[dict]:
    """检索候选：同产品线、排除 rejected、有 embedding。返回 [{id, content, embedding}]。"""
    rows = (await session.execute(
        select(Faq).where(
            Faq.product_tag == product_tag,
            Faq.review_status != ReviewStatus.REJECTED.value,
            Faq.embedding.is_not(None),
            Faq.is_deleted.is_(False),
        )
    )).scalars()
    return [{"id": r.id, "content": r.content, "embedding": r.embedding} for r in rows]


async def dedup_candidates(session: AsyncSession, product_tag: str) -> list[dict]:
    """收录前去重候选（同产品线全部，含 pending/approved）。"""
    rows = (await session.execute(
        select(Faq).where(
            Faq.product_tag == product_tag,
            Faq.review_status != ReviewStatus.REJECTED.value,
            Faq.embedding.is_not(None),
            Faq.is_deleted.is_(False),
        )
    )).scalars()
    return [{"id": r.id, "content": r.content, "embedding": r.embedding} for r in rows]


async def create_faq(session: AsyncSession, *, title: str, content: str, product_tag: str,
                     source_ticket_id: int, embedding: Optional[list]) -> Faq:
    faq = Faq(faq_no=await next_faq_no(session), title=title[:64], content=content[:512],
              product_tag=product_tag, source_ticket_id=source_ticket_id, embedding=embedding,
              review_status=ReviewStatus.PENDING_REVIEW.value, created_by="pipeline")
    session.add(faq)
    await session.flush()
    return faq


async def hit_inc(session: AsyncSession, faq_id: int) -> None:
    faq = await session.get(Faq, faq_id)
    if faq:
        faq.hit_count += 1
        await session.flush()


async def set_review(session: AsyncSession, faq_id: int, *, result: str, reason: str,
                     dims: Optional[dict] = None, reject_dims: str = "") -> None:
    faq = await session.get(Faq, faq_id)
    if faq:
        faq.review_status = result
        faq.review_reason = reason
        faq.reviewed_at = datetime.now(timezone.utc)
    dims = dims or {}
    session.add(FaqReview(faq_id=faq_id, result=result,
                          dim_sensitive=dims.get("sensitive"), dim_factual=dims.get("factual"),
                          dim_internal=dims.get("internal"), dim_quality=dims.get("quality"),
                          reject_dims=reject_dims, reason=reason, created_by="pipeline"))
    await session.flush()
