"""全局配置：pydantic-settings 读 .env。密钥一律走环境变量。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # DB
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ticket_hub"

    # JWT
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 28800

    # webhook
    webhook_access_token: str = "change-me"

    # 飞书
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_sso_redirect_uri: str = ""
    feishu_bot_webhooks: str = ""
    feishu_bot_webhook_sla_manual: str = ""
    feishu_bot_webhook_sla_rd: str = ""
    feishu_bot_webhook_system: str = ""

    # KSM
    ksm_base_url: str = "https://ierp.kingdee.com"
    ksm_app_id: str = ""
    ksm_app_secret: str = ""
    ksm_tenant_id: str = ""
    ksm_account_id: str = ""          # 数据中心账号id（鉴权用）
    ksm_user: str = ""                # 登录用户名（三步鉴权用）
    ksm_handler_name: str = "李志坚"    # KSM 处理人姓名（lock/handle/supply 的 account/accountName）
    ksm_handler_number: str = ""      # KSM 处理人工号（accountNumber，飞书员工搜索接口获取）

    # 智齿
    zhichi_base_url: str = "https://www.soboten.com"
    zhichi_appid: str = ""
    zhichi_app_key: str = ""

    # ask agent（本期用现有旧单步契约；四步 open-api-channel 凭证缺，预留字段）
    agent_url: str = ""          # 单步: POST {agent_url} {question, cid}
    agent_cid: str = "test"
    agent_token: str = ""
    agent_base_url: str = ""      # 四步(预留)
    agent_appid: str = ""
    agent_app_key: str = ""

    # 硅基流动
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"

    # LLM（Claude 网关 + DeepSeek 均 OpenAI 兼容 /v1/chat/completions）
    claude_api_key: str = ""
    claude_base_url: str = ""
    claude_model: str = "claude-sonnet-4-6"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Linear（生产：责任人只能李志坚）
    linear_api_token: str = ""
    linear_team: str = "CNPRD"
    linear_team_id: str = ""              # team UUID
    linear_assignee_name: str = "李志坚"   # ★生产红线：推 ticket 责任人固定此人
    linear_assignee_id: str = ""          # 其 Linear userId（运行时解析或配置）
    # 转 Linear 责任人统一指派：配了人名 → 所有 issue 都指派给此人；留空 → 按正常逻辑（不强制指派）
    linear_force_assignee: str = "李志坚"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "ticket-hub"
    minio_public_base: str = "https://fpy-jfsv.kingdee.com:8864"

    # 业务阈值
    faq_hit_threshold: float = 0.8
    info_dedup_threshold: float = 0.85
    hub_dedup_threshold: float = 0.80
    faq_dedup_threshold: float = 0.85
    sla_manual_hours: int = 48
    # 去AI化：列入的 skill 跳过 LLM、返回规则默认值（逗号分隔，默认空=全部走 AI）
    skill_no_ai: str = ""
    sla_rd_hours: int = 48
    observe_days: int = 14
    queue_backlog_n: int = 100
    queue_oldest_m: int = 30
    default_dev_owner: str = "待人工分配"

    # 安全/部署
    admin_names: str = "李志坚"           # 登录自动授予 admin 的姓名(逗号分隔), 解决首个管理员引导
    writeback_dry_run: bool = True        # ★对外写(KSM/智齿/Linear/飞书)默认只组装不真发
    ksm_max_retry: int = 3                # KSM 重试上限(「只调一次」仅测试期保险，生产可重试≤3)
    cors_allow_origins: str = ""          # 逗号分隔；前端 http://dl.piaozone.com:18025
    global_max_retry: int = 3             # 其它接口默认重试上限


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
