"""Skill 管理仓储：t_skill_md / t_skill_md_history 读写（含种子 upsert + 版本历史）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.skill.models import SkillMd, SkillMdHistory


async def get_by_name(session: AsyncSession, name: str) -> Optional[SkillMd]:
    return (
        await session.execute(
            select(SkillMd).where(SkillMd.skill_name == name, SkillMd.is_deleted.is_(False))
        )
    ).scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[SkillMd]:
    return list((await session.execute(select(SkillMd).where(SkillMd.is_deleted.is_(False)).order_by(SkillMd.skill_name))).scalars())


async def upsert(
    session: AsyncSession,
    *,
    name: str,
    skill_type: str,
    editable: bool,
    frontmatter: dict,
    content_md: str,
    updated_by: str = "seed",
) -> SkillMd:
    """存在则更新内容并 bump version（旧版入 history）；不存在则新建。"""
    skill = await get_by_name(session, name)
    if skill is None:
        skill = SkillMd(skill_name=name, skill_type=skill_type, editable=editable,
                        frontmatter=frontmatter, content_md=content_md, version=1, updated_by=updated_by)
        session.add(skill)
        await session.flush()
        session.add(SkillMdHistory(skill_name=name, version=1, frontmatter=frontmatter,
                                   content_md=content_md, change_note="seed", created_by=updated_by))
    elif skill.content_md != content_md or (skill.frontmatter or {}) != frontmatter:
        skill.version += 1
        skill.content_md = content_md
        skill.frontmatter = frontmatter
        skill.skill_type = skill_type
        skill.editable = editable
        skill.updated_by = updated_by
        session.add(SkillMdHistory(skill_name=name, version=skill.version, frontmatter=frontmatter,
                                   content_md=content_md, change_note="seed-update", created_by=updated_by))
    await session.flush()
    return skill
