# ticket-hub Skill 详规与时序设计 v2

> 依据：需求基线 v2（《需求基线与数据模型草案》《需求澄清变更摘要-v2》）。处理单元 = `t_ticket_info` 单条（不拆单）。
> 运行模型：**Runner(harness，唯一读写 DB + 写 `t_skill_log`) → Skill(纯函数/SKILL.md，不连库) → Integrations(HTTP)**。
> ⚠️ v2 重大变更：移除 Dify；ask agent 改 open-api-channel 四步异步；助手只读 NL2SQL；新增 reply-humanize；Skill 重划为 9 个。

---

## 〇、设计约定

- **Skill 绝不碰 DB**：入参 payload、出参 result 信封 `{status, fields, evidence, model_used}`。Runner 负责落库 + 每步写 `t_skill_log`。
- **分层——"是不是 Skill" 与 "走不走统一日志" 解耦**：
  - **harness 统一编排 + 日志**：全部步骤经 `_run_step(name, fn, payload)` 包裹 → 统一写 `t_skill_log`。
  - **真 Skill（SKILL.md，DB 权威，页面可编辑，✏️v2=9 个）**：`ticket-routable / ticket-tagging / info-dedup / hub-dedup / answer-router / reply-humanize / faq-record / faq-review / assistant-nl2sql`。
  - **普通 py（无 SKILL.md，不可页面改）**：`faq-retrieve / agent-answer / linear-sync / ticket-dispatch / desensitize / 入站&退回&观察期&队列&回写&通知` 等。
  - ✏️ **v2 划分变更**：
    - `faq-retrieve` 原 Dify SKILL → **降 py**（硅基流动向量检索本地 t_faq，纯确定性）。
    - `answer-router` 原 py 规则 → **升 SKILL**（先 transfer_result，NO_ACTION 时 LLM 语义分类）。
    - `info-dedup`/`hub-dedup` 原纯阈值 → **SKILL**（embedding 召回 + LLM 二次语义确认）。
    - 🆕 `reply-humanize`（去 AI 化）、`assistant-nl2sql`（NL→SQL，护栏在 py）。
  - ⚠️ **routable 是流转闸门**：✏️v2.1 全规则（判定逻辑+关键词清单+模块黑名单）写进 SKILL.md，**全页面可热改，取消 py 硬护栏**；LLM 失败降级 DeepSeek，皆失败则**任务挂起**（不再有关键词规则兜底）。
  - **护栏红线**：判断/提示词进 SKILL（可热改）；**安全控制(NL2SQL 的 SELECT-only/LIMIT/PII脱敏)、集成、调度永远留 py**，绝不进可编辑 SKILL。
- **降级**：Claude→DeepSeek；硅基流动→DeepSeek/视未命中；ask agent 失败/TRANSFER→分支 C；reply-humanize 失败→原文回写。
- **Skill 异常**：harness 兜底记 `failed`，不中断 worker；任务 `t_task_queue` 重试 ≤3 → `abandoned`（告警+手动重入队）；**依赖全挂→挂起不消费**。

---

## 一、Skill 详规

### S1. ticket-routable（步骤1 流转判断，不拆单）— **真 Skill** Claude→DeepSeek（SKILL.md，✏️v2.1 全规则页面可改）
| 项 | 内容 |
|---|---|
| 触发 | 入站入库后第一步（退回单也跑） |
| 输入 | title / description / product_name / module / has_attachment |
| 逻辑(SKILL.md 可编辑) | LLM 按 SKILL.md 判定：① **非一对一**(≥2 显式编号 或 分隔词接 **≥10 字**新问题) → `不接管-多问题`；② 描述 **<15 字** 且 无附件 **且 LLM 判语义不明** → `不接管-不可流转`；③ 命中非发票云模块黑名单且无发票云关键词 → `不接管-不可流转`；④ 完全无发票云关键词 → `不接管-不可流转`；⑤ 否则 `可流转`。**✏️模块黑名单+关键词清单写在 SKILL.md 内，页面可改** |
| 输出 | routable / route_action / route_reason |
| harness | 不接管 → 按来源动作(KSM零回写returned / 智齿话术+ticket_status=3 / assistant私信)；可流转且 KSM → `lockKsmOrder`。**✏️退回单(FR-01)：照常判断+跑完AI作参考，末端一律转人工 pending_manual** |
| **异常** | Claude→DeepSeek 降级；✏️**两者皆失败 → 任务挂起等待**(不再有关键词规则兜底，v2.1 取消 py 硬护栏)；FR-05 判定逻辑全在 SKILL.md |

