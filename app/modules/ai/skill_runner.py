"""Skill Runner：从 t_skill_md 热加载 SKILL.md（缓存+version 失效）喂 LLM，返回信封。

Skill 本身不连业务 DB——runner 只读 t_skill_md（提示词源），数据由 harness 以 variables 传入。
输出要求 LLM 返回 JSON，解析为 fields。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.db.session import get_sessionmaker
from app.modules.ai import schema
from app.modules.ai.llm_gateway import chat
from app.modules.skill import repository as skill_repo

logger = logging.getLogger("ticket_hub.skill")

# 去AI化：配置 SKILL_NO_AI 列入的 skill 跳过 LLM，返回以下规则默认值（中性/不阻断流程）。
_NON_AI_FIELDS: dict[str, dict] = {
    "ticket-routable": {"routable": True, "route_action": "可流转", "route_reason": "去AI化:默认接管"},
    "ticket-tagging": {"ai_product_tag": "无法判断", "ai_func_module": ""},
    "answer-router": {"answer_branch": "D", "final_reply": "", "full_reply": "", "supply_note": ""},
    "info-dedup": {"is_duplicate": False, "dup_ticket_ids": []},
    "hub-dedup": {"is_dup": False, "dup_hub_id": None, "score": 0},
    "reply-humanize": {"humanized_reply": ""},      # 空→harness 用原文
    "faq-record": {},                                # 空→harness 跳过收录
    "faq-review": {"approved": None},                # 不自动审，留待人工
}


def _no_ai_skills() -> set:
    return {s.strip() for s in (settings.skill_no_ai or "").split(",") if s.strip()}

# 缓存：name -> (version, content_md, frontmatter)
_cache: dict[str, tuple[int, str, dict]] = {}

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)
_OUTPUT_RULE = (
    "\n\n---\n请严格按上文 SKILL 的「输出 result」规范，**只输出一个可被 json.loads 解析的合法 JSON 对象**，"
    "不要 markdown 代码块、不要额外解释。**字符串值内不要使用英文双引号 \" **（需要引用时用中文引号「」），"
    "确保所有引号正确闭合转义。"
)
_RETRY_NOTE = "\n\n注意：你上次的输出无法被 json.loads 解析。请重新只输出一个合法 JSON，字符串内不要用英文双引号。"


async def _load(name: str) -> tuple[str, dict]:
    """读取 SKILL.md（按 version 缓存失效）。"""
    sm = get_sessionmaker()
    async with sm() as session:
        skill = await skill_repo.get_by_name(session, name)
        if skill is None:
            raise KeyError(f"SKILL 未配置: {name}")
        cached = _cache.get(name)
        if cached is None or cached[0] != skill.version:
            _cache[name] = (skill.version, skill.content_md, skill.frontmatter or {})
        return _cache[name][1], _cache[name][2]


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1)
    else:
        i, j = text.find("{"), text.rfind("}")
        if i >= 0 and j > i:
            text = text[i : j + 1]
    return json.loads(text)


async def run_skill(
    name: str,
    variables: dict[str, Any],
    *,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> dict:
    """运行一个 LLM SKILL。variables=喂给提示词的数据。返回信封 {status,fields,evidence,model_used}。"""
    # 去AI化：配置关闭该 skill 的 AI → 直接返回规则默认，不调 LLM
    if name in _no_ai_skills():
        return schema.ok(_NON_AI_FIELDS.get(name, {}), evidence="去AI化:配置跳过LLM,返回规则默认", model_used="none")
    try:
        content_md, _fm = await _load(name)
    except KeyError as e:
        return schema.failed(str(e))
    user = json.dumps(variables, ensure_ascii=False)
    model = ""
    last_err: Optional[str] = None
    for attempt in range(2):  # 解析失败重试一次（强化指令）
        system = content_md + _OUTPUT_RULE + (_RETRY_NOTE if attempt else "")
        try:
            text, model = await chat(system=system, user=user, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        except Exception as exc:  # noqa: BLE001 — LLM 失败由调用方按 routable挂起/其它failed 处置
            return schema.failed(f"LLM 调用失败: {exc}")
        try:
            data = _parse_json(text)
            fields = data.get("fields", data)
            return schema.ok(fields, evidence=str(data.get("evidence", "")), model_used=model)
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            logger.warning("SKILL %s 输出非 JSON(try%d): %s", name, attempt, (text or "")[:200])
    return schema.failed(f"输出解析失败: {last_err}", model_used=model)


def clear_cache(name: Optional[str] = None) -> None:
    """SKILL.md 编辑保存后清缓存（热生效）。"""
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()
