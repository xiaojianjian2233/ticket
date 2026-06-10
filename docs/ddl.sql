-- ============================================================
-- ticket-hub 完整建表 SQL (PostgreSQL 16 + pgvector)
-- 编制日期: 2026-06-10
-- 规范: 三范式为主 + 高频字段合理冗余; 统一审计5字段; 全表 t_ 前缀
-- 说明: 枚举用 varchar+注释(线上可加值); 时间 timestamptz; 主键 BIGSERIAL
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector (FAQ/hub 向量检索)

-- ============================================================
-- 表1: t_ticket_info 工单主表
-- ============================================================
CREATE TABLE t_ticket_info (
    id                      BIGSERIAL PRIMARY KEY,
    ticket_no               varchar(32)  NOT NULL,
    source                  varchar(16)  NOT NULL,            -- ksm/zhichi/assistant
    source_id               varchar(64)  NOT NULL,            -- 来源工单编号(幂等/退回键)
    source_bill_no          varchar(64),
    assistant_submitter_uid varchar(64),                      -- assistant提单人飞书uid
    title                   varchar(512) NOT NULL,
    description             text         NOT NULL,            -- 问题描述(高频)
    customer_company        varchar(255),                     -- 客户公司(冗余,列表显示)
    has_attachment          boolean      NOT NULL DEFAULT false,
    -- 流转
    routable                boolean,
    route_action            varchar(32),                      -- 可流转/不接管-多问题/不接管-不可流转
    route_reason            varchar(512),
    is_returned             boolean      NOT NULL DEFAULT false,
    return_count            int          NOT NULL DEFAULT 0,
    -- 打标(冗余高频)
    ai_product_tag          varchar(64),
    ai_func_module          varchar(128),
    ai_dev_owner            varchar(64),
    dev_owner_missing       boolean      NOT NULL DEFAULT false,
    -- 去重
    is_duplicate            boolean      NOT NULL DEFAULT false,
    reused_from_ticket_id   bigint,                           -- 短路复用源(自关联)
    -- 答复
    answer_branch           varchar(4),                       -- A/B/C/D
    transfer_result         varchar(16),                      -- NO_ACTION/TRANSFER
    final_reply             text,                             -- 最终答复(humanize+脱敏后)
    rd_hub_id               bigint,                           -- 研发单id
    rd_status               varchar(20),                      -- 研发状态镜像(Linear回调)
    rd_handler              varchar(64),                      -- 研发处理人镜像
    rd_status_note          text,                             -- 研发说明镜像
    -- 派单
    dispatch_assignee       varchar(64),
    dispatched_at           timestamptz,
    -- 回写
    writeback_status        varchar(16),                      -- pending/success/failed
    writeback_retry         int          NOT NULL DEFAULT 0,
    -- SLA-1 人工 + 关闭
    sla_start_at            timestamptz,
    sla_due_at              timestamptz,
    sla_state               varchar(16)  NOT NULL DEFAULT 'normal',
    sla_notified_marks      jsonb,                            -- 已通报时点(运行时去重)
    resolved_at             timestamptz,                      -- 处理完成(观察期起点)
    closed_at               timestamptz,
    status                  varchar(20)  NOT NULL DEFAULT 'pending',
    -- 审计
    is_deleted              boolean      NOT NULL DEFAULT false,
    created_at              timestamptz  NOT NULL DEFAULT now(),
    updated_at              timestamptz  NOT NULL DEFAULT now(),
    created_by              varchar(64),
    updated_by              varchar(64)
);
CREATE UNIQUE INDEX uk_ticket_no        ON t_ticket_info (ticket_no);
CREATE UNIQUE INDEX uk_source_sourceid  ON t_ticket_info (source, source_id);
CREATE INDEX idx_ti_status              ON t_ticket_info (status, is_deleted);
CREATE INDEX idx_ti_dev_owner_sla       ON t_ticket_info (ai_dev_owner, sla_state, sla_due_at);
CREATE INDEX idx_ti_resolved            ON t_ticket_info (resolved_at) WHERE status NOT IN ('closed','returned');
CREATE INDEX idx_ti_product_created     ON t_ticket_info (ai_product_tag, created_at);
CREATE INDEX idx_ti_rd_hub              ON t_ticket_info (rd_hub_id);

