---
name: answer-router
description: ask agent 答复分类（步骤3.3）。结合"问题原文 + agent 答复"语义判定为 A(bug)/B(需求)/C(补充资料·退回客户)/D(正常答复) 四类之一。判断逻辑可页面热改。
editable: true
model: claude→deepseek
---

# answer-router — Agent 答复四分类

> Skill 纯判断，**不连 DB**。
> ⚠️ **输入必须 = 问题原文 + agent 答复一起判**（只看答复会误判，见 B/C 区分）。
> ⚠️ transfer_result 由 harness 先判：=TRANSFER 直接 C，不调本 Skill；=NO_ACTION 才调本 Skill 语义分类。

## 输入 payload
| 字段 | 说明 |
|---|---|
| question | **客户问题原文**（关键，判 B/C 必需） |
| agent_answer | ask agent 返回的答复全文 |

## 判定逻辑（语义，结合 question + agent_answer）

| 分支 | 判定特征 |
|---|---|
| **A bug** | agent 答复含**根因分析 + 源码定位 + 日志/TraceId + 解决方案面向研发改代码**（不是客户能自己操作的步骤） |
| **B 需求** | **问题原文是"新增功能/改造"诉求**（要新功能）→ 判 B。⚠️ 即使 agent 答复因诊断技能要 traceId/报错，也勿误判 C——以问题原文诉求性质为准 |
| **C 补充资料/转人工** | 问题原文是**具体故障/疑问**，但 agent **缺信息无法定位**（要环境/traceId/报错内容）**或** agent 明确无答案引导转人工/提工单 |
| **D 正常答复** | agent 给出**确定答复**：①客户可自行操作的解决步骤(操作型) **或** ②事实性查询结论(结论型，如"已查实推送成功/系统正常") |

**关键区分**：
- **B vs C**（两者 agent 都可能"要 traceId"）：看**问题原文**——需求诉求→B；故障+缺信息→C。
- **A vs D**：解决方案面向**研发改代码**(A) vs **客户自行操作/事实结论**(D)。
- 无法识别 → **兜底 C**。

## few-shot（真实样本）
- 「未找到流水号记录，请提供时间/traceId/环境」→ **C**（故障+缺信息）。
- 「知识库未找到，建议提工单/转人工坐席」→ **C**（无答案转人工）。
- 「根因：travelDate 格式解析错误，源码 InvoiceOperationService.java:244，建议改解析逻辑」→ **A**（根因+源码+改代码）。
- 「canBeDeduction=0 根因，CanBeDeductionEnum.java:101 字符串匹配缺陷，建议联系研发补字段」→ **A**。
- 「websocket 推送已查实成功，发票信息如下表…」→ **D**（事实查询结论）。
- 问题「新增更换logo需求」+ agent「这是新增需求，但本技能是诊断需 traceId…」→ **B**（问题是需求，勿因要 traceId 误判 C）。
- 问题「换logo点不动」+ agent「您用哪个环境？生产/测试/演示」→ **C**（故障+缺环境信息）。

## 输出 result
```
{
  "status": "ok",
  "fields": {
    "answer_branch": "A | B | C | D",
    "final_reply": "<取数：【问题原因】→根因 + 【解决建议】→方案；D/FAQ用>",
    "full_reply": "<agent 全文，含需补充项；A/B/C 转人工/研发用>",
    "supply_note": "<C 分支：需客户补充的信息项>"
  },
  "evidence": "<判为该类的语义依据>",
  "model_used": "claude | deepseek"
}
```

## 降级与边界
- Claude→DeepSeek；LLM 失败 → 兜底 C。
- 各分支动作由 harness(v2.1)：A→hub生成+Linear / B→hub生成+Linear(同A，需求也进研发) / C→supplyKsmOrder补充资料退回客户(状态置「补充资料」supplement) / D→reply-humanize→回写关单(agent已脱敏，不再脱敏)。FAQ 收录改由 C/B 人工关单后触发(不在 D 自动收录)。
