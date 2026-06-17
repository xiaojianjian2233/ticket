---
name: faq-review
description: FAQ 内容审核（分支D 收录后，先入库后审不阻断）。DeepSeek 按四维（敏感信息/事实性/内部细节/表达质量）审核 FAQ，输出通过或驳回+维度。可页面热改。
editable: true
model: deepseek
---

# faq-review — FAQ 四维审核

> Skill 纯判断，**不连 DB**。先入库后审、不阻断：harness 已写 t_faq(pending_review) 后才调本 Skill。

## 输入 payload
| 字段 | 说明 |
|---|---|
| title | FAQ 标题 |
| content | FAQ 正文 |
| product_tag | 产品线 |

## 审核四维

逐维判断是否通过：

| 维度 | 检查 |
|---|---|
| ① 敏感信息残留 | 有无漏网 PII（手机/邮箱/税号/账号/密码）、密钥、单号 |
| ② 事实性 | 答复是否正确、无误导、解法可行 |
| ③ 内部细节泄露 | 有无内部系统名/源码/服务名/人员/架构等不应外露信息 |
| ④ 表达质量 | 是否清晰、通顺、适合入库复用 |

## 判定
- 四维**全过** → `approved`。
- **任一不过** → `rejected`（不分轻重）。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "result": "approved | rejected",
    "dim_sensitive": true/false,
    "dim_factual": true/false,
    "dim_internal": true/false,
    "dim_quality": true/false,
    "reject_dims": "<驳回的维度列表，approved 时空>",
    "reason": "<审核结论详情>"
  },
  "evidence": "<审核依据>",
  "model_used": "deepseek"
}
```

## 降级与边界
- DeepSeek 失败 → harness 保持 t_faq=pending_review（仍可被检索，不阻断），记 failed 重试。
- harness 收到输出：approved→review_status=approved；rejected→review_status=rejected（检索自动排除软下线）+ 飞书@审核人（notified 防重发）。
- 人工有最终决定权，可在审核页覆盖本 Skill 结果（人工编辑后直接 approved）。
- 写 t_faq_review 明细由 harness 执行。
