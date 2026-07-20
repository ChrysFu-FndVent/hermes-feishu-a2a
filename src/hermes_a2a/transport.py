from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings
from .models import AgentRecord, TaskSpec


class AgentTransport(Protocol):
    async def dispatch(self, agent: AgentRecord, task: TaskSpec, run_id: str) -> str: ...


@dataclass
class TokenCache:
    token: str = ""
    expires_at: float = 0


class FeishuClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=20)
        self._token = TokenCache()

    async def close(self) -> None:
        await self.client.aclose()

    async def tenant_token(self) -> str:
        if self._token.token and self._token.expires_at > time.time() + 60:
            return self._token.token
        if (
            not self.settings.feishu_app_id
            or not self.settings.feishu_app_secret.get_secret_value()
        ):
            raise RuntimeError("Feishu app credentials are not configured")
        response = await self.client.post(
            f"{self.settings.feishu_domain.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.settings.feishu_app_id,
                "app_secret": self.settings.feishu_app_secret.get_secret_value(),
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0 or not payload.get("tenant_access_token"):
            raise RuntimeError(
                f"Feishu token request failed: {payload.get('msg', 'unknown error')}"
            )
        self._token = TokenCache(
            payload["tenant_access_token"], time.time() + int(payload.get("expire", 7200))
        )
        return self._token.token

    async def send_post(
        self, chat_id: str, content: list[list[dict[str, Any]]], reply_to: str | None = None
    ) -> str:
        token = await self.tenant_token()
        endpoint = (
            f"{self.settings.feishu_domain.rstrip('/')}/open-apis/im/v1/messages/{reply_to}/reply"
            if reply_to
            else f"{self.settings.feishu_domain.rstrip('/')}/open-apis/im/v1/messages?receive_id_type=chat_id"
        )
        body: dict[str, Any] = {"msg_type": "post", "content": {"zh_cn": {"content": content}}}
        if not reply_to:
            body["receive_id"] = chat_id
        response = await self.client.post(
            endpoint, headers={"Authorization": f"Bearer {token}"}, json=body
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"Feishu message failed: {payload.get('msg', 'unknown error')}")
        return str(payload.get("data", {}).get("message_id", ""))


class DispatchTransport:
    def __init__(self, feishu: FeishuClient | None = None, http: httpx.AsyncClient | None = None):
        self.feishu = feishu
        self.http = http or httpx.AsyncClient(timeout=30)

    async def dispatch(self, agent: AgentRecord, task: TaskSpec, run_id: str) -> str:
        if agent.transport == "http":
            if not agent.endpoint:
                raise RuntimeError(f"agent {agent.id} has no endpoint")
            response = await self.http.post(
                agent.endpoint, json={"run_id": run_id, "task": task.model_dump(mode="json")}
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("output", data.get("message", "")))
        if not self.feishu or not task.agent_id:
            raise RuntimeError("Feishu transport is not configured")
        chat_id = agent.metadata.get("chat_id")
        if not isinstance(chat_id, str) or not chat_id:
            raise RuntimeError(f"agent {agent.id} requires metadata.chat_id")
        mention = {
            "tag": "at",
            "user_id": agent.open_id or agent.id,
            "user_name": agent.display_name,
        }
        text = {"tag": "text", "text": f"\n[Hermes task {run_id}/{task.id}] {task.prompt}"}
        return await self.feishu.send_post(chat_id, [[mention, text]])


async def close_transport(transport: DispatchTransport) -> None:
    await asyncio.gather(
        transport.feishu.close() if transport.feishu else asyncio.sleep(0),
        transport.http.aclose(),
    )