### S2. ticket-tagging（步骤2 打标）— Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 输入 | 工单文本 + product_tags(14 类候选) + func_modules(157 标签+触发词) |
| 逻辑 | LLM 在候选中择优选 **产品线 + 功能模块**（各单选）；**研发责任人由 harness 查表补**（✏️v2.1 方案C：模块+责任人映射写在 SKILL.md 内，拆两段用途——责任人不进 LLM prompt，harness 解析映射后确定性查表） |
| 数据源 | ✏️v2.1：14产品线/157模块/模块→责任人映射**均以 SKILL.md 为权威源，页面可改**（原 xlsx 仅首次种子导入） |
| 输出 | ai_product_tag / ai_func_module / ai_dev_owner |
| **异常分支** | 产品线无法判断 → 标`无法判断`+继续(不阻断)；模块返回非候选 → 取最近邻或标`无法判断`；**dev_owner 查表无命中 → `dev_owner_missing=true` + 默认接口人**（走配置） |

### S3. info-dedup（✏️v2.1 工单层短路出口，打标后→FAQ 前）— Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 位置 | ✏️**打标后、FAQ 检索之前**（短路闸，优先级高于 FAQ） |
| 输入 | 当前工单 + 近 120 天同产品线候选（harness 硅基流动 embedding 取 top8 喂入） |
| 逻辑 | ✏️**阈值 0.85**（从 0.8 调高），≥阈值召回 + LLM 二次语义确认是否真重复 |
| 命中(harness) | ✏️**短路**：复用重复单中"有有效 final_reply 且已关单(done/观察期)的最近一单"答复 → 回写当前工单关单 → resolved_at → **结束**（不调 agent/分类/收录）。记 `dup_ticket_ids` + `reused_from_ticket_id` |
| 回退 | ✏️重复单中无任何有效答复 → 不短路，照常走流水线 |
| 物理合并 | ✏️**不合并**（两单各自存在，仅短路复用答复） |
| 输出 | is_duplicate / dup_ticket_ids / reused_from_ticket_id |
| 异常 | 硅基流动挂 → 降级"非重复"，照常走流水线 |

### S4. faq-retrieve（步骤3.1 FAQ 检索）— ✏️**普通 py**（硅基流动向量检索本地 t_faq）
| 项 | 内容 |
|---|---|
| 输入 | 脱敏 query → 硅基流动 embedding → 与本地 `t_faq.embedding` 余弦相似度比对 |
| 逻辑 | 候选过滤 `review_status != 'rejected'`（只比 approved+pending_review）；取最高分，**> `faq_hit_threshold`(默认 0.8，可配)** → 命中 |
| 命中(harness) | `final_reply` = t_faq 正文 → **直接回写关单**（智齿 `save_ticket_reply` / KSM `handleKsmOrder`）→ 记 `resolved_at` → 结束 |
| 输出 | hit / faq_hit_id / faq_score / faq_content |
| 异常 | 硅基流动不可用 → 视为未命中，进 S6 ask agent |

