"""KSM 工单客户端（业务调用重试上限 = settings.ksm_max_retry，默认 3）。

依据 KSM接口速查.md：三步鉴权(getAppToken→login→access_token)；业务成功判断 status==true；
access_token 作 query 参数。写操作(lock/handle/supply)经 dry_run 守卫。
注：早期「只调一次(retries=0)」仅测试期保险，生产可重试≤3 次。
"""
from __future__ import annotations

import time
from typing import Optional

from app.core.config import settings
from app.core.exceptions import IntegrationException
from app.integrations.base import HttpClient

_client: Optional["KsmClient"] = None
_LOCK_OPINION = "已受理，工单人员分析处理中"
_HANDLE_OPINION = "工单人员分析处理中"


class KsmClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            settings.ksm_base_url,
            integration="ksm",
            default_timeout=30.0,
            default_retries=settings.ksm_max_retry,  # 默认 3
        )
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    async def _access_token(self, force: bool = False) -> str:
        now = time.time()
        if not force and self._token and now < self._token_exp:
            return self._token
        # 步骤1 getAppToken
        app = await self.post("/ierp/api/getAppToken.do", json={
            "appId": settings.ksm_app_id,
            "appSecuret": settings.ksm_app_secret,  # 注意拼写(接口要求)
            "tenantid": settings.ksm_tenant_id,
            "accountId": settings.ksm_account_id,
            "language": "zh_CN",
        })
        app_token = (app.get("data") or {}).get("app_token")
        if not app_token:
            raise IntegrationException(f"getAppToken 失败: {app.get('message') or app}", integration="ksm")
        # 步骤2 login
        login = await self.post("/ierp/api/login.do", json={
            "user": settings.ksm_user,
            "apptoken": app_token,
            "tenantid": settings.ksm_tenant_id,
            "accountId": settings.ksm_account_id,
            "usertype": "UserName",
            "language": "zh_CN",
        })
        data = login.get("data") or {}
        token = data.get("access_token")
        if not token:
            raise IntegrationException(f"login 失败: {login.get('message') or login}", integration="ksm")
        self._token = token
        exp_ms = data.get("expire_time")
        self._token_exp = (exp_ms / 1000 - 1800) if exp_ms else (now + 1800)
        return token

    async def _biz(self, path: str, payload: dict, *, timeout: float = 30.0) -> dict:
        """业务 POST（access_token 作 query）。重试上限 = ksm_max_retry(默认 3)。"""
        token = await self._access_token()
        data = await self.post(f"{path}?access_token={token}", json=payload, timeout=timeout,
                               retries=self.default_retries)
        if data.get("status") is not True:
            raise IntegrationException(f"{path} 失败: {data.get('message')}", integration="ksm")
        return data

    async def subscribe_callback(self, notice_num: str, *, subscribe_num: Optional[str] = None,
                                 bill_id: Optional[str] = None) -> dict:
        """拉取工单全量（读操作）。subscribeNum 用推送值(缺省回退默认订阅)，带上 billId。返回 data。"""
        payload = {"noticeNum": notice_num, "subscribeNum": subscribe_num or "ksm_feedback_change"}
        if bill_id:
            payload["billId"] = bill_id
        data = await self._biz("/ierp/kapi/app/open/subscribeCallback", payload, timeout=60.0)
        return data.get("data", {})

    async def lock_order(self, *, bill_id: str, account: str, account_name: str, account_number: str) -> dict:
        payload = {"billId": bill_id, "account": account, "accountName": account_name,
                   "accountNumber": account_number, "dealOpinion": _LOCK_OPINION}
        if self.dry_run:
            return self.dry_run_stub("lockKsmOrder", payload)
        return await self._biz("/ierp/kapi/v2/kded/kded_wos/lockKsmOrder", payload)

    async def handle_order(self, *, bill_id: str, account: str, account_name: str, account_number: str,
                           linkman: str, email: str, mobile: str, product_id: str, version_id: str,
                           module_id: str, back_type: str, current_node_id: str, reply: str,
                           is_deal: bool = False) -> dict:
        # is_deal=True 结案模式（实际解决答复客户）：isDeal=2 + dealMethod/billType；普通处理 isDeal=""（只推进节点）
        payload = {"billId": bill_id, "account": account, "accountName": account_name,
                   "accountNumber": account_number, "linkman": linkman, "email": email, "mobile": mobile,
                   "productId": product_id, "versionId": version_id, "moduleId": module_id,
                   "backType": back_type, "isDeal": "2" if is_deal else "",
                   "dealOpinion": reply or _HANDLE_OPINION,
                   "handleInfo": {"currentNodeID": current_node_id}}
        if is_deal:
            payload["dealMethod"] = "指导解决"
            payload["billType"] = "服务咨询"
        if self.dry_run:
            return self.dry_run_stub("handleKsmOrder", payload)
        return await self._biz("/ierp/kapi/v2/kded/kded_wos/handleKsmOrder", payload)

    async def return_order(self, *, bill_id: str, account: str, account_name: str, account_number: str,
                           current_node_id: str, opercache_id: str, deal_opinion: str = "退回") -> dict:
        payload = {"billId": bill_id, "account": account, "accountName": account_name,
                   "accountNumber": account_number, "dealOpinion": deal_opinion,
                   "opercacheID": opercache_id, "currentNodeID": current_node_id}
        if self.dry_run:
            return self.dry_run_stub("returnKsmOrder", payload)
        return await self._biz("/ierp/kapi/v2/kded/kded_wos/returnKsmOrder", payload)

    async def supply_order(self, *, bill_id: str, account: str, account_name: str,
                           account_number: str, current_node_id: str, deal_opinion: str) -> dict:
        payload = {"billId": bill_id, "account": account, "accountNumber": account_number,
                   "accountName": account_name, "dealOpinion": deal_opinion[:4000], "currentNodeID": current_node_id}
        if self.dry_run:
            return self.dry_run_stub("supplyKsmOrder", payload)
        return await self._biz("/ierp/kapi/v2/kded/kded_wos/supplyKsmOrder", payload)


def get_ksm() -> "KsmClient":
    global _client
    if _client is None:
        _client = KsmClient()
    return _client
