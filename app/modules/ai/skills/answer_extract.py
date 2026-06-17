"""answer_extract（py）：从 agent 答复提取两段。

final_reply = 【问题根因】+【解决方案】（D/FAQ 回客户用）；
full_reply  = 全文（含【需要您提供】，转人工/研发用）；
supply_note = 【需要您提供】内容（C 分支）。
模板别名：问题原因→问题根因、解决建议→解决方案。
"""
from __future__ import annotations

import re

_SEG = re.compile(r"【([^】]+)】\s*([\s\S]*?)(?=【[^】]+】|$)")


def extract_answer(answer: str) -> dict:
    text = (answer or "").strip()
    segs = {name.strip(): body.strip() for name, body in _SEG.findall(text)}
    cause = segs.get("问题根因") or segs.get("问题原因") or ""
    solution = segs.get("解决方案") or segs.get("解决建议") or ""
    need = segs.get("需要您提供") or ""

    if cause or solution:
        parts = []
        if cause:
            parts.append(f"【问题根因】{cause}")
        if solution:
            parts.append(f"【解决方案】{solution}")
        final = "\n".join(parts)
    else:
        final = text  # 无结构标记 → 用全文
    return {"final_reply": final, "full_reply": text, "supply_note": need}
