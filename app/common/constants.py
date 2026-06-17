"""全局常量 + 来源系统状态码映射。"""
from __future__ import annotations

# ---------------- 来源系统状态码（回写用）----------------
# KSM handleKsmOrder 节点
KSM_STATUS_RESOLVED = 4          # 处理完成（关单）

# 智齿 save_ticket_reply ticket_status
ZHICHI_STATUS_WAITING = 2        # 等待回复（补料 C）
ZHICHI_STATUS_RESOLVED = 3       # 已解决（关单 / 不接管话术）

# ---------------- 编号前缀 ----------------
TICKET_NO_PREFIX = "FPY"         # 工单号 FPY+yyyyMMdd+seq
HUB_NO_PREFIX = "HUB"            # 研发单号
FAQ_NO_PREFIX = "FAQ"            # FAQ 编号

# ---------------- embedding ----------------
EMBEDDING_DIM = 1024             # bge-m3 维度（pgvector vector(1024)）

# ---------------- 向量召回 topN ----------------
INFO_DEDUP_TOPN = 8              # info-dedup 同产品线近120天 top8
HUB_DEDUP_TOPN = 5              # hub-dedup 历史 hub top5
INFO_DEDUP_RECALL_DAYS = 120     # info-dedup 候选时间窗（天）

# ---------------- 业务文本约束 ----------------
FAQ_TITLE_MAX = 20               # FAQ 标题字数
FAQ_CONTENT_MAX = 300            # FAQ 正文字数
MIN_DESC_LEN = 15                # 有效工单/提单描述最小字数（FR-02 / AS-01）
ASSISTANT_DEDUP_WINDOW_SEC = 300  # 提单防重复窗口（5 分钟）

# ---------------- ask agent 轮询 ----------------
AGENT_POLL_INTERVAL_SEC = 60     # 轮询间隔
AGENT_POLL_MAX_TIMES = 3         # 最多轮询次数（总 ~180s）
AGENT_ERR_TRANSFER = "100002"    # agent 转人工错误码 → 分支 C

# ---------------- 超时（秒）----------------
TIMEOUT_HTTP = 30                # 普通 HTTP
TIMEOUT_LLM = 60                 # LLM
TIMEOUT_KSM_SUBSCRIBE = 60       # KSM subscribeCallback 慢接口

# ---------------- 智齿不接管固定话术（走配置可覆盖）----------------
ZHICHI_NOT_TAKEOVER_REPLY = (
    "您好，当前工单存在非发票云问题，请通过 KSM 提单提交对应模块处理人；"
    "或者工单中有多个问题，请拆分后提。"
)

# ---------------- Linear 计划+发版日期 自动答复话术（固定模板，不脱敏）----------------
LINEAR_PLAN_REPLY_TPL = (
    "您好，您提的问题会在大约{date}可以修复，公有云环境自动发版、"
    "私有化客户需要申请私包发版，如有问题可以咨询发票云在线客服。"
)

# ---------------- 对客答复统一尾注（自动/人工答复客户均追加）----------------
CUSTOMER_REPLY_FOOTER = (
    "\n\n如有问题或者其他发票云问题可以咨询发票云客服："
    "https://tax.piaozone.com/sobot-web/home"
)
