---
name: pipeline-v2-changes
description: 2026-06-11 流水线重大变更——双源分流、去FAQ检索、责任人后置、B进Linear、FAQ收录改C/B关单触发
metadata: 
  node_type: memory
  type: project
  originSessionId: 54aac31c-ad17-478d-88e2-abe60940f44b
---

## 双源流水线变更（v2.1 确认，2026-06-11）

### KSM 流水线（完整AI流水线）

```
KSM工单
  → 接入（归一/幂等/SLA-1）
       退回单 → 直接转人工(pending_manual) ✋结束
  → 流转判断（ticket-routable，不变）
       不接管 → 飞书通知 + returned（零回写）✋结束
       可流转 → lockKsmOrder 接管
  → 打标（产品线+功能模块，LLM）
  → 查 t_module_owner 补 dev_owner
  → info-dedup（硅基流动 top8 + ≥0.85 + LLM语义确认）
       命中 → 短路复用 final_reply → handleKsmOrder回写 → done ✋结束
       未命中 → ask agent
  → ask agent（拼装："{产品线}-{功能模块}：{原始问题}"）
  → answer-router（LLM语义判定）：
       D 正常答复 → handleKsmOrder 回写客户 → done（不脱敏，agent已处理）
       A bug      → 生成 hub+Linear → pending_rd（保持接管，等Linear回调）
       B 需求     → 生成 hub+Linear → pending_rd（保持接管，等Linear回调）
       C 资料缺失 → unlockKsmOrder 退回客户 → 飞书通知客服
       其它/兜底  → dispatch派单 → pending_manual → 飞书@处理人
```

### 智齿流水线（简化，不走agent）

```
智齿工单
  → 接入（归一/幂等/SLA-1）
       退回单 → 直接转人工(pending_manual) ✋结束
  → 打标（产品线+功能模块，LLM）（不走流转判断）
  → 查 t_module_owner 补 dev_owner
  → info-dedup（硅基流动 top8 + ≥0.85 + LLM语义确认）
       命中 → 短路复用 final_reply → save_ticket_reply回写 → done ✋结束
       未命中 → dispatch派单 → pending_manual → 飞书@处理人
```

### 关键变更点汇总

| 项目 | 原设计 | v2.1变更 |
|---|---|---|
| FAQ检索（S4） | 保留 | **去掉** |
| 责任人查表 | 打标时同步查 | **后置到A/B分支生成hub时** |
| agent入参 | 原始问题 | **拼装"{产品线}-{功能模块}：{原始问题}"** |
| D分支脱敏 | humanize→脱敏→回写 | **humanize→回写（去掉脱敏，agent已处理）** |
| B需求分支 | 转人工 | **进Linear（同A bug）** |
| FAQ收录触发 | D分支自动答复后 | **C/B人工关单后触发** |
| 智齿流水线 | 走完整流水线 | **简化：打标+去重+转人工，不走agent** |
| KSM退回单 | 照常跑AI末端转人工 | **直接转人工，不跑流水线** |
| 智齿退回单 | 照常跑AI末端转人工 | **直接转人工，不跑流水线** |
| A/B转研发后KSM状态 | 未明确 | **保持接管，等Linear回调后回写** |
| C资料缺失KSM动作 | supplyKsmOrder补料 | **unlockKsmOrder退回客户** |

### Linear 回调（不变）

- 计划+有日期 → 自动答复关单所有关联info（固定话术含发版日期）
- 计划+无日期 → 转回Linear附"未有具体发版日期"
- 产研退回+非空 → 飞书通知→转人工
- 产研退回+空 → 转回Linear附"未有退回原因"
- 其它 → hub原样显示不处理

### ask agent 接口信息（测试环境已验证）

- baseUrl: `http://123.207.158.7:9123`
- appId: `sadajfkefhksjh`
- appKey: `addk23-adasfsf-asdasc`
- 接口文档: `docs/open-api-channel.md`（项目根目录）
- 同步接口: `POST /open-api/ask/answer_no_stream`，timeout=600s
- 四步调用: get_token → ask_init → answer_no_stream → end_session

### pipeline_demo.py

- 位置: `/Users/junill/Documents/ticket-hub/pipeline_demo.py`
- 知识库缓存: `kb_cache.json`（1496条，FAQ+doc全量embedding）
- 开关: `ENABLE_KB=True/False` 控制是否启用硅基流动检索
- 当前状态: ENABLE_KB=False，只跑 agent→分类

**Why:** 2026-06-11 与用户逐条确认流水线改动，覆盖双源分流/去FAQ检索/责任人后置/B进Linear/FAQ收录改触发时机。
**How to apply:** 实现时以本记忆为准，原《业务流程与前端设计.md》开头的「双源流水线总览」章节已同步更新。
相关：[[ask-agent-contract]] [[dedup-rules]] [[linear-callback-sync]] [[close-return-semantics]]
