from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from hermes_a2a.attachments import AttachmentError, DownloadedFile
from hermes_a2a.config import Settings
from hermes_a2a.models import (
    AgentRecord,
    AttachmentReference,
    ExtractedAttachment,
    TaskSpec,
)
from hermes_a2a.transport import DispatchTransport, FeishuClient


@pytest.mark.asyncio
async def test_http_agent_dispatch_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["run_id"] == "run-123"
        assert payload["task"]["id"] == "implement"
        return httpx.Response(200, json={"output": "implemented"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = DispatchTransport(http=http)
    agent = AgentRecord(
        id="engineer",
        display_name="Engineering Agent",
        role="implementation",
        endpoint="https://agent.internal/execute",
    )
    task = TaskSpec(
        id="implement",
        title="Implement",
        prompt="Implement the change",
        agent_id="engineer",
    )

    assert await transport.dispatch(agent, task, "run-123") == "implemented"
    await transport.http.aclose()


@pytest.mark.asyncio
async def test_feishu_post_content_is_json_encoded() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200},
            )
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "om_result"}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = FeishuClient(
        Settings(feishu_app_id="cli_test", feishu_app_secret="app-secret"), client=http
    )

    message_id = await client.send_post("oc_chat", [[{"tag": "text", "text": "hello"}]])
    await client.close()

    assert message_id == "om_result"
    payload = json.loads(requests[1].content)
    assert payload["receive_id"] == "oc_chat"
    assert isinstance(payload["content"], str)
    assert json.loads(payload["content"])["zh_cn"]["content"][0][0]["text"] == "hello"


@pytest.mark.asyncio
async def test_feishu_drive_file_download() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200},
            )
        assert request.url.path == "/open-apis/drive/v1/files/file_token/download"
        return httpx.Response(
            200,
            content=b"document contents",
            headers={
                "content-type": "text/plain",
                "content-disposition": 'attachment; filename="notes.txt"',
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = FeishuClient(
        Settings(feishu_app_id="cli_test", feishu_app_secret="app-secret"), client=http
    )

    downloaded = await client.download_drive_file("file_token", max_bytes=1024)
    await client.close()

    assert downloaded == DownloadedFile(
        name="notes.txt", media_type="text/plain", content=b"document contents"
    )


@pytest.mark.asyncio
async def test_feishu_download_enforces_declared_size_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200},
            )
        return httpx.Response(
            200,
            content=b"large",
            headers={"content-length": "2048", "content-type": "text/plain"},
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = FeishuClient(
        Settings(feishu_app_id="cli_test", feishu_app_secret="app-secret"), client=http
    )

    with pytest.raises(AttachmentError, match="download limit"):
        await client.download_drive_file("file_token", max_bytes=1024)
    await client.close()


@pytest.mark.asyncio
async def test_http_agent_receives_extracted_attachments() -> None:
    reference = AttachmentReference(kind="drive_file", file_token="file_token", name="notes.txt")

    class FakeIngestor:
        async def resolve_all(
            self, references: list[AttachmentReference]
        ) -> list[ExtractedAttachment]:
            assert references == [reference]
            return [
                ExtractedAttachment(
                    name="notes.txt",
                    media_type="text/plain",
                    text="document contents",
                    reference=reference,
                )
            ]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["attachments"][0]["name"] == "notes.txt"
        assert payload["attachments"][0]["text"] == "document contents"
        return httpx.Response(200, json={"output": "processed"})

    transport = DispatchTransport(
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        attachment_ingestor=FakeIngestor(),  # type: ignore[arg-type]
    )
    agent = AgentRecord(
        id="researcher",
        display_name="Research Agent",
        role="research",
        endpoint="https://agent.internal/execute",
        permissions=["task:execute", "attachment:read"],
    )
    task = TaskSpec(
        id="read",
        title="Read",
        prompt="Read the file",
        agent_id="researcher",
        attachments=[reference],
    )

    assert await transport.dispatch(agent, task, "run-files") == "processed"
    await transport.http.aclose()


@pytest.mark.asyncio
async def test_feishu_dispatch_waits_for_agent_result() -> None:
    class FakeFeishu:
        async def send_post(self, chat_id: str, content: object) -> str:
            return "om_task"

    transport = DispatchTransport(feishu=FakeFeishu())  # type: ignore[arg-type]
    agent = AgentRecord(
        id="reviewer",
        display_name="Review Agent",
        role="review",
        transport="feishu",
        open_id="ou_agent",
        metadata={"chat_id": "oc_chat"},
    )
    task = TaskSpec(id="review", title="Review", prompt="Check the result", agent_id="reviewer")

    dispatched = asyncio.create_task(transport.dispatch(agent, task, "run-123"))
    await asyncio.sleep(0)

    assert not dispatched.done()
    assert transport.resolve_result(
        "run-123", "review", output="accepted", error=None, success=True
    )
    assert await dispatched == "accepted"
    await transport.http.aclose()


@pytest.mark.asyncio
async def test_feishu_thread_reply_completes_agent_result() -> None:
    class FakeFeishu:
        async def send_post(self, chat_id: str, content: object) -> str:
            return "om_task"

    transport = DispatchTransport(feishu=FakeFeishu())  # type: ignore[arg-type]
    agent = AgentRecord(
        id="reviewer",
        display_name="Review Agent",
        role="review",
        transport="feishu",
        open_id="ou_agent",
        metadata={"chat_id": "oc_chat"},
    )
    task = TaskSpec(id="review", title="Review", prompt="Check the result", agent_id="reviewer")

    dispatched = asyncio.create_task(transport.dispatch(agent, task, "run-thread"))
    await asyncio.sleep(0)

    assert transport.resolve_feishu_reply(["om_task"], "ou_agent", "thread result")
    assert await dispatched == "thread result"
    await transport.http.aclose()
