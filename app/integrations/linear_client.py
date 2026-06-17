"""Linear GraphQL 客户端（★生产：issueCreate 责任人只能李志坚）。

鉴权：header Authorization=<api_token>（Linear 个人密钥，无 Bearer 前缀）。
写操作(issueCreate/issueUpdate/commentCreate)经 dry_run 守卫。
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.core.exceptions import IntegrationException
from app.integrations.base import HttpClient

_client: Optional["LinearClient"] = None
_GRAPHQL = "https://api.linear.app/graphql"


class LinearClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(integration="linear", default_timeout=30.0)
        self.token = settings.linear_api_token
        self.team_id = settings.linear_team_id
        # 按人名缓存 userId；预置配置里给定的 force_assignee→id（若已配 id）
        self._id_by_name: dict = {}
        if settings.linear_assignee_id and settings.linear_force_assignee:
            self._id_by_name[settings.linear_force_assignee] = settings.linear_assignee_id

    async def _gql(self, query: str, variables: Optional[dict] = None) -> dict:
        data = await self.post(
            _GRAPHQL,
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
        )
        if data.get("errors"):
            raise IntegrationException(f"Linear GraphQL 错误: {data['errors']}", integration="linear")
        return data["data"]

    async def resolve_assignee_id(self, name: Optional[str] = None) -> Optional[str]:
        """解析指定人名的 Linear userId（按人名缓存）。name 省略时用 force_assignee。"""
        name = (name or settings.linear_force_assignee or settings.linear_assignee_name or "").strip()
        if not name:
            return None
        if self._id_by_name.get(name):
            return self._id_by_name[name]
        data = await self._gql("{ users(first: 250) { nodes { id name displayName email } } }")
        for u in data["users"]["nodes"]:
            if name in (u.get("name") or "") or name in (u.get("displayName") or ""):
                self._id_by_name[name] = u["id"]
                return u["id"]
        return None

    async def create_issue(self, *, title: str, description: str) -> dict:
        """建 issue。配置了 linear_force_assignee → 统一指派给此人；留空 → 不强制指派(正常逻辑)。
        返回 {id, identifier, url}。dry_run 时不真建。"""
        force_name = (settings.linear_force_assignee or "").strip()
        if self.dry_run:
            stub = self.dry_run_stub("issueCreate", {"title": title, "team": self.team_id,
                                                     "assignee": force_name or "(正常逻辑/未指定)"})
            return {"id": "", "identifier": "DRYRUN", "url": "", **stub}
        inp: dict = {"teamId": self.team_id, "title": title, "description": description}
        if force_name:  # 配了人名 → 全部指派给配置人；未配 → 按正常逻辑(不带 assignee)
            assignee_id = await self.resolve_assignee_id(force_name)
            if assignee_id:
                inp["assigneeId"] = assignee_id
        q = ("mutation IssueCreate($input: IssueCreateInput!) {"
             " issueCreate(input: $input) { success issue { id identifier url } } }")
        data = await self._gql(q, {"input": inp})
        res = data["issueCreate"]
        if not res.get("success"):
            raise IntegrationException("issueCreate 未成功", integration="linear")
        return res["issue"]

    async def update_issue(self, issue_id: str, *, assignee_id: Optional[str] = None, state_id: Optional[str] = None) -> dict:
        if self.dry_run:
            return self.dry_run_stub("issueUpdate", {"issue_id": issue_id})
        inp: dict = {}
        if assignee_id:
            inp["assigneeId"] = assignee_id
        if state_id:
            inp["stateId"] = state_id
        q = ("mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {"
             " issueUpdate(id: $id, input: $input) { success } }")
        return await self._gql(q, {"id": issue_id, "input": inp})

    async def get_issue_state(self, issue_id: str) -> Optional[dict]:
        """拉取 issue 当前状态：{name, type}（用于主动同步 Linear→本系统）。dry_run 跳过。"""
        if self.dry_run:
            return None
        data = await self._gql("query($id: String!){ issue(id:$id){ id state { name type } } }", {"id": str(issue_id)})
        iss = data.get("issue") or {}
        return iss.get("state") or None

    async def create_comment(self, issue_id: str, body: str) -> dict:
        if self.dry_run:
            return self.dry_run_stub("commentCreate", {"issue_id": issue_id, "body": body[:200]})
        q = ("mutation CommentCreate($input: CommentCreateInput!) {"
             " commentCreate(input: $input) { success } }")
        return await self._gql(q, {"input": {"issueId": issue_id, "body": body}})


def get_linear() -> "LinearClient":
    global _client
    if _client is None:
        _client = LinearClient()
    return _client
