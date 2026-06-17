"""后端集成冒烟测试（pytest）：对部署后端 + 共享 PG 断言。
运行: BASE_URL=<后端地址> PG_DSN='host=<host> port=5432 user=postgres password=<DB_PASSWORD> dbname=ticket_hub' pytest tests/api -v
依赖: pip install pytest requests psycopg[binary]
"""
import os, time, uuid, requests, psycopg, pytest

BASE = os.getenv("BASE_URL", "http://localhost:8000")
PG = os.getenv("PG_DSN", "host=localhost port=5432 user=postgres password= dbname=ticket_hub")


def test_health_and_login_url():
    r = requests.get(f"{BASE}/api/v1/auth/feishu/login", timeout=10).json()
    assert r["code"] == 0 and "authorize_url" in r["data"]          # 正常: 登录URL
    assert "/fpy/" in r["data"]["authorize_url"]                    # redirect 正确


def test_webhook_idempotent_and_pipeline():
    tid = "PYT" + uuid.uuid4().hex[:10]
    payload = {"ticketid": tid, "ticket_code": "ZC-PYT", "ticket_title": "发票开票测试",
               "ticket_content": "星瀚开票提示未找到流水号请协助处理该发票问题描述足够长以通过流转判断",
               "ticket_status": 1, "ticket_level": 2, "create_time": "2026-06-11 10:00:00", "enterprise_name": "PYT",
               "extend_fields_list": [{"field_name": "产品分类", "field_type": "6", "field_text": "星瀚-开票"}]}
    r = requests.post(f"{BASE}/webhook/zhichi", json=payload, timeout=10).json()
    assert r["code"] == 0                                           # 入站入队
    # 轮询 DB 等流水线创建工单(最多120s)
    with psycopg.connect(PG, connect_timeout=10) as c:
        for _ in range(40):
            row = c.execute("SELECT status, ai_product_tag, answer_branch FROM t_ticket_info WHERE source_id=%s", (tid,)).fetchone()
            if row:
                break
            time.sleep(3)
        assert row is not None, "工单未创建"                          # 建单
        # 再等流水线打标(产品线非空)
        for _ in range(40):
            row = c.execute("SELECT ai_product_tag, answer_branch, status FROM t_ticket_info WHERE source_id=%s", (tid,)).fetchone()
            if row[0]:
                break
            time.sleep(3)
        assert row[0] == "星瀚-开票"                                  # 打标正确(LLM)


def test_webhook_returned_on_duplicate():
    """同编号二次推送 → 退回(return_count+1)"""
    tid = "PYTDUP" + uuid.uuid4().hex[:8]
    p = {"ticketid": tid, "ticket_title": "重复测试", "ticket_content": "星瀚开票问题描述足够长以入库测试退回逻辑",
         "ticket_status": 1, "extend_fields_list": [{"field_name": "产品分类", "field_type": "6", "field_text": "星瀚-开票"}]}
    requests.post(f"{BASE}/webhook/zhichi", json=p, timeout=10)
    time.sleep(8)
    requests.post(f"{BASE}/webhook/zhichi", json=p, timeout=10)     # 二次推送
    time.sleep(8)
    with psycopg.connect(PG, connect_timeout=10) as c:
        for _ in range(20):
            row = c.execute("SELECT return_count, is_returned FROM t_ticket_info WHERE source_id=%s", (tid,)).fetchone()
            if row and row[0] and row[0] >= 1:
                break
            time.sleep(3)
        assert row and row[1] is True                               # 退回标记
