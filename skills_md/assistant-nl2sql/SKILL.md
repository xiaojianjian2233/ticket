---
name: assistant-nl2sql
description: 智能助手自然语言转 SQL（只读统计）。把用户自然语言统计指令转成 PostgreSQL 查询语句。安全护栏（SELECT-only/LIMIT/PII脱敏）在 py 执行层强制，不在本 Skill。提示词可页面热改。
editable: true
model: claude→deepseek
---

# assistant-nl2sql — 自然语言转 SQL（只读统计）

> Skill 纯生成，**不连 DB、不执行 SQL**。本 Skill 只产出 SQL 文本，执行 + 安全护栏 + 结果脱敏全部由 py 层（sql_guard）强制。
> ⚠️ **本期只读**：只生成 SELECT 查询，不生成任何写/操作语句（关闭工单/改责任人等本期不做）。

## 输入 payload
| 字段 | 说明 |
|---|---|
| nl_query | 用户自然语言统计指令（如"今天有多少工单"、"各产品线分布"） |
| schema_hint | 可查询表结构摘要（harness 注入：表名/字段/注释，便于生成准确 SQL） |
| user_role | 用户角色（仅作生成参考；PII 脱敏由 py 层按角色强制，不在此） |

## 生成要求

把 `nl_query` 转成一条 **PostgreSQL SELECT** 查询：
- **只生成 SELECT**（禁 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE 等）。
- 全表全字段可查（业务表+用户/权限/审计表均可统计）。
- 用 `schema_hint` 的真实表名/字段名，避免臆造。
- 复杂统计可用 JOIN/GROUP BY/聚合函数/时间过滤。
- **不要自己加 LIMIT 之外的篡改**；LIMIT 封顶由 py 层统一加。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "sql": "<生成的 SELECT 语句>",
    "explain": "<这条查询在统计什么，给用户看的自然语言说明>"
  },
  "evidence": "<NL→SQL 的映射要点>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界（护栏在 py，本 Skill 仅生成）
- LLM 失败 → 提示用户"无法理解，请换种问法"。
- 生成了非 SELECT 语句 → **py 层 sql_guard 强制拦截**（拒绝执行，记 sql_guard_pass=false），本 Skill 不负责拦截但应尽量只生成 SELECT。
- **py 层强制（不可在本 Skill 热改）**：SELECT-only 校验、结果 LIMIT 封顶、PII 列按角色脱敏（visitor 脱敏/handler·admin 明文）。
- 写操作（关闭/改责任人）→ 本期不生成，py 层提示"该操作暂未开放"。
