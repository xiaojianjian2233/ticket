"""v2.1 流水线流程测试（纯本地，mock 外部 + DB）：逐分支跑 run_pipeline，断言终态、无异常。
运行: pytest tests/api/test_pipeline_flow.py -v
"""
import asyncio
from types import SimpleNamespace

import pytest

import app.pipeline.runner as runner
from app.pipeline import writeback
from app.common.enums import Source, TicketStatus
from app.common.constants import CUSTOMER_REPLY_FOOTER
from app.core.config import settings


# ---------- 假 DB ----------
class FakeResult:
    def scalar_one(self):
        return 1

    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class FakeSession:
    def __init__(self, info):
        self._info = info
        self.added = []

    async def get(self, model, _id):
        return self._info

    async def flush(self):
        pass

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, *a, **k):
        return FakeResult()

    async def commit(self):
        pass


def _ai(ret=None):
    async def f(*a, **k):
        return ret if ret is not None else {}
    return f


def _mk_info(**over):
    base = dict(id=1, ticket_no="T1", source=Source.KSM.value, source_id="S1",
                title="开票问题", description="星瀚开票未找到流水号，请协助处理，问题描述足够长以通过流转判断。",
                is_returned=False, is_deleted=False, has_attachment=False,
                ai_product_tag=None, ai_func_module=None, ai_dev_owner=None, dev_owner_missing=False,
                answer_branch=None, transfer_result=None, final_reply=None, is_duplicate=False,
                customer_company="某公司", rd_hub_id=None, status="pending")
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def patched(monkeypatch):
    """patch run_step + 集成 getter + ticket_repo + _info_dedup。测试通过 ENV 控制 answer-router 分支。"""
    ENV = {"branch": "D", "routable": True, "dedup_reply": None}

    async def fake_run_step(session, ctx, name, fn, payload, *, step_no=None):
        if name == "ticket-routable":
            return {"status": "ok", "fields": {"routable": ENV["routable"], "route_action": "可流转" if ENV["routable"] else "不接管-不可流转", "route_reason": "x"}}
        if name == "ticket-tagging":
            return {"status": "ok", "fields": {"ai_product_tag": "开票-星瀚", "ai_func_module": "开票"}}
        if name == "agent-answer":
            return {"status": "ok", "fields": {"answer": "这是 agent 答复内容", "transfer_result": "NO_ACTION"}}
        if name == "answer-router":
            return {"status": "ok", "fields": {"answer_branch": ENV["branch"]}}
        if name == "reply-humanize":
            return {"status": "ok", "fields": {"humanized_reply": "润色后的答复"}}
        if name == "hub-dedup":
            return {"status": "ok", "fields": {"is_dup": False}}
        return {"status": "ok", "fields": {}}

    async def fake_update_info(session, info, **kw):
        for k, v in kw.items():
            setattr(info, k, v)

    async def fake_update_detail(session, info_id, **kw):
        pass

    async def fake_get_detail(session, info_id):
        return SimpleNamespace(product_name_raw="", module_raw="", customer_contact="联系人",
                               customer_mobile="138", customer_tel="", customer_email="a@b.c",
                               customer_tax_no="TAX", customer_no="租户")

    async def fake_info_dedup(session, ctx, info, desc, product):
        return ENV["dedup_reply"]

    monkeypatch.setattr(runner, "run_step", fake_run_step)
    monkeypatch.setattr(runner, "_info_dedup", fake_info_dedup)
    monkeypatch.setattr(runner.ticket_repo, "update_info", fake_update_info)
    monkeypatch.setattr(runner.ticket_repo, "update_detail", fake_update_detail)
    monkeypatch.setattr(runner.ticket_repo, "get_detail", fake_get_detail)
    monkeypatch.setattr(runner.ticket_repo, "lookup_dev_owner", _ai("张三"))
    monkeypatch.setattr(runner.ticket_repo, "module_candidates", _ai([]))
    monkeypatch.setattr(runner.ticket_repo, "hub_candidates", _ai([]))
    monkeypatch.setattr(runner, "get_ksm", lambda: SimpleNamespace(lock_order=_ai({}), handle_order=_ai({}), unlock_order=_ai({})))
    monkeypatch.setattr(runner, "get_linear", lambda: SimpleNamespace(create_issue=_ai({"id": "i1", "url": "u1", "dry_run": True})))
    monkeypatch.setattr(runner, "get_siliconflow", lambda: SimpleNamespace(embed_one=_ai([0.1, 0.2, 0.3])))
    monkeypatch.setattr(runner, "get_feishu", lambda: SimpleNamespace(send_text=_ai({})))
    monkeypatch.setattr(writeback, "get_feishu", lambda: SimpleNamespace(send_text=_ai({})))
    # writeback_not_takeover(KSM) 走真实(仅日志)，无需 patch
    return ENV


