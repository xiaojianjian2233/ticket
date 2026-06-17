"""知识库业务：FAQ 列表/详情/语义检索/人工审核/编辑/删除。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import FAQ_CONTENT_MAX, FAQ_TITLE_MAX
from app.common.enums import ReviewStatus
from app.common.utils.vector import cosine
from app.core.exceptions import BizException
from app.integrations.siliconflow_client import get_siliconflow
from app.modules.knowledge import repository as repo
from app.modules.knowledge.models import Faq, FaqReview


def _view(f: Faq) -> dict:
    return {"id": f.id, "faqNo": f.faq_no, "title": f.title, "content": f.content, "productTag": f.product_tag,
            "reviewStatus": f.review_status, "hitCount": f.hit_count, "sourceTicketId": f.source_ticket_id,
            "createdAt": f.created_at}


async def list_faq(session, *, product_tag=None, review_status=None, keyword=None, page=1, page_size=20):
    stmt = select(Faq).where(Faq.is_deleted.is_(False))
    if product_tag:
        stmt = stmt.where(Faq.product_tag == product_tag)
    if review_status:
        stmt = stmt.where(Faq.review_status == review_status)
    if keyword:
        stmt = stmt.where(Faq.title.ilike(f"%{keyword}%") | Faq.content.ilike(f"%{keyword}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Faq.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars()
    return [_view(f) for f in rows], total


async def get_faq(session, faq_id: int) -> dict:
    f = await session.get(Faq, faq_id)
    if f is None or f.is_deleted:
        raise BizException("FAQ 不存在", code=404)
    reviews = (await session.execute(select(FaqReview).where(FaqReview.faq_id == faq_id).order_by(FaqReview.id.desc()))).scalars()
    v = _view(f)
    v["reviews"] = [{"result": r.result, "reason": r.reason, "rejectDims": r.reject_dims,
                     "modelUsed": r.model_used, "createdAt": r.created_at} for r in reviews]
    return v


async def search(session, *, query: str, product_tag: Optional[str] = None, top_n: int = 10) -> list[dict]:
    stmt = select(Faq).where(Faq.review_status != ReviewStatus.REJECTED.value, Faq.embedding.is_not(None),
                             Faq.is_deleted.is_(False))
    if product_tag:
        stmt = stmt.where(Faq.product_tag == product_tag)
    cands = list((await session.execute(stmt)).scalars())
    if not cands:
        return []
    try:
        q_emb = await get_siliconflow().embed_one(query)
    except Exception:  # noqa: BLE001 降级关键词 like
        kw = [c for c in cands if query in c.title or query in c.content][:top_n]
        return [{**_view(c), "similarity": None} for c in kw]
    scored = sorted(((cosine(q_emb, c.embedding), c) for c in cands), key=lambda t: t[0], reverse=True)
    return [{**_view(c), "similarity": round(s, 4)} for s, c in scored[:top_n]]


async def review(session, faq_id: int, *, result: str, reason: str = "") -> None:
    if result not in (ReviewStatus.APPROVED.value, ReviewStatus.REJECTED.value):
        raise BizException("审核结果非法", code=422)
    f = await session.get(Faq, faq_id)
    if f is None:
        raise BizException("FAQ 不存在", code=404)
    await repo.set_review(session, faq_id, result=result, reason=reason)


async def edit_faq(session, faq_id: int, *, title: str, content: str, product_tag: str) -> None:
    if len(title) > FAQ_TITLE_MAX:
        raise BizException(f"标题不超过 {FAQ_TITLE_MAX} 字", code=422)
    if len(content) > FAQ_CONTENT_MAX:
        raise BizException(f"正文不超过 {FAQ_CONTENT_MAX} 字", code=422)
    f = await session.get(Faq, faq_id)
    if f is None:
        raise BizException("FAQ 不存在", code=404)
    f.title, f.content, f.product_tag = title, content, product_tag
    f.review_status = ReviewStatus.APPROVED.value  # 人工编辑后直接通过
    f.reviewed_at = datetime.now(timezone.utc)
    try:
        f.embedding = await get_siliconflow().embed_one(content)  # 重算 embedding
    except Exception:  # noqa: BLE001
        pass
    await session.flush()


async def delete_faq(session, faq_id: int) -> None:
    f = await session.get(Faq, faq_id)
    if f is None:
        raise BizException("FAQ 不存在", code=404)
    await session.delete(f)  # FAQ 破例物理删
    await session.execute(FaqReview.__table__.delete().where(FaqReview.faq_id == faq_id))
    await session.flush()