### S5. desensitize（脱敏·3 处）— 规则
| 项 | 内容 |
|---|---|
| 调用点 | ① 调 ask agent 前(question) ② 答客户/回写前(answer) ③ 收录 FAQ 前 |
| 逻辑 | ✏️v2.1 两类：**①完全替换**(公司名/联系人/单号FPY/HUB/ZC/R/供应商订单号/合同号/账号/authCode/邮箱/座机/税号 + 凭证类按字段名抹值:clientSecret/entryKey/appSecret/privateKey/password/token/secret)；**②部分保留打码**(手机号前3后4`138****5678`、身份证前6后4) |
| 输出 | desensitized_text |

### S6. agent-answer（步骤3.2 ask agent 答复）— ✏️ask agent（open-api-channel 四步异步）
| 项 | 内容 |
|---|---|
| 鉴权 | `get_token`：`md5(appid+create_time+app_key)` → token（24h 缓存，同智齿签名） |
| 调用链 | **每工单一会话**：`ask_init`(取动态 `ai_agent_cid`) → `POST answer_async`{question, images[MinIO public_url], uid, user_name} → 轮询 `GET answer_async/{task_id}`(✏️每 60s 一次、最多 3 次) → `end_session` |
| 返回 | `data.answer`(纯文本) + `transfer_result`(NO_ACTION\|TRANSFER) + `robot_answer_type` |
| 输出 | ai_reply(answer 原文) / transfer_result |
| **异常分支** | token 失效刷新重试；轮询 `status=ERROR`/超时/`errcode=100002`/空 → **转分支 C**；`transfer_result=TRANSFER` → 直接 C（见 S7） |
| 约束 | 同一 cid 同时只能一个请求（会话独占）→ 故每工单独立会话；images ≤5 张、≤5MB、公网可达 URL |

### S6.5 reply-humanize（D 答复去 AI 化）— 🆕**真 Skill** Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 触发 | **仅分支 D 正常答复**，回写客户前（FAQ 命中/C 补料/不接管 不过） |
| 顺序 | 提取两段(问题根因+解决方案) → **reply-humanize(去AI化)** → desensitize(脱敏) → writeback |
| 逻辑(SKILL.md 可编辑) | 改写成自然人工客服口吻，去 AI 腔/免责声明/"作为AI"等；**红线：只改表达，不改事实/解决步骤/具体操作动作** |
| 输出 | humanized_reply |
| 异常 | LLM 失败 → 用原文回写，不阻断关单，记 log |
| FAQ 收录取数 | faq-record 用 **humanize+脱敏后**版本归纳（FAQ 库存高质量人工口吻内容） |

### S7. answer-router（步骤3.3 分支路由）— ✏️**真 Skill** Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 逻辑 | **① 先看 `transfer_result`：`TRANSFER` → 直接 C**；② `NO_ACTION` → LLM **语义判定** agent 全文归类：bug→A / 需求→B / 【需要您提供】为核心问题无法定位→C / 正常回答→D；无法识别→C |
| 取数 | `final_reply` = 【问题原因】→【问题根因】+【解决建议】→【解决方案】；`full_reply` = 全文(含【需要您提供】) |
| 输出 | answer_branch / final_reply / full_reply / supply_note |
| 异常 | LLM 失败 → 兜底 C |

### S8. hub-dedup（分支A 转研发去重）— Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 输入 | 当前问题 + 历史 hub 候选（harness 硅基流动 top5 召回喂入） |
| 逻辑 | **embedding 召回 + LLM 二次语义确认**；阈值 0.7（可配），LLM 判定"是否真重复" → 重复(关联已有 hub_id)/否则新建 |
| 输出 | is_dup / dup_hub_id / score |
| harness | 重复 → `info.rd_hub_id` 关联已有 hub；新建 → 建 hub(full_reply) → S9。**A 分支不回写客户，status=pending_rd（SLA 不豁免）** |
| 异常 | 硅基流动/LLM 挂 → 降级"非重复"(新建)，避免漏单 |

