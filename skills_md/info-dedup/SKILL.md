---
name: info-dedup
description: 工单去重二次确认（步骤③ 短路出口）。harness 用硅基流动 embedding 召回同产品线候选后，本 Skill 做 LLM 语义二次确认"是否真重复"，命中则 harness 短路复用历史答复关单。
editable: true
model: claude→deepseek
---

# info-dedup — 工单重复语义确认

> Skill 纯判断，**不连 DB**。embedding 召回由 harness（硅基流动）完成，候选随 payload 传入。
> 本 Skill 只做"召回候选是否真重复"的语义二次确认；命中后的短路复用/关单由 harness 执行。

## 输入 payload
| 字段 | 说明 |
|---|---|
| current_title / current_description | 当前工单文本 |
| candidates[] | harness 硅基流动召回的同产品线近 120 天 top8 候选，每项含：ticket_id、title、description、similarity、是否有有效答复(has_valid_reply) |
| threshold | 相似度阈值（默认 0.85，harness 注入，可配） |

## 判定逻辑

对 `candidates` 中 similarity ≥ threshold 的候选，逐一做 LLM 语义判断：
- 当前工单与候选是否为**同一个真实问题**（不只是字面相似，要语义同根因/同诉求）。
- 在语义确认为真重复的候选中，**优先选有有效答复（has_valid_reply=true）且时间最近的一条**作为复用源。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "is_duplicate": true/false,
    "dup_ticket_ids": [命中的真重复工单id...],
    "reuse_from_ticket_id": <选中的复用源id，无有效答复候选时为 null>
  },
  "evidence": "<判定为重复/非重复的语义依据>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界
- 硅基流动召回失败（harness 侧）→ harness 直接降级"非重复"，不调本 Skill。
- LLM 判断失败 → 降级"非重复"，照常走后续流水线（不误短路）。
- `reuse_from_ticket_id` 有值 → harness 短路复用该工单 final_reply 关单；为 null（重复但无有效答复）→ harness 不短路，照常走流水线。
- 本 Skill 不物理合并工单、不关单——只输出判断，动作由 harness 执行。
