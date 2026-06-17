"""种子导入：9 个 SKILL.md → t_skill_md；模块责任人映射 + 派单兜底（占位，L10 真值联调补）。

运行：python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.modules.skill import repository as skill_repo  # noqa: E402
from app.modules.dispatch.models import DispatchAssignee, DispatchConfig  # noqa: E402
from app.modules.ticket.models import ModuleOwner  # noqa: E402
from sqlalchemy import select  # noqa: E402

SKILLS_DIR = ROOT / "skills_md"
LLM_SKILLS = [
    "ticket-routable", "ticket-tagging", "info-dedup", "hub-dedup", "answer-router",
    "reply-humanize", "faq-record", "faq-review", "assistant-nl2sql",
]


def parse_frontmatter(md: str) -> tuple[dict, str]:
    """解析 --- frontmatter --- + 正文。返回 (frontmatter_dict, body)。"""
    fm: dict = {}
    body = md
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end > 0:
            for line in md[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = md[end + 4 :].lstrip("\n")
    return fm, body


async def seed_skills(session) -> int:
    n = 0
    for name in LLM_SKILLS:
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.exists():
            print(f"  ⚠️ 缺失 {path}")
            continue
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        await skill_repo.upsert(session, name=name, skill_type="llm", editable=True, frontmatter=fm, content_md=body)
        n += 1
    return n


# 占位模块责任人（真值见 L10 xlsx；先让打标/查表链路可跑）
_MODULE_SEED = [
    ("星瀚-开票", "开票申请", "开票|发票申请|蓝字发票", "李志坚"),
    ("星瀚-收票", "收票管理", "收票|认证|抵扣|勾选", "李志坚"),
    ("标准版-开票", "开票", "开票|开具|红冲", "李志坚"),
    ("基础研发", "全电发票", "全电|数电|电子发票", "李志坚"),
]


async def seed_module_owner(session) -> int:
    n = 0
    for product, module, words, owner in _MODULE_SEED:
        exists = (await session.execute(
            select(ModuleOwner).where(ModuleOwner.product_tag == product, ModuleOwner.func_module == module, ModuleOwner.row_type == "module")
        )).scalar_one_or_none()
        if exists:
            continue
        session.add(ModuleOwner(product_tag=product, func_module=module, row_type="module",
                                trigger_words=words, dev_owner=owner, is_active=True, created_by="seed"))
        n += 1
    return n


async def seed_dispatch(session) -> None:
    if not (await session.execute(select(DispatchConfig).where(DispatchConfig.config_key == "default_assignee"))).scalar_one_or_none():
        session.add(DispatchConfig(config_key="default_assignee", config_value="李志坚", remark="兜底处理人(占位)", created_by="seed"))
    if not (await session.execute(select(DispatchAssignee).where(DispatchAssignee.tier == "main"))).scalars().first():
        session.add(DispatchAssignee(assignee_name="李志坚", alloc_value=1, tier="main", is_active=True, created_by="seed"))


async def main() -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        ns = await seed_skills(session)
        nm = await seed_module_owner(session)
        await seed_dispatch(session)
        await session.commit()
    print(f"✅ 种子完成: SKILL={ns}, module_owner+{nm}, dispatch 兜底已置")


if __name__ == "__main__":
    asyncio.run(main())