-- ============================================================
-- 表2: t_ticket_detail 工单详情(1:1)
-- ============================================================
CREATE TABLE t_ticket_detail (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         bigint       NOT NULL,
    customer_contact  varchar(64),
    customer_mobile   varchar(32),
    customer_email    varchar(128),
    customer_tel      varchar(32),
    customer_tax_no   varchar(64),
    customer_no       varchar(64),
    product_name_raw  varchar(128),
    module_raw        varchar(128),
    raw_json          jsonb,                                  -- 原始报文(留底,不建GIN)
    ai_reply          text,
    full_reply        text,
    humanized_reply   text,
    supply_note       text,
    writeback_error   text,
    is_deleted        boolean      NOT NULL DEFAULT false,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    created_by        varchar(64),
    updated_by        varchar(64)
);
CREATE UNIQUE INDEX uk_td_ticket_id ON t_ticket_detail (ticket_id);

-- ============================================================
-- 表3: t_ticket_tag 打标历史(1:N)
-- ============================================================
CREATE TABLE t_ticket_tag (
    id                BIGSERIAL PRIMARY KEY,
    ticket_id         bigint       NOT NULL,
    product_tag       varchar(64),
    func_module       varchar(128),
    dev_owner         varchar(64),
    dev_owner_missing boolean      NOT NULL DEFAULT false,
    confidence        numeric(4,3),
    tag_source        varchar(16)  NOT NULL DEFAULT 'llm',    -- llm/manual/fallback
    model_used        varchar(32),
    is_current        boolean      NOT NULL DEFAULT true,
    revised_by        varchar(64),
    evidence          text,
    is_deleted        boolean      NOT NULL DEFAULT false,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    created_by        varchar(64),
    updated_by        varchar(64)
);
CREATE INDEX idx_tt_ticket_current ON t_ticket_tag (ticket_id, is_current);
CREATE INDEX idx_tt_ticket_created ON t_ticket_tag (ticket_id, created_at);

-- ============================================================
-- 表4: t_ticket_merge 合并/去重记录(1:N)
-- ============================================================
CREATE TABLE t_ticket_merge (
    id               BIGSERIAL PRIMARY KEY,
    ticket_id        bigint       NOT NULL,
    merge_type       varchar(16)  NOT NULL,                   -- dedup_reuse/dedup_marked/hub_merge
    target_ticket_id bigint,
    target_hub_id    bigint,
    similarity       numeric(4,3),
    threshold        numeric(4,3),
    llm_confirmed    boolean,
    evidence         text,
    is_deleted       boolean      NOT NULL DEFAULT false,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    created_by       varchar(64),
    updated_by       varchar(64)
);
CREATE INDEX idx_tm_ticket        ON t_ticket_merge (ticket_id);
CREATE INDEX idx_tm_target_ticket ON t_ticket_merge (target_ticket_id);
CREATE INDEX idx_tm_target_hub    ON t_ticket_merge (target_hub_id);
CREATE INDEX idx_tm_type          ON t_ticket_merge (merge_type);

