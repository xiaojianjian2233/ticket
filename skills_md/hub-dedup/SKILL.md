---
name: hub-dedup
description: 研发单去重二次确认（分支A bug 转研发前）。harness 用硅基流动召回历史 hub 候选后，本 Skill 做 LLM 语义确认"是否同一研发问题"，命中则关联已有 hub，否则新建。
editable: true
model: claude→deepseek
---

# hub-dedup — 研发单重复语义确认

> Skill 纯判断，**不连 DB**。embedding 召回由 harness（硅基流动）完成，候选随 payload 传入。

## 输入 payload
| 字段 | 说明 |
|---|---|
| current_problem | 当前 bug 问题归纳（含 full_reply 根因） |
| product_tag / func_module | 当前工单产品线/模块 |
| candidates[] | harness 硅基流动召回的历史 hub top5，每项含：hub_id、title、problem_summary、similarity |
| threshold | 相似度阈值（默认 0.80，harness 注入，可配）。先按阈值召回，再由本 Skill 大模型语义确认 |

## 判定逻辑

对 similarity ≥ threshold 的候选 hub，LLM 语义判断：
- 当前 bug 与候选 hub 是否为**同一个研发问题**（同根因/同代码缺陷，不只字面相似）。
- 确认为同一问题 → 关联该 hub；否则 → 新建。
- 多个候选都像 → 选语义最贴近的一个。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "is_dup": true/false,
    "dup_hub_id": <命中的已有 hub id，新建时为 null>,
    "score": <选中候选的 similarity>
  },
  "evidence": "<判定同一问题/不同问题的依据>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界
- 硅基流动召回失败 或 LLM 判断失败 → 降级 `is_dup=false`（**新建 hub**），避免漏单（宁可重复建，不漏 bug）。
- is_dup=true → harness 关联 info.rd_hub_id 到 dup_hub_id，**不新建 Linear issue**。
- is_dup=false → harness 新建 hub + linear-sync(issueCreate, CNPRD)，hub 默认 in_progress，SLA-2 启动。
- 本 Skill 只判断不执行；建 hub/调 Linear 由 harness。
