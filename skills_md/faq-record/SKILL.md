---
name: faq-record
description: FAQ 收录归纳（分支D 答复关单后）。把工单问题+去AI化脱敏后的答复归纳成简洁 FAQ（title≤20、content≤300）。前置去重由 harness 完成。可页面热改。
editable: true
model: claude→deepseek
---

# faq-record — FAQ 收录归纳

> Skill 纯判断/归纳，**不连 DB**。仅分支 D 答复关单后调用。
> 前置去重（硅基流动 0.85 比对同产品线 t_faq）由 harness 完成；≥0.85 则 harness 不调本 Skill。

## 输入 payload
| 字段 | 说明 |
|---|---|
| description | 工单问题描述 |
| final_reply | **humanize + 脱敏后**的答复（根因+方案） |
| product_tag | 产品线 |

## 归纳要求

把"问题 + 答复"归纳成一条可复用的 FAQ：
- **title**：≤20 字，概括问题（如"高德打车发票收票报网络繁忙"）。
- **content**：≤300 字，简洁的问题+解决方案，**面向通用场景**（去掉本工单特有的单号/客户/时间等细节，保留可复用的解法）。
- 内容已是脱敏后版本，归纳时不得引入新的 PII。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "faq_title": "<≤20字>",
    "faq_content": "<≤300字>"
  },
  "evidence": "<归纳要点，可空>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界
- 前置去重 ≥0.85 → harness 不收录（faq_status=no_faq），不调本 Skill。
- LLM 失败 → Claude→DeepSeek；都失败 → 跳过收录（不阻断 D 分支已完成的关单）。
- harness 收到输出后：写本地 t_faq(review_status=pending_review) + 算 embedding → 触发 faq-review。
- title/content 字数：本 Skill 按 ≤20/≤300 归纳，harness/应用层再校验。
