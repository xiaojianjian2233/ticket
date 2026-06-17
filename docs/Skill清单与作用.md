# ticket-hub Skill 清单与作用

> Skill = 纯判断函数（不连业务 DB），提示词存 `t_skill_md`（页面可热改、版本回滚）。
> harness（`app/pipeline/runner.py`）负责取数/落库/分支；Skill 只吃 `variables` 出信封 `{status,fields,evidence,model_used}`。
> LLM 网关：Claude(claude-sonnet-4-6) → DeepSeek 兜底。

## 一、Skill 一览

| Skill | 流水线步骤 | 作用 | 模型 |
|-------|-----------|------|------|
| **ticket-routable** | S1 流转闸门（仅 KSM） | 判定工单是否可流转进入发票云处理；输出 可流转/不接管+原因 | claude→deepseek |
| **ticket-tagging** | S2 打标（KSM+智齿） | 从候选中择优选「产品线 + 功能模块」（责任人由 harness 查表，不在此） | claude→deepseek |
| **info-dedup** | S3 去重短路 | 对硅基召回的同产品线候选做语义二次确认「是否真重复」，命中则复用历史答复关单 | claude→deepseek |
| **answer-router** | S7 答复分类（仅 KSM） | 结合「问题原文+agent 答复」判 A(bug)/B(需求)/C(资料缺失·退回客户)/D(正常答复) | claude→deepseek |
| **hub-dedup** | S8 研发单去重（A/B 建 hub 前） | 对硅基召回的历史 hub 候选语义确认「是否同一研发问题」，命中关联已有 hub（不重复推 Linear） | claude→deepseek |
| **reply-humanize** | S6.5 去AI化（仅 D 回写前） | 把 agent 答复改写成人工客服口吻，去 AI 腔；只改表达不改事实/步骤 | claude→deepseek |
| **faq-record** | S10 收录（C/B 人工关单后触发） | 把问题+答复归纳成简洁 FAQ（title≤20/content≤300） | claude→deepseek |
| **faq-review** | S11 审核（收录后，先入库后审） | 四维（敏感/事实/内部细节/表达）审核 FAQ，输出通过或驳回+维度 | deepseek |
| **assistant-nl2sql** | 智能助手 | 自然语言→只读 PostgreSQL 统计（安全护栏在 py 执行层） | claude→deepseek |

> 已退役：`faq-retrieve`（v2.1 删除 S4 FAQ 检索短路，不再使用）。

## 二、去AI化开关（默认不开启）

配置 `SKILL_NO_AI`（逗号分隔 skill 名）。**列入者跳过 LLM**，直接返回下表「规则默认值」；不调用大模型、`model_used=none`。**默认空 = 全部走 AI**。

```env
# 默认（全 AI）
SKILL_NO_AI=
# 示例：关掉去重与润色的 AI（用规则默认）
SKILL_NO_AI=info-dedup,hub-dedup,reply-humanize
```

| Skill | 去AI化后的规则默认值 | 效果 | 安全性 |
|-------|--------------------|------|--------|
| info-dedup | `is_duplicate=false` | 不做去重，全部当新工单 | 安全（仅少省一次复用） |
| hub-dedup | `is_dup=false` | 每次新建 hub（不关联） | 安全（可能重复建单，靠人工合并） |
| reply-humanize | `humanized_reply=""` | harness 用 agent 原文回写 | 安全 |
| faq-record | `{}` | 跳过 FAQ 收录 | 安全 |
| faq-review | `approved=null` | 不自动审，留待人工 | 安全 |
| ticket-tagging | `产品线=无法判断, 模块=""` | 不打标 | ⚠️ 改变派单/责任田 |
| ticket-routable | `routable=true(默认接管)` | 不做流转判断，全部接管 | ⚠️ 会接管本不该接的单 |
| answer-router | `branch=D(直接答复)` | 不分类，一律按正常答复回写关单 | ⚠️ 高风险，慎用 |

**建议**：生产仅对前 5 个「安全」类按需去AI化（省成本/提速）；后 3 个是核心决策，去AI化会显著改变业务行为，仅供降级演练。

## 三、实现位置
- 开关：`app/core/config.py:skill_no_ai`、`.env:SKILL_NO_AI`
- 逻辑：`app/modules/ai/skill_runner.py`（`_no_ai_skills()` + `_NON_AI_FIELDS`，在 `run_skill` 入口拦截）
- 提示词：`skills_md/<name>/SKILL.md`（种子）→ `t_skill_md`（运行时源，页面热改）
