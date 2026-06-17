"""NL2SQL 安全护栏（★py 不可热改）：强制 SELECT-only + LIMIT 封顶 + PII 按角色脱敏。

护栏在代码层，页面改不到（与可热改的 assistant-nl2sql 提示词分离）。
"""
from __future__ import annotations

import re
from typing import Any

from app.core.exceptions import BizException

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|call|copy|do|comment|vacuum|"
    r"reindex|cluster|lock|set|begin|commit|rollback|savepoint)\b", re.I)
_LIMIT_RE = re.compile(r"\blimit\s+\d+", re.I)
_PII_COLS = {"customer_mobile", "customer_email", "customer_tax_no", "customer_tel", "customer_contact",
             "mobile", "email", "feishu_uid", "org_mobile", "org_email", "org_linkman"}
LIMIT_CAP = 500


def guard_sql(sql: str, *, limit_cap: int = LIMIT_CAP) -> str:
    """校验并加固 SQL：单条 SELECT、无写操作、强制 LIMIT。违规抛 BizException。"""
    if not sql or not sql.strip():
        raise BizException("未生成可执行 SQL", code=400)
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise BizException("仅支持单条查询语句", code=400)
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise BizException("仅支持数据查询，不支持修改操作", code=400)
    if _FORBIDDEN.search(s):
        raise BizException("仅支持数据查询，不支持修改操作", code=400)
    if not _LIMIT_RE.search(low):
        s = f"{s} LIMIT {limit_cap}"
    return s


def _mask(col: str, val: Any) -> Any:
    if val is None or not isinstance(val, str):
        return val
    if "mobile" in col and len(val) >= 7:
        return val[:3] + "****" + val[-4:]
    if "email" in col and "@" in val:
        u, _, dom = val.partition("@")
        return (u[:2] + "***@" + dom)
    return "[已脱敏]"


def mask_rows(rows: list[dict], role: str) -> list[dict]:
    """visitor 脱敏 PII 列；handler/admin 明文。"""
    if role in ("admin", "handler"):
        return rows
    out = []
    for r in rows:
        out.append({k: (_mask(k, v) if k.lower() in _PII_COLS else v) for k, v in r.items()})
    return out