def _run(info):
    sess = FakeSession(info)
    asyncio.run(runner.run_pipeline(sess, info.id, "trace-test"))
    return sess


# ---------- 分支用例 ----------
def test_ksm_d_normal_done(patched):
    patched["branch"] = "D"
    info = _mk_info()
    _run(info)
    assert info.status == TicketStatus.DONE.value


def test_ksm_a_bug_pending_rd(patched):
    patched["branch"] = "A"
    info = _mk_info()
    sess = _run(info)
    assert info.status == TicketStatus.PENDING_RD.value
    assert any(type(o).__name__ == "TicketHub" for o in sess.added)   # 新建了 hub


def test_ksm_b_requirement_pending_rd(patched):
    patched["branch"] = "B"
    info = _mk_info()
    sess = _run(info)
    assert info.status == TicketStatus.PENDING_RD.value          # B 同 A 进 Linear
    assert any(type(o).__name__ == "TicketHub" for o in sess.added)


def test_ksm_c_supplement(patched):
    patched["branch"] = "C"
    info = _mk_info()
    _run(info)
    assert info.status == TicketStatus.SUPPLEMENT.value          # C 退回客户=补充资料


def test_ksm_not_takeover_returned(patched):
    patched["routable"] = False
    info = _mk_info()
    _run(info)
    assert info.status == TicketStatus.RETURNED.value


def test_ksm_dedup_hit_done(patched):
    patched["dedup_reply"] = "复用历史答复"
    info = _mk_info()
    _run(info)
    assert info.status == TicketStatus.DONE.value
    assert info.is_duplicate is True


def test_zhichi_miss_pending_manual(patched):
    info = _mk_info(source=Source.ZHICHI.value)
    _run(info)
    assert info.status == TicketStatus.PENDING_MANUAL.value      # 智齿未命中→转人工


def test_zhichi_dedup_hit_done(patched):
    patched["dedup_reply"] = "智齿复用答复"
    info = _mk_info(source=Source.ZHICHI.value)
    _run(info)
    assert info.status == TicketStatus.DONE.value


def test_returned_ticket_direct_manual(patched):
    info = _mk_info(is_returned=True)
    _run(info)
    assert info.status == TicketStatus.PENDING_MANUAL.value      # 退回单不跑流水线


# ---------- footer 直测 ----------
def test_writeback_close_appends_footer_ksm(monkeypatch):
    captured = {}

    async def fake_org(session, info_id):
        return None
    monkeypatch.setattr(writeback, "_org", fake_org)

    def fake_ksm():
        async def handle_order(*, reply, **k):
            captured["reply"] = reply
            return {"ok": True}
        return SimpleNamespace(handle_order=handle_order)
    monkeypatch.setattr(writeback, "get_ksm", fake_ksm)
    info = _mk_info(source=Source.KSM.value)
    asyncio.run(writeback.writeback_close(FakeSession(info), info, "您的问题已处理完成"))
    assert captured["reply"].endswith("https://tax.piaozone.com/sobot-web/home")   # handleKsmOrder reply 带尾注
    assert "发票云客服" in captured["reply"]


def test_writeback_close_appends_footer_zhichi(monkeypatch):
    monkeypatch.setattr(settings, "writeback_dry_run", True)
    captured = {}

    def fake_zhichi():
        async def close_with_reply(*, ticketid, title, content, reply):
            captured["reply"] = reply
            return {"ok": True}
        return SimpleNamespace(close_with_reply=close_with_reply)
    monkeypatch.setattr(writeback, "get_zhichi", fake_zhichi)
    info = _mk_info(source=Source.ZHICHI.value)
    asyncio.run(writeback.writeback_close(FakeSession(info), info, "已解决"))
    assert captured["reply"].endswith(CUSTOMER_REPLY_FOOTER.rstrip("\n").split("：")[0] + "：https://tax.piaozone.com/sobot-web/home")
