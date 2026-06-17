"""知识库路由：FAQ 列表/详情/检索/浏览/审核列表/审核/编辑/删除。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ReviewStatus
from app.core.response import page, success
from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.modules.knowledge import service

router = APIRouter(prefix="/api/v1/faq", tags=["faq"])


@router.get("")
async def list_faq(product_tag: Optional[str] = None, review_status: Optional[str] = None, keyword: Optional[str] = None,
                   page_no: int = 1, page_size: int = 20, _: dict = Depends(get_current_user),
                   session: AsyncSession = Depends(get_db)):
    items, total = await service.list_faq(session, product_tag=product_tag, review_status=review_status,
                                          keyword=keyword, page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


@router.get("/browse")
async def browse(product_tag: Optional[str] = None, page_no: int = 1, page_size: int = 20,
                 _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    items, total = await service.list_faq(session, product_tag=product_tag,
                                          review_status=ReviewStatus.APPROVED.value, page=page_no, page_size=page_size)
    return success(page(items, total, page_no, page_size))


class SearchIn(BaseModel):
    query: str
    product_tag: Optional[str] = None


@router.post("/search")
async def search(body: SearchIn, _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return success({"items": await service.search(session, query=body.query, product_tag=body.product_tag)})


@router.get("/review-list")
async def review_list(page_no: int = 1, page_size: int = 50, _: dict = Depends(require_role("handler")),
                      session: AsyncSession = Depends(get_db)):
    rej, _t1 = await service.list_faq(session, review_status=ReviewStatus.REJECTED.value, page=1, page_size=page_size)
    pend, _t2 = await service.list_faq(session, review_status=ReviewStatus.PENDING_REVIEW.value, page=page_no, page_size=page_size)
    return success({"items": rej + pend})


@router.get("/{faq_id}")
async def get_faq(faq_id: int, _: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return success(await service.get_faq(session, faq_id))


class ReviewIn(BaseModel):
    result: str
    reason: Optional[str] = ""


@router.post("/{faq_id}/review")
async def review(faq_id: int, body: ReviewIn, _: dict = Depends(require_role("handler")),
                 session: AsyncSession = Depends(get_db)):
    await service.review(session, faq_id, result=body.result, reason=body.reason or "")
    await session.commit()
    return success({"ok": True})


class EditIn(BaseModel):
    title: str
    content: str
    product_tag: str


@router.put("/{faq_id}")
async def edit(faq_id: int, body: EditIn, _: dict = Depends(require_role("admin")),
               session: AsyncSession = Depends(get_db)):
    await service.edit_faq(session, faq_id, title=body.title, content=body.content, product_tag=body.product_tag)
    await session.commit()
    return success({"ok": True})


@router.delete("/{faq_id}")
async def delete(faq_id: int, _: dict = Depends(require_role("admin")), session: AsyncSession = Depends(get_db)):
    await service.delete_faq(session, faq_id)
    await session.commit()
    return success({"ok": True})