### S9. linear-sync（分支A 新 bug）— Linear GraphQL（本期真启用）
| 项 | 内容 |
|---|---|
| 逻辑 | `issueCreate`(team=CNPRD)，描述=【问题】+【答复 full_reply】 |
| 输出 | linear_issue_id / linear_url → 落 hub，`linear_sync_status=synced` |
| **异常分支** | 失败 → hub 保留，`linear_sync_status=failed` + 入 `t_task_queue` 重试(≤3)；超限 → 飞书通知人工 |

### S10. faq-record（分支D 收录·归纳）— Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 逻辑 | description + **humanize+脱敏后的 final_reply** 归纳 `{title≤20, content≤300}` |
| 前置去重 | harness 硅基流动 0.85 与 t_faq 同产品线比对，≥0.85 → `faq_status=no_faq` 终止 |
| 输出 | faq_title / faq_content（写入即计算 embedding 落库，供 S4 检索） |

### S11. faq-review（分支D 收录·审核，**不阻断**）— DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 顺序 | **先入库后审核**：✏️harness 先写**本地 t_faq**(`review_status=pending_review` + embedding)，**再**调 S11（无 Dify 写入） |
| 逻辑 | 审核 敏感信息/事实性/内部细节 → `{approved:bool, reason}` |
| harness | approved → `review_status=approved`；rejected → `review_status=rejected` + **飞书通知审核人**（人工决定删/改）。✏️检索侧 S4 已过滤 rejected |

### S12. ticket-dispatch（转人工·B/C/退回/不接管转人工）— ✏️v2.1 规则（按数量配额派单）
| 项 | 内容 |
|---|---|
| 触发 | 转人工那一刻（B/C/退回末端/不接管转人工）；bug 走 hub 不走此 |
| 逻辑 | ✏️**按数量配额比例**（`alloc_value`）分派到具体处理人（本期全局单名单，页面可配）；兜底：溢出人→默认人→群发 |
| harness | 飞书群**@对应处理人** + `status=pending_manual` + 记 `dispatch_assignee`/`dispatched_at` + t_dispatch_log |

### S13. assistant-nl2sql（智能助手·只读统计）— 🆕**真 Skill** Claude→DeepSeek（SKILL.md）
| 项 | 内容 |
|---|---|
| 触发 | 用户在助手对话发自然语言统计指令 |
| 逻辑(SKILL.md 可编辑) | NL → SQL 生成（提示词可热改）；全表全字段可查 |
| **护栏(py 执行层，不可热改)** | **强制 SELECT-only**（禁 UPDATE/DELETE/DROP）+ **结果 LIMIT 封顶** + **PII 列按角色脱敏**（visitor 脱敏，handler/admin 明文） |
| 输出 | 查询结果（对话机器人返回，可表格/图表） |
| 约束 | ✏️**本期只读，不做任何写/操作触发**（关闭工单/改责任人等降为后续规划） |

---

## 二、主流程时序

