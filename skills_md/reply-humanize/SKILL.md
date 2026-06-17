---
name: reply-humanize
description: 答复去 AI 化（仅 D 正常答复回写客户前）。把 agent 答复改写成自然人工客服口吻，去除 AI 腔/免责声明，红线是只改表达不改事实与解决步骤。可页面热改。
editable: true
model: claude→deepseek
---

# reply-humanize — 答复去 AI 化

> Skill 纯判断/改写，**不连 DB**。仅分支 D 正常答复、回写客户前调用（FAQ 命中/C 补料/不接管 不过本 Skill）。
> 顺序：提取两段(根因+方案) → **reply-humanize(本步)** → desensitize(脱敏) → writeback。

## 输入 payload
| 字段 | 说明 |
|---|---|
| final_reply | 待改写的答复（已提取的【问题根因】+【解决方案】两段） |

## 改写要求

把答复改写成**自然的人工客服口吻**：
- 去除 AI 腔/机械感（"根据分析"、"综上所述"、过度结构化的标号堆砌）。
- 去除免责声明、"作为 AI 助手"、"我是…机器人"等表述。
- 去除"以上分析是否帮助您解决问题，请回复 1/2"这类机器人式结尾。
- 语气自然、简洁、专业，像真人客服在回复。

## 红线（硬约束，不可违反）

**只改表达，不改事实与解决步骤：**
- 不得篡改具体操作动作（如"重启服务"不能改成别的动作）。
- 不得改动技术参数、字段名、数值、版本号。
- 不得新增或删除解决步骤。
- 只调整措辞、语气、行文，事实内容 100% 保留。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "humanized_reply": "<去AI化后的答复>"
  },
  "evidence": "<改写要点，可空>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界
- LLM 失败 → harness 用**原文 final_reply 回写**，不阻断关单，记 log。
- 输出后由 harness 接 desensitize 脱敏，再 writeback。
- FAQ 收录（faq-record）使用 **humanize+脱敏后**版本归纳。
