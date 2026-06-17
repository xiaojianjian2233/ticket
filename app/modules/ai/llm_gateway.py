"""LLM 网关：Claude 主 → DeepSeek 降级（业务无感）。

所有判断/生成类 Skill 经此调用；返回 (text, model_used)。
两者皆失败抛 IntegrationException，由 harness/调用方按 routable=挂起 / 其它=failed不阻断 处置。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.integrations.llm import ChatClient

logger = logging.getLogger("ticket_hub.llm")

_claude: Optional[ChatClient] = None
_deepseek: Optional[ChatClient] = None


def _clients() -> tuple[ChatClient, ChatClient]:
    global _claude, _deepseek
    if _claude is None:
        _claude = ChatClient(settings.claude_base_url, settings.claude_api_key, settings.claude_model, integration="claude")
    if _deepseek is None:
        _deepseek = ChatClient(settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model, integration="deepseek")
    return _claude, _deepseek


async def chat(
    *,
    system: Optional[str] = None,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> tuple[str, str]:
    """调 LLM：先 Claude，失败降级 DeepSeek。返回 (回复文本, 实际模型 'claude'|'deepseek')。"""
    claude, deepseek = _clients()
    try:
        text = await claude.chat(system=system, user=user, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
        if text and text.strip():
            return text, "claude"
        logger.warning("Claude 返回空内容，降级 DeepSeek")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude 失败，降级 DeepSeek: %s", exc)
    text = await deepseek.chat(system=system, user=user, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
    return text or "", "deepseek"