-- ============================================================
-- 表5: t_ticket_hub 研发单(N info : 1 hub)
-- ============================================================
CREATE TABLE t_ticket_hub (
    id                 BIGSERIAL PRIMARY KEY,
    hub_no             varchar(32)  NOT NULL,
    title              varchar(512) NOT NULL,
    problem_summary    text,
    full_reply         text,
    product_tag        varchar(64),
    func_module        varchar(128),
    dev_owner          varchar(64),
    embedding          vector(1024),                          -- hub-dedup 召回
    linear_issue_id    varchar(64),
    linear_url         varchar(512),
    linear_sync_status varchar(16)  NOT NULL DEFAULT 'pending',
    linear_sync_retry  int          NOT NULL DEFAULT 0,
    rd_handler         varchar(64),                           -- Linear回调:处理人
    rd_status_note     text,                                  -- Linear回调:说明
    rd_callback_at     timestamptz,
    rd_sla_start_at    timestamptz,                           -- =hub.created_at
    rd_sla_due_at      timestamptz,
    rd_sla_state       varchar(16)  NOT NULL DEFAULT 'normal',
    rd_resolved_at     timestamptz,                           -- 回调resolved时填,SLA-2停表
    status             varchar(20)  NOT NULL DEFAULT 'in_progress', -- in_progress/resolved/closed
    is_deleted         boolean      NOT NULL DEFAULT false,
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now(),
    created_by         varchar(64),
    updated_by         varchar(64)
);
CREATE UNIQUE INDEX uk_hub_no          ON t_ticket_hub (hub_no);
CREATE INDEX idx_th_dev_owner_sla      ON t_ticket_hub (dev_owner, rd_sla_state, rd_sla_due_at);
CREATE INDEX idx_th_product            ON t_ticket_hub (product_tag);
CREATE INDEX idx_th_linear_status      ON t_ticket_hub (linear_sync_status);
CREATE INDEX ivf_th_embedding          ON t_ticket_hub USING ivfflat (embedding vector_cosine_ops);

-- ============================================================
-- 表6: t_faq FAQ检索主库
-- ============================================================
CREATE TABLE t_faq (
    id              BIGSERIAL PRIMARY KEY,
    faq_no          varchar(32)  NOT NULL,
    title           varchar(64)  NOT NULL,                    -- 应用层限≤20
    content         varchar(512) NOT NULL,                    -- 应用层限≤300
    product_tag     varchar(64)  NOT NULL,
    source_ticket_id bigint,
    embedding       vector(1024),                             -- bge-m3
    review_status   varchar(16)  NOT NULL DEFAULT 'pending_review',
    review_reason   text,
    reviewed_at     timestamptz,
    hit_count       int          NOT NULL DEFAULT 0,
    is_deleted      boolean      NOT NULL DEFAULT false,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now(),
    created_by      varchar(64),
    updated_by      varchar(64)
);
CREATE UNIQUE INDEX uk_faq_no        ON t_faq (faq_no);
CREATE INDEX idx_faq_product_review  ON t_faq (product_tag, review_status);
CREATE INDEX ivf_faq_embedding       ON t_faq USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_faq_source_ticket   ON t_faq (source_ticket_id);

-- ============================================================
-- 表7: t_faq_review FAQ审核记录(1:N)
-- ============================================================
CREATE TABLE t_faq_review (
    id            BIGSERIAL PRIMARY KEY,
    faq_id        bigint       NOT NULL,
    result        varchar(16)  NOT NULL,                      -- approved/rejected
    dim_sensitive boolean,
    dim_factual   boolean,
    dim_internal  boolean,
    dim_quality   boolean,
    reject_dims   varchar(128),
    reason        text,
    model_used    varchar(32)  NOT NULL DEFAULT 'deepseek',
    notified      boolean      NOT NULL DEFAULT false,
    is_deleted    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_by    varchar(64)
);
CREATE INDEX idx_fr_faq    ON t_faq_review (faq_id);
CREATE INDEX idx_fr_result ON t_faq_review (result);

-- ============================================================
-- 表8: t_sla_log SLA超时记录(双SLA)
-- ============================================================
CREATE TABLE t_sla_log (
    id            BIGSERIAL PRIMARY KEY,
    sla_type      varchar(8)   NOT NULL,                      -- manual/rd
    ref_type      varchar(8)   NOT NULL,                      -- info/hub
    ref_id        bigint       NOT NULL,
    owner         varchar(64),
    notify_date   date         NOT NULL,
    notify_mark   varchar(16)  NOT NULL,                      -- 2026-06-10-08:00
    overdue_hours numeric(8,2),
    notified      boolean      NOT NULL DEFAULT false,
    is_deleted    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_by    varchar(64)
);
CREATE UNIQUE INDEX uk_sla_ref_mark ON t_sla_log (ref_type, ref_id, notify_mark);
CREATE INDEX idx_sla_owner_date     ON t_sla_log (owner, notify_date);
CREATE INDEX idx_sla_type_date      ON t_sla_log (sla_type, notify_date);

