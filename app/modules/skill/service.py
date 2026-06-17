"""Skill 管理：列表/取/编辑(bump version+history+审计+清缓存热生效)/回滚/试跑预览。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.modules.ai.skill_runner import clear_cache, run_skill
from app.modules.skill import repository as repo
from app.modules.skill.models import OperationLog, SkillMd, SkillMdHistory


async def list_skills(session: AsyncSession) -> list[dict]:
    rows = await repo.list_all(session)
    return [{"name": s.skill_name, "type": s.skill_type, "editable": s.editable, "version": s.version,
             "updatedBy": s.updated_by, "updatedAt": s.updated_at} for s in rows]


async def get_skill(session: AsyncSession, name: str) -> dict:
    s = await repo.get_by_name(session, name)
    if s is None:
        raise BizException("SKILL 不存在", code=404)
    return {"name": s.skill_name, "type": s.skill_type, "editable": s.editable, "version": s.version,
            "frontmatter": s.frontmatter, "contentMd": s.content_md}


async def edit_skill(session: AsyncSession, name: str, content_md: str, operator: str) -> dict:
    s = await repo.get_by_name(session, name)
    if s is None:
        raise BizException("SKILL 不存在", code=404)
    if not s.editable:
        raise BizException("该 SKILL 为代码逻辑，不可页面编辑", code=403)
    if not content_md.strip():
        raise BizException("正文不能为空", code=422)
    before = s.content_md
    s.version += 1
    s.content_md = content_md
    s.updated_by = operator
    session.add(SkillMdHistory(skill_name=name, version=s.version, frontmatter=s.frontmatter,
                               content_md=content_md, change_note="page-edit", created_by=operator))
    session.add(OperationLog(operator_uid=operator, target_type="skill_md", target_id=name, action="update",
                             before_value={"content_md": before[:2000]}, after_value={"content_md": content_md[:2000]},
                             created_by=operator))
    await session.flush()
    clear_cache(name)  # 热生效
    return {"name": name, "version": s.version}


async def rollback(session: AsyncSession, name: str, version: int, operator: str) -> dict:
    hist = (await session.execute(select(SkillMdHistory).where(
        SkillMdHistory.skill_name == name, SkillMdHistory.version == version))).scalar_one_or_none()
    if hist is None:
        raise BizException("目标版本不存在", code=404)
    s = await repo.get_by_name(session, name)
    s.version += 1
    s.content_md = hist.content_md
    s.frontmatter = hist.frontmatter
    s.updated_by = operator
    session.add(SkillMdHistory(skill_name=name, version=s.version, frontmatter=hist.frontmatter,
                               content_md=hist.content_md, change_note=f"rollback->v{version}", created_by=operator))
    session.add(OperationLog(operator_uid=operator, target_type="skill_md", target_id=name, action="rollback",
                             after_value={"to_version": version}, created_by=operator))
    await session.flush()
    clear_cache(name)
    return {"name": name, "version": s.version}


async def preview(name: str, sample: dict) -> dict:
    """样例试跑（用当前已保存内容，不落库）。"""
    return await run_skill(name, sample)
