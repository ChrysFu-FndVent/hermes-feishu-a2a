from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from email.message import Message
from typing import Any, Protocol
from urllib.parse import unquote

import httpx

from .attachments import AttachmentError, AttachmentIngestor, DownloadedFile
from .config import Settings
from .models import AgentRecord, ExtractedAttachment, TaskSpec


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
        body: dict[str, Any] = {
            "msg_type": "post",
            "content": json.dumps({"zh_cn": {"content": content}}, ensure_ascii=False),
        }
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

    async def send_text(self, chat_id: str, text: str, reply_to: str | None = None) -> str:
        token = await self.tenant_token()
        endpoint = (
            f"{self.settings.feishu_domain.rstrip('/')}/open-apis/im/v1/messages/{reply_to}/reply"
            if reply_to
            else f"{self.settings.feishu_domain.rstrip('/')}/open-apis/im/v1/messages?receive_id_type=chat_id"
        )
        body: dict[str, Any] = {
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
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

    async def download_message_resource(
        self, message_id: str, file_key: str, *, max_bytes: int
    ) -> DownloadedFile:
        endpoint = (
            f"{self.settings.feishu_domain.rstrip('/')}/open-apis/im/v1/messages/"
            f"{message_id}/resources/{file_key}?type=file"
        )
        return await self._download(endpoint, fallback_name=file_key, max_bytes=max_bytes)

    async def download_drive_file(self, file_token: str, *, max_bytes: int) -> DownloadedFile:
        endpoint = (
            f"{self.settings.feishu_domain.rstrip('/')}/open-apis/drive/v1/files/"
            f"{file_token}/download"
        )
        return await self._download(endpoint, fallback_name=file_token, max_bytes=max_bytes)

    async def _download(
        self, endpoint: str, *, fallback_name: str, max_bytes: int
    ) -> DownloadedFile:
        token = await self.tenant_token()
        async with self.client.stream(
            "GET", endpoint, headers={"Authorization": f"Bearer {token}"}
        ) as response:
            declared_size = int(response.headers.get("content-length", "0") or 0)
            if declared_size > max_bytes:
                raise AttachmentError(
                    f"attachment exceeds the configured {max_bytes}-byte download limit"
                )
            chunks: list[bytes] = []
            received = 0
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise AttachmentError(
                        f"attachment exceeds the configured {max_bytes}-byte download limit"
                    )
                chunks.append(chunk)
            content = b"".join(chunks)

        media_type = response.headers.get("content-type", "application/octet-stream")
        disposition = response.headers.get("content-disposition")
        possible_api_error = response.status_code >= 400 or (
            media_type.startswith("application/json") and not disposition
        )
        if possible_api_error:
            try:
                payload = json.loads(content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            if response.status_code >= 400 or (
                isinstance(payload, dict) and payload.get("code", 0) != 0
            ):
                code = payload.get("code", response.status_code)
                message = payload.get("msg", response.reason_phrase or "download failed")
                raise AttachmentError(
                    f"Feishu file download failed ({code}: {message}); verify file-read scopes "
                    "and that the app identity can access the file"
                )

        name = _response_filename(disposition) or fallback_name
        return DownloadedFile(name=name, media_type=media_type, content=content)


class DispatchTransport:
    def __init__(
        self,
        feishu: FeishuClient | None = None,
        http: httpx.AsyncClient | None = None,
        attachment_ingestor: AttachmentIngestor | None = None,
    ):
        self.feishu = feishu
        self.http = http or httpx.AsyncClient(timeout=30)
        self.attachment_ingestor = attachment_ingestor or (
            AttachmentIngestor(feishu.settings, feishu)
            if isinstance(feishu, FeishuClient)
            else None
        )
        self._pending_results: dict[tuple[str, str], asyncio.Future[str]] = {}
        self._pending_feishu_replies: dict[str, tuple[tuple[str, str], str]] = {}

    async def dispatch(self, agent: AgentRecord, task: TaskSpec, run_id: str) -> str:
        if task.attachments and "attachment:read" not in agent.permissions:
            raise AttachmentError(f"agent {agent.id} requires the attachment:read permission")
        attachments = await self._resolve_attachments(task)
        if agent.transport == "http":
            if not agent.endpoint:
                raise RuntimeError(f"agent {agent.id} has no endpoint")
            response = await self.http.post(
                agent.endpoint,
                json={
                    "run_id": run_id,
                    "task": task.model_dump(mode="json"),
                    "attachments": [item.model_dump(mode="json") for item in attachments],
                },
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
        text = {
            "tag": "text",
            "text": (
                f"\n[Hermes task {run_id}/{task.id}] {task.prompt}"
                "\nReply in this message thread with the final result, or use the "
                "/events/agent-result callback."
            ),
        }
        content: list[dict[str, Any]] = [mention, text]
        if attachments:
            context = _attachment_context(
                attachments,
                self.feishu.settings.feishu_file_max_agent_chars,
            )
            content.append({"tag": "text", "text": f"\n\n{context}"})
        key = (run_id, task.id)
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._pending_results[key] = future
        task_message_id = ""
        try:
            task_message_id = await self.feishu.send_post(chat_id, [content])
            if task_message_id:
                self._pending_feishu_replies[task_message_id] = (
                    key,
                    agent.open_id or agent.id,
                )
            return await future
        finally:
            self._pending_results.pop(key, None)
            if task_message_id:
                self._pending_feishu_replies.pop(task_message_id, None)

    async def _resolve_attachments(self, task: TaskSpec) -> list[ExtractedAttachment]:
        if not task.attachments:
            return []
        if self.attachment_ingestor is None:
            raise AttachmentError("attachment ingestion is not configured")
        return await self.attachment_ingestor.resolve_all(task.attachments)

    def resolve_result(
        self,
        run_id: str,
        task_id: str,
        *,
        output: str,
        error: str | None,
        success: bool,
    ) -> bool:
        future = self._pending_results.get((run_id, task_id))
        if future is None or future.done():
            return False
        if success:
            future.set_result(output)
        else:
            future.set_exception(RuntimeError(error or "Agent reported failure"))
        return True

    def resolve_feishu_reply(
        self, parent_message_ids: list[str], sender_open_id: str, output: str
    ) -> bool:
        for message_id in parent_message_ids:
            pending = self._pending_feishu_replies.get(message_id)
            if pending is None:
                continue
            key, expected_open_id = pending
            if sender_open_id != expected_open_id:
                return False
            future = self._pending_results.get(key)
            if future is None or future.done():
                return False
            future.set_result(output)
            return True
        return False


async def close_transport(transport: DispatchTransport) -> None:
    await asyncio.gather(
        transport.feishu.close() if transport.feishu else asyncio.sleep(0),
        transport.http.aclose(),
    )


def _response_filename(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    message = Message()
    message["content-disposition"] = content_disposition
    filename = message.get_filename()
    if not filename:
        return None
    return unquote(str(filename)).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


def _attachment_context(attachments: list[ExtractedAttachment], max_chars: int) -> str:
    sections = [f"[Attachment: {item.name}]\n{item.text}" for item in attachments]
    context = "\n\n".join(sections)
    if len(context) > max_chars:
        return f"{context[:max_chars]}\n\n[truncated for Feishu Agent delivery]"
    return context