-- ============================================================
-- 表9: t_integration_log 第三方接口日志(高写入,120天)
-- ============================================================
CREATE TABLE t_integration_log (
    id               BIGSERIAL PRIMARY KEY,
    trace_id         varchar(64)  NOT NULL,
    ticket_id        bigint,
    integration      varchar(32)  NOT NULL,                   -- ksm/zhichi/agent/...
    endpoint         varchar(128) NOT NULL,
    request_summary  text,                                    -- 脱敏+截断
    response_summary text,
    http_status      int,
    biz_success      boolean,
    error_msg        varchar(512),
    duration_ms      int,
    retry_seq        int          NOT NULL DEFAULT 0,
    is_deleted       boolean      NOT NULL DEFAULT false,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    created_by       varchar(64),
    updated_by       varchar(64)
);
CREATE INDEX idx_il_trace            ON t_integration_log (trace_id);
CREATE INDEX idx_il_ticket           ON t_integration_log (ticket_id);
CREATE INDEX idx_il_integration_date ON t_integration_log (integration, created_at);
CREATE INDEX idx_il_fail             ON t_integration_log (biz_success, created_at) WHERE biz_success = false;

-- ============================================================
-- 表10: t_users 飞书SSO用户
-- ============================================================
CREATE TABLE t_users (
    id            BIGSERIAL PRIMARY KEY,
    feishu_uid    varchar(64),
    name          varchar(64)  NOT NULL,
    email         varchar(128),
    mobile        varchar(32),
    avatar_url    varchar(512),
    employee_no   varchar(32),
    role          varchar(16)  NOT NULL DEFAULT 'visitor',    -- admin/handler/visitor
    is_active     boolean      NOT NULL DEFAULT true,
    last_login_at timestamptz,
    is_deleted    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_by    varchar(64)
);
CREATE UNIQUE INDEX uk_users_feishu_uid ON t_users (feishu_uid);
CREATE INDEX idx_users_name             ON t_users (name);
CREATE INDEX idx_users_role             ON t_users (role, is_active);

-- ============================================================
-- 表11: t_module_owner 产品线/模块/责任人映射
-- ============================================================
CREATE TABLE t_module_owner (
    id            BIGSERIAL PRIMARY KEY,
    product_tag   varchar(64)  NOT NULL,
    func_module   varchar(128) NOT NULL,
    trigger_words text,                                       -- '|' 分隔
    dev_owner     varchar(64),
    dev_owner_uid varchar(64),
    is_active     boolean      NOT NULL DEFAULT true,
    sort_order    int          NOT NULL DEFAULT 0,
    is_deleted    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_by    varchar(64)
);
CREATE UNIQUE INDEX uk_mo_product_module ON t_module_owner (product_tag, func_module);
CREATE INDEX idx_mo_module               ON t_module_owner (func_module);
CREATE INDEX idx_mo_active               ON t_module_owner (is_active);

-- ============================================================
-- 表12: t_operation_log 配置审计(长期)
-- ============================================================
CREATE TABLE t_operation_log (
    id            BIGSERIAL PRIMARY KEY,
    operator_uid  varchar(64)  NOT NULL,
    operator_name varchar(64),
    target_type   varchar(32)  NOT NULL,                      -- skill_md/dispatch_assignee/...
    target_id     varchar(64),
    action        varchar(16)  NOT NULL,                      -- create/update/delete/rollback
    before_value  jsonb,
    after_value   jsonb,
    remark        varchar(512),
    is_deleted    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    created_by    varchar(64),
    updated_by    varchar(64)
);
CREATE INDEX idx_ol_operator ON t_operation_log (operator_uid, created_at);
CREATE INDEX idx_ol_target   ON t_operation_log (target_type, target_id);