```
KSM/智齿/assistant webhook
  └─(KSM) /webhook/ksm: 存 noticeNum → 入队 ksm_intake
        worker ksm_intake: subscribeCallback 拉全量 → normalize(附件→MinIO) → 入库 → 入队 run_pipeline
  └─(智齿) /webhook/zhichi: normalize → 入队 sync_ticket → 入库 → 入队 run_pipeline
  └─(assistant) 助手提单: 建单 source=assistant → 入队 run_pipeline
        │  ★ 幂等: 编号(source_id)已存在 → 【退回】更新原单+退回标签+return_count+1
        │            +status=pending_manual+飞书通知人工 → ✏️跑完AI作人工参考→末端转人工 → END
        │  ★ SLA: sla_start_at=created_at, sla_due_at=created_at+48h
        ▼
worker run_pipeline(info_id):
  S1 routable ──不接管──> ┌ KSM: feishu-notify + status=returned(零回写)
        │                 └ 智齿: feishu-notify + 固定话术 + ticket_status=3 ──> END
        │可流转
        │(KSM) lockKsmOrder 接管
        ▼
  S2 tagging(dev_owner查表,无映射→默认接口人)
        ▼
  S3 info-dedup(✏️短路出口 0.85, 打标后→FAQ前)
        │命中 → 复用历史最近有效答复 → writeback关单 → resolved_at ──> END
        │未命中/无有效答复
        ▼
  S5 desensitize(query) → S4 faq-retrieve(✏️硅基流动 本地t_faq >0.8 过滤rejected)
        │命中 → final_reply=FAQ → writeback(关单) → resolved_at → status进观察期 ──> END
        │未命中
        ▼
  S5 desensitize(question) → S6 agent-answer(✏️open-api-channel 四步异步)
        │agent失败/transfer_result=TRANSFER → 分支C
        ▼
  S7 answer-router(✏️先transfer_result,后LLM语义分类):
     A → S8 hub-dedup → (新)S9 linear-sync / (重)关联 rd_hub_id → 不回写客户, status=pending_rd
     B → dispatch(群发) + feishu-notify → status=pending_manual
     C → dispatch + feishu-notify / KSM supplyKsmOrder / 智齿统一回复 → status=pending_manual
     D → S6.5 reply-humanize(✏️去AI化) → S5 desensitize → writeback(关单 final_reply) → resolved_at
         → S10 faq-record(用humanize后版本)→ 写本地t_faq(pending_review)+embedding
         → S11 faq-review → feishu-notify(仅rejected/异常)
        ▼
  全程每步 → t_skill_log
  assistant来源: 上述回写/话术统一改 飞书私信提单人; D答复直接done(无观察期)

[周期任务 sla_scan] 每日北京时间 08:00(工作日计时, 排除周末/节假日):
  SLA-1人工(t_ticket_info, ai_dev_owner) + SLA-2研发(t_ticket_hub, dev_owner) 分别扫
  → 按责任人 计数+单号列表 → 分不同 webhook 群通报(无限直到关闭, 观察期不跑)

[周期任务 observe_scan] resolved_at+14天(可配) 且未退回 → 本地 status=closed(不回写来源系统)

[队列健康监控] 积压>阈值→系统告警; 依赖全挂→挂起不消费; abandoned→告警+手动重入队
```

---

## 三、回写（writeback）分支→接口映射（v2）

| 分支/场景 | 来源 | 接口 | 关键参数 |
|---|---|---|---|
| FAQ 命中 / D 正常答复（关单） | 智齿 | `save_ticket_reply` | ticket_status=3, reply_content=问题根因+解决方案(拼 `<br>`) + 图片 MinIO 链接 |
| FAQ 命中 / D 正常答复（关单） | KSM | `handleKsmOrder` | 推进节点至处理完成(4)；reply=两段 + 图片 MinIO 链接 |
| C 补充资料 | KSM | `supplyKsmOrder` | dealOpinion=full_reply 引导补料 |
| C 补充资料 | 智齿 | `save_ticket_reply` | ✏️ticket_status=2(等待回复)，发"需要您提供…" |
| 不接管 | KSM | **无回写** | 仅 feishu-notify |
| 不接管 | 智齿 | `save_ticket_reply` | ✏️固定话术 + ticket_status=3 关单 |
| A bug / B 需求 | — | **不回写**，挂起 | A→pending_rd / B→pending_manual |
| assistant 全场景 | — | **飞书私信提单人** | 无外部系统回写 |
| 接管 | KSM | `lockKsmOrder` | account/accountName/accountNumber(飞书工号) |

> ✏️v2：关闭 = 回写到**处理完成**(KSM4/智齿3) + 记 `resolved_at`；**14 天观察期到期由 observe_scan 置本地 closed，不再回写**。图片**一律给 MinIO public_url 链接**(不塞二进制)。回写直接真启用(无 DRY_RUN)。

---

## 四、周期扫描器设计（v2）

