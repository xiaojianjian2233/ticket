# ticket-hub 部署说明（前后端分开 + 复用共享 PG）

## 拓扑
- **frontend**（nginx）：宿主 `:18025` → `/fpy/` 静态 + 反代 `/api` `/webhook` `/minio` 到后端/minio。访问 `http://dl.piaozone.com:18025/fpy/`。
- **backend**（uvicorn :8000）：FastAPI API + webhook。
- **worker**：消费 `t_task_queue` 跑流水线。
- **scheduler**：双 SLA(每日08:00) / 观察期 / 队列监控 / 节假日。
- **minio**：附件存储（public_url 经 nginx `/minio/`）。
- **PostgreSQL**：复用宿主共享 `docker-db_postgres-1` 的 `ticket_hub` 库（`.env` 的 `DATABASE_URL=...@106.55.57.40:5432/ticket_hub`），已装 ~~pgvector~~ → embedding 用 jsonb+应用层余弦。

## 前置
1. `ticket_hub` 库已建 + 23 表已应用（`docs/ddl.sql`）+ 种子已导入（`scripts/seed.py`：9 SKILL.md/模块映射/派单兜底）。
2. `.env` 在仓库根（含生产凭证，勿提交）。compose 用 `env_file: ../.env`；容器内覆盖 `MINIO_ENDPOINT=minio:9000`。

## 部署步骤（服务器）
```bash
# 1) 同步代码到服务器（本机执行 deploy/sync.sh 或手动 rsync 到 /data/ticket-hub）
# 2) 服务器上构建并启动
cd /data/ticket-hub
bash deploy/deploy.sh up        # build + up -d
bash deploy/deploy.sh seed      # 首次：导入 SKILL.md/种子（若未导入）
bash deploy/deploy.sh logs      # 看日志
```

## 生产红线（务必）
- **KSM 只调一次不重试**（`KSM_MAX_RETRY=0`）。
- **Linear 责任人只能李志坚**（`LINEAR_ASSIGNEE_ID` 已固化）。
- 开发/联调期 `WRITEBACK_DRY_RUN=true`（对外写只组装不真发）；确认无误再置 false 真回写。
- ask agent 单步端点不可用 → 走四步需 L2 凭证；当前 agent 失败优雅降级为分支 C（转人工），不阻塞。