-- ============================================================
-- 表13: t_assistant_log 智能助手记录(90天)
-- ============================================================
CREATE TABLE t_assistant_log (
    id             BIGSERIAL PRIMARY KEY,
    user_uid       varchar(64)  NOT NULL,
    user_role      varchar(16),
    session_id     varchar(64),
    nl_query       text         NOT NULL,
    generated_sql  text,
    sql_guard_pass boolean,
    result_rows    int,
    pii_masked     boolean,
    op_type        varchar(16)  NOT NULL DEFAULT 'query',     -- query/submit
    error_msg      varchar(512),
    is_deleted     boolean      NOT NULL DEFAULT false,
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    created_by     varchar(64),
    updated_by     varchar(64)
);
CREATE INDEX idx_al_user    ON t_assistant_log (user_uid, created_at);
CREATE INDEX idx_al_session ON t_assistant_log (session_id);
CREATE INDEX idx_al_optype  ON t_assistant_log (op_type);

-- ============================================================
-- 外键约束(可选,内网/性能权衡; 默认注释,用应用层保证)
-- ============================================================
-- ALTER TABLE t_ticket_detail ADD CONSTRAINT fk_td_ticket FOREIGN KEY (ticket_id) REFERENCES t_ticket_info(id);
-- ALTER TABLE t_ticket_info   ADD CONSTRAINT fk_ti_hub    FOREIGN KEY (rd_hub_id)  REFERENCES t_ticket_hub(id);
-- ALTER TABLE t_faq_review    ADD CONSTRAINT fk_fr_faq    FOREIGN KEY (faq_id)     REFERENCES t_faq(id);
-- (其余关联用应用层维护,避免外键锁影响高并发写入)

-- ============================================================
-- 表14: t_ticket_org 来源原始工单字段(1:1宽表)
-- ============================================================
CREATE TABLE t_ticket_org (
    id                  BIGSERIAL PRIMARY KEY,
    ticket_id           bigint       NOT NULL,
    source              varchar(16)  NOT NULL,                -- ksm/zhichi
    org_bill_id         varchar(64),                          -- KSM billId / 智齿 ticketid
    org_bill_no         varchar(64),                          -- KSM billNumber / 智齿 ticket_code
    org_title           varchar(512),
    org_content         text,                                 -- KSM problem / 智齿 ticket_content
    org_status          varchar(32),
    org_urgency         varchar(16),
    org_create_time     timestamptz,
    org_update_time     timestamptz,
    org_customer_name   varchar(255),
    org_linkman         varchar(64),
    org_mobile          varchar(32),
    org_email           varchar(128),
    org_product_name    varchar(128),
    org_module_name     varchar(128),
    org_assign_user     varchar(64),
    -- KSM 特有
    ksm_feedback_type   varchar(16),
    ksm_product_id      varchar(64),                          -- 回写用
    ksm_module_id       varchar(64),
    ksm_version_id      varchar(64),
    ksm_node_id         varchar(64),
    ksm_node_name       varchar(64),
    ksm_customer_no     varchar(64),
    ksm_service_level   varchar(32),
    ksm_sponsor         varchar(64),
    ksm_main_product    varchar(128),
    -- 智齿 特有
    zhichi_deal_agent   varchar(64),
    zhichi_erp          varchar(64),
    zhichi_project_name varchar(255),
    -- 嵌套 jsonb
    ksm_handle_steps    jsonb,                                -- handleSteps[]
    ksm_evaluate_info   jsonb,                                -- evaluateInfo
    zhichi_extend_fields jsonb,                               -- extend_fields_list[]
    -- 审计
    is_deleted          boolean      NOT NULL DEFAULT false,
    created_at          timestamptz  NOT NULL DEFAULT now(),
    updated_at          timestamptz  NOT NULL DEFAULT now(),
    created_by          varchar(64),
    updated_by          varchar(64)
);
CREATE UNIQUE INDEX uk_org_ticket_id ON t_ticket_org (ticket_id);
CREATE INDEX idx_org_bill_id         ON t_ticket_org (source, org_bill_id);