### SLA 扫描器（sla_scan）✏️v2.1 双 SLA + 工作日 + 每日一次
- **触发**：✏️**每天北京时间 08:00 一次**（去掉 14:00）。
- **工作日计时**：✏️排除周末+法定节假日（接国务院节假日 API，本地 `t_holiday` 兜底）；时长各自可配（`sla_manual_hours`/`sla_rd_hours`，默认 48）。SLA-1 起点=工单 `created_at`，✏️**SLA-2 起点=hub 创建时刻**(`rd_sla_start_at`)。
- **SLA-1 人工**（t_ticket_info）：扫 `status NOT IN(done,closed,returned) AND now>sla_due_at` → 按 `ai_dev_owner` 分组 **计数+单号列表** → 人工 SLA 群。`dev_owner_missing`→"未分配"桶。
- **SLA-2 研发**（t_ticket_hub）：扫 `status未闭环 AND now>rd_sla_due_at` → 按 hub `dev_owner` 分组计数+单号 → 研发 SLA 群（不同 webhook）。
- **bug 接力**：bug 单 info 转研发后停 SLA-1，由 hub SLA-2 接力（不双重通报）。
- **去重**：`sla_notified_marks`/`rd_sla_notified_marks` 按"日期+08:00"去重。
- **停表/排除**：到达终态或 `resolved_at`/`rd_resolved_at`；✏️**观察期不跑 SLA**。

### 观察期扫描器（observe_scan）🆕
- **扫描**：`resolved_at IS NOT NULL AND status NOT IN(closed,returned) AND now() > resolved_at + 14天(可配)`。
- **动作**：本地 `status=closed`（**不回写来源系统**）。
- **退回中断**：观察期内编号被重推 → 退回逻辑接管，取消自动关闭。
- **范围**：KSM/智齿；assistant 无观察期（D 答复直接 done）。

### 队列健康监控 🆕
- 积压（待处理 >N 或 最老等待 >M 分钟，走配置）→ 系统级飞书告警（与责任人 SLA 通报区分）。
- 关键依赖(agent+DeepSeek)全挂 → 探活，**挂起不消费**，恢复后续跑，不耗光重试。
- `abandoned` 任务 → 飞书告警 + 后台手动重入队。

---

## 五、统一飞书通知服务（feishu-notify）

收敛触发点为**单一服务**：

| 触发点 | 场景 | 卡片要点 |
|---|---|---|
| 不接管 | routable 退回 | 工单号/标题/退回原因 |
| 转人工 B/C | 需求/补料 | 工单号/分支/full_reply（群发） |
| 退回 | 编号已存在 | 工单号/第 N 次退回/最新内容 |
| FAQ 审核 | rejected/异常 | FAQ 标题/原工单/审核结论 reason |
| SLA 超时 | breached | ✏️按 ai_dev_owner 聚合**数量** |
| 系统告警 | 队列积压/abandoned | 队列深度/卡死任务 |
| assistant 答复 | 各分支 | ✏️**飞书私信提单人**（非群） |

- **配置化**：✏️`FEISHU_BOT_WEBHOOKS`（支持多个）+ 各场景模板 → **配置文件**（不硬编码）。
- **健壮性**：发送失败重试(≤3)；同工单+同场景短时去抖防刷屏。

---

## 六、异常与重试矩阵（v2）

