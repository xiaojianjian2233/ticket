"""智能助手路由：对话(NL2SQL统计) + 提单。三级均可只读统计；PII 按角色脱敏。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.modules.assistant import service

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class ChatIn(BaseModel):
    nl_query: str
    session_id: Optional[str] = ""


@router.post("/chat")
async def chat(body: ChatIn, user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    data = await service.nl2sql_query(session, nl=body.nl_query, role=user.get("role", "visitor"),
                                      user_uid=str(user.get("sub")), session_id=body.session_id or "")
    await session.commit()
    return success(data)


class SubmitIn(BaseModel):
    title: str
    description: str


@router.post("/submit")
async def submit(body: SubmitIn, user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    data = await service.submit_ticket(session, title=body.title, description=body.description,
                                       submitter_uid=str(user.get("sub")))
    await session.commit()
    return success(data)
