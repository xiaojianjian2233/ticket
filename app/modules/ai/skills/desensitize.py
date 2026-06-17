"""脱敏（业务规则 FQ-02 两类）：调 agent 前 / 答客户前 / 收录 FAQ 前。

① 完全替换类：公司名/联系人(已知实体名)、单号、邮箱、座机、税号、外部订单号/合同号/authCode、凭证(按字段名)。
② 部分保留打码类：手机号(前3后4)、身份证(前6后4)。
脱敏放在 humanize 之后、writeback 之前（防破坏占位符）。
"""
from __future__ import annotations

import re
from typing import Iterable

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")          # 手机 → 138****5678
_IDCARD = re.compile(r"(?<!\d)(\d{6})\d{4,8}([0-9Xx]{4})(?!\d)")     # 身份证 → 前6后4
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_TEL = re.compile(r"(?<!\d)(0\d{2,3}-?\d{7,8})(?!\d)")
_TAXNO = re.compile(r"(?<![0-9A-Z])([0-9A-Z]{15,20})(?![0-9A-Z])")
_TICKETNO = re.compile(r"(?<![A-Za-z0-9])(?:FPY|HUB|DUP|FAQ|ZC|R)-?\d{6,}(?!\d)", re.I)  # 中文前缀也能匹配
_AUTHCODE = re.compile(r"\b[A-Z0-9]{8,}\b")                          # 授权码/订单号(粗粒度, 放最后)

# 凭证类字段名（结构化数据按 key 抹值）
_SECRET_KEYS = {"clientsecret", "entrykey", "appsecret", "privatekey", "password", "token", "secret", "app_key", "apikey"}


def _mask_phone(m: re.Match) -> str:
    return f"{m.group(1)}****{m.group(2)}"


def _mask_idcard(m: re.Match) -> str:
    return f"{m.group(1)}****{m.group(2)}"


def desensitize_text(text: str, *, names: Iterable[str] = ()) -> str:
    """脱敏自由文本。names=已知公司名/联系人，整体替换为占位符。"""
    if not text:
        return text or ""
    out = text
    for nm in sorted([n for n in names if n], key=len, reverse=True):
        out = out.replace(nm, "[已脱敏]")
    # 顺序关键：先移除带前缀/分隔的具体实体(单号/邮箱/座机)，再处理纯数字串(手机/身份证/税号)，
    # 避免身份证/税号正则误吞单号等的数字。
    out = _TICKETNO.sub("[单号]", out)
    out = _EMAIL.sub("[邮箱]", out)
    out = _TEL.sub("[电话]", out)
    out = _PHONE.sub(_mask_phone, out)
    out = _IDCARD.sub(_mask_idcard, out)         # 身份证(前6后4)先于税号(避免18位被税号整体抹)
    out = _TAXNO.sub("[税号]", out)
    return out


def scrub_dict(data: dict) -> dict:
    """结构化数据：凭证类字段名抹值。"""
    result = {}
    for k, v in data.items():
        if isinstance(k, str) and k.lower().replace("_", "") in _SECRET_KEYS:
            result[k] = "[已脱敏]"
        elif isinstance(v, dict):
            result[k] = scrub_dict(v)
        else:
            result[k] = v
    return result