| 环节 | 失败表现 | 处置 |
|---|---|---|
| KSM subscribeCallback | status=false/超时 | 入队重试 ≤3 → abandoned + 告警 |
| LLM(routable/tagging/dedup/router/humanize/record) | Claude 失败 | 降级 DeepSeek；全失败记 failed 不阻断 |
| 硅基流动 embedding | 服务挂 | dedup 降级"非重复"；✏️**FAQ 检索视未命中走 agent** |
| ask agent | 失败/空/ERROR/超时(轮询60s×3未DONE)/TRANSFER | 转分支 C 人工 |
| reply-humanize | LLM 失败 | ✏️用原文回写，不阻断关单 |
| Linear | issueCreate 失败 | hub 保留+重试 ≤3 → 人工 |
| 回写 | 失败 | 记 writeback_error + 重试 ≤3 退避（直接真回写） |
| 编号生成 | 并发重号 | **PG sequence** |
| 关键依赖全挂 | agent+DeepSeek 都不可用 | ✏️任务挂起不消费，探活恢复 |
| **abandoned** | 重试耗尽 | ✏️**自动置 pending_manual + 飞书通知 + 后台手动重入队** |
| ~~Dify~~ | — | ✏️v2 已移除 |

---

## 七、附件/图片处理（MinIO，v2）

**入站转存（normalize 阶段，普通 py）**
- 解析 KSM `raw.attachment[]` / 智齿 `raw.file_str` → 逐个下载（KSM 需 `User-Agent: Mozilla/5.0`）→ PUT MinIO → 写 `t_attachment(scope=ticket)` 含 `public_url`。
- 路径：`tickets/{ticket_no}/{uuid}_{filename}`；`is_image` 按 mime；失败不阻断（记 failed，可重试）。

**回写客户（✏️v2 一律给链接）**
- 关单/补料回写客户图片：✏️**一律附 MinIO `public_url` 链接**（`https://fpy-jfsv.kingdee.com:8864/...`），**不往来源系统塞 base64 二进制**。
- ask agent `images[]` 同样传 `public_url`（公网可达）。

**FAQ 图片（收录阶段）**
- 来源 = 工单原图：引用工单 `t_attachment(scope=ticket)` 图 → 写 `t_attachment(scope=faq)`；FAQ 正文以 MinIO `public_url` 引用。

**已确认细则**：P1 全类型转存 · P2 暂不 OCR · P3 FAQ 图源=工单原图 · P4 服务端内网直连 MinIO；✏️**对外暴露 `https://fpy-jfsv.kingdee.com:8864/`** 供客户/agent 访问。

---

## 八、Skill 管理与热加载（skill-creator 标准 + 页面编辑，v2）

**目录标准**：`backend/skills_md/<name>/`（`SKILL.md` frontmatter `name/description` + 可选 `impl.py`）。首次种子导入 `t_skill_md`。

**权威源 = DB（`t_skill_md`）**：解决 backend/worker 双容器一致性 + 热加载。runtime `run_skill_md(name)` 从 DB 读（缓存+version 失效）→ 喂 Claude/DeepSeek；保存清缓存热生效。

**管理 API（仅 admin）**
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/skills` | 列表（type/editable/version） |
| GET | `/api/v1/skills/{name}` | 取 SKILL.md 正文 |
| PUT | `/api/v1/skills/{name}` | 编辑（仅 9 个 LLM 类）→ 校验 → 存 + history + `t_operation_log` → bump version → 清缓存 |
| POST | `/api/v1/skills/{name}/preview` | 样例工单试跑预览，不落库 |
| POST | `/api/v1/skills/{name}/rollback` | 回滚到 history 某版本 |

**约束（✏️v2 = 9 个可编辑）**
- 可编辑 LLM 类 9 个：`ticket-routable / ticket-tagging / info-dedup / hub-dedup / answer-router / reply-humanize / faq-record / faq-review / assistant-nl2sql`。
- py 类（faq-retrieve/agent-answer/linear-sync/ticket-dispatch/desensitize/NL2SQL 护栏等）**只读展示**，标注"逻辑在代码，不可热改"。
- ⚠️ **assistant-nl2sql 仅"NL→SQL 提示词"可编辑；SELECT-only/LIMIT/PII 脱敏护栏在 py，页面改不到**。
- 保存前校验 frontmatter + 正文非空；全部编辑入 `t_operation_log`（前后值）+ 版本历史，支持回滚。
