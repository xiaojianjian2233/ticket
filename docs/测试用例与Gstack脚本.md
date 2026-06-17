# ticket-hub 测试用例 + 浏览器自动化脚本（Gstack/Playwright）

> 脚本：`tests/e2e/`（Playwright 浏览器自动化，可直接运行）+ `tests/api/`（pytest 后端集成）。
> 运行 e2e：`cd tests/e2e && npm i && npx playwright install chromium && BASE_URL=http://dl.piaozone.com:18025 TOKEN=<JWT> npx playwright test`
> 运行 api：`BASE_URL=... PG_DSN='...' pytest tests/api -v`（pip install pytest requests "psycopg[binary]"）
> 登录态：e2e 用 `_auth.js` 注入 JWT 到 localStorage 绕开飞书 OAuth（TOKEN/ROLE 环境变量）。

## 逐模块测试用例（正常 / 分支 / 边界 / 异常）

### 1 登录 (login.spec.js)
| 类型 | 用例 | 元素定位 | 断言 |
|---|---|---|---|
| 正常 | 登录页渲染 | `button[飞书登录]` `text=ticket-hub` | 可见 |
| 异常 | 未登录访问 /tickets | 路由守卫 | URL→#/login |
| 边界 | token 过期(401) | 拦截器 | 清token+跳登录 |

### 2 工单 (tickets.spec.js)
| 类型 | 用例 | 断言 |
|---|---|---|
| 正常 | 列表加载/列/分页 | `.el-table` 行可见 |
| 正常 | 行→详情 | URL `/tickets/\d+`，含流转/答复区块 |
| 分支 | 按状态/来源/退回 筛选 | 表格刷新 |
| 边界 | 空结果/末页 | 空表不报错 |
| 异常 | visitor 无写按钮 / 改判非returned拒绝 | 按钮隐藏/400 |

### 3 智能助手 (assistant.spec.js)
| 类型 | 用例 | 断言 |
|---|---|---|
| 正常 | NL2SQL「各状态工单数」 | 返回表格/无数据 |
| 分支 | 提单卡片→建单 | source=assistant 入流水线 |
| 异常 | 写指令「删除工单」 | sql_guard 拦截「仅支持查询」 |
| 边界 | visitor 看 PII 脱敏 / 结果 LIMIT 封顶 | 138****/前N条 |

### 4 知识库 (faq.spec.js)
| 类型 | 用例 | 断言 |
|---|---|---|
| 正常 | FAQ 列表 / 语义搜索 | 卡片+相似度% |
| 分支 | 审核通过/驳回 | 状态更新, rejected 检索排除 |
| 异常 | 标题>20/正文>300 | 422 |

### 5 SLA (sla.spec.js)
| 正常 | 列表+概览卡片+tab | breached 红 / 系统告警 tab |

### 6 研发单 (hubs)
| 正常 | 列表/详情/Linear状态 | 关联工单+回调镜像 |

### 7 系统配置 admin (system.spec.js)
| 正常 | 用户改角色/启用 | 保存生效 |
| 正常 | Skill 编辑保存 | 「已热生效」+ version+1 |
| 分支 | Skill 回滚/预览 | 版本恢复/试跑结果 |
| 正常 | 派单配额/默认人、模块映射 CRUD | 列表刷新 |

### 8 端到端串联 (e2e_flow.spec.js + tests/api/test_smoke.py)
| 类型 | 用例 | 断言 |
|---|---|---|
| 正常 | 智齿 webhook→入队→worker→建单→打标→分支→pending_manual | DB 工单 product=星瀚-开票/owner=李志坚, skill_log 增长(已服务器验证✅) |
| 分支 | 同编号二次推送 | return_count+1, is_returned=true(退回转人工) |
| 异常 | agent 超时 | 降级分支 C(已验证) |
| 异常 | KSM 生产 | 只调一次不重试 |

## 已验证（服务器端真实）
- ✅ webhook→流水线全链路：FPY20260611000003 打标星瀚-收票/李志坚→分支C→pending_manual，skill_log 记录，队列闭环。
- ✅ 前端 18 页构建通过 + /fpy 200；后端 41 路由 + /api 200；4 关键鉴权(Claude/硅基/智齿/KSM/Linear)真实联通。

## 注（live 浏览器跑）
Gstack/Playwright 浏览器跑需在已连接的 Chrome 中选一个浏览器（本会话有多个，按"不询问"约定未交互选择）；脚本已就绪，指定浏览器后 `npx playwright test` 即可。
