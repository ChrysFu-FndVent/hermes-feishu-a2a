from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx
import pytest

from hermes_a2a.api import create_app
from hermes_a2a.config import Settings
from hermes_a2a.coordinator import Coordinator
from hermes_a2a.models import (
    AgentRegistration,
    AgentStatus,
    AttachmentReference,
    ExtractedAttachment,
    TaskResult,
    TaskSpec,
    TaskState,
    WorkflowDefinition,
    WorkflowRun,
)
from hermes_a2a.store import Store
from hermes_a2a.transport import DispatchTransport


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        internal_api_token="test-token",
        feishu_verification_token="verify-token",
        feishu_encrypt_key="encrypt-key",
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
    )
    app = create_app(
        settings=settings, coordinator=Coordinator(settings, store=Store(settings.database_url))
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health_and_protected_agent_registration(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200

    denied = await client.get("/agents")
    assert denied.status_code == 401

    created = await client.post(
        "/agents",
        headers={"X-Hermes-Token": "test-token"},
        json={
            "id": "engineer",
            "display_name": "Engineering Agent",
            "role": "coding",
            "endpoint": "https://agent.example/execute",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "offline"


@pytest.mark.asyncio
async def test_webhook_signature_and_chat_allow_list(client: httpx.AsyncClient) -> None:
    body = json.dumps(
        {
            "type": "event",
            "header": {"token": "verify-token"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_owner"}},
                "message": {"chat_id": "oc_demo", "message_id": "om_demo"},
            },
        }
    ).encode()
    timestamp = str(int(time.time()))
    nonce = "nonce"
    signature = hashlib.sha256(
        timestamp.encode() + nonce.encode() + b"encrypt-key" + body
    ).hexdigest()
    response = await client.post(
        "/webhooks/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
            "X-Lark-Signature": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is True


@pytest.mark.asyncio
async def test_agent_result_must_match_assigned_agent(client: httpx.AsyncClient) -> None:
    headers = {"X-Hermes-Token": "test-token"}
    await client.post(
        "/agents",
        headers=headers,
        json={
            "id": "engineer",
            "display_name": "Engineering Agent",
            "role": "coding",
            "endpoint": "https://agent.example/execute",
        },
    )
    app = client._transport.app
    coordinator = app.state.coordinator
    workflow = WorkflowDefinition(
        id="callback-test",
        name="callback-test",
        tasks=[TaskSpec(id="task", title="task", prompt="task", agent_id="engineer")],
    )
    coordinator.store.save_workflow(workflow)
    run = WorkflowRun(workflow_id=workflow.id)
    run.task_results["task"] = TaskResult(
        task_id="task", state=TaskState.running, agent_id="engineer"
    )
    coordinator.store.save_run(run)
    response = await client.post(
        "/events/agent-result",
        headers=headers,
        json={"run_id": run.run_id, "task_id": "task", "agent_id": "wrong", "output": "spoof"},
    )
    assert response.status_code == 403

    stale = await client.post(
        "/events/agent-result",
        headers=headers,
        json={
            "run_id": run.run_id,
            "task_id": "task",
            "agent_id": "engineer",
            "output": "late result",
        },
    )
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_app_preloads_agent_config(tmp_path: Path) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """agents:
  - id: engineer
    display_name: Engineering Agent
    role: coding
    transport: http
    endpoint: https://agent.internal/execute
""",
        encoding="utf-8",
    )
    settings = Settings(
        internal_api_token="test-token",
        agents_config_path=config_path,
        database_url=f"sqlite:///{tmp_path / 'preload.db'}",
    )
    app = create_app(settings=settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as preload_client:
        response = await preload_client.get("/agents", headers={"X-Hermes-Token": "test-token"})

    assert response.status_code == 200
    assert [agent["id"] for agent in response.json()] == ["engineer"]


@pytest.mark.asyncio
async def test_webhook_rejects_unlisted_sender(tmp_path: Path) -> None:
    settings = Settings(
        internal_api_token="test-token",
        feishu_verification_token="verify-token",
        feishu_encrypt_key="encrypt-key",
        feishu_allowed_chat_ids=["oc_allowed"],
        feishu_owner_open_ids=["ou_owner"],
        database_url=f"sqlite:///{tmp_path / 'sender.db'}",
    )
    app = create_app(
        settings=settings, coordinator=Coordinator(settings, store=Store(settings.database_url))
    )
    body = json.dumps(
        {
            "header": {"token": "verify-token"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_unknown"}},
                "message": {"chat_id": "oc_allowed"},
            },
        }
    ).encode()
    timestamp = str(int(time.time()))
    nonce = "nonce"
    signature = hashlib.sha256(
        timestamp.encode() + nonce.encode() + b"encrypt-key" + body
    ).hexdigest()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as sender_client:
        response = await sender_client.post(
            "/webhooks/feishu",
            content=body,
            headers={
                "X-Lark-Request-Timestamp": timestamp,
                "X-Lark-Request-Nonce": nonce,
                "X-Lark-Signature": signature,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"accepted": False, "reason": "sender_not_allowed"}


@pytest.mark.asyncio
async def test_webhook_routes_drive_file_to_intake_agent_and_replies(tmp_path: Path) -> None:
    replies: list[tuple[str, str, str | None]] = []
    received_payloads: list[dict[str, object]] = []

    class FakeFeishu:
        async def send_text(self, chat_id: str, text: str, reply_to: str | None = None) -> str:
            replies.append((chat_id, text, reply_to))
            return "om_reply"

        async def close(self) -> None:
            return None

    reference = AttachmentReference(kind="drive_file", file_token="drive_token", name="budget.docx")

    class FakeIngestor:
        async def resolve_all(
            self, references: list[AttachmentReference]
        ) -> list[ExtractedAttachment]:
            assert references == [reference]
            return [
                ExtractedAttachment(
                    name="budget.docx",
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    text="Rent: 100000",
                    reference=reference,
                )
            ]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        received_payloads.append(payload)
        return httpx.Response(200, json={"output": "Budget file processed"})

    settings = Settings(
        internal_api_token="test-token",
        feishu_app_id="cli_test",
        feishu_app_secret="app-secret",
        feishu_verification_token="verify-token",
        feishu_encrypt_key="encrypt-key",
        feishu_allowed_chat_ids=["oc_allowed"],
        feishu_owner_open_ids=["ou_owner"],
        feishu_file_intake_agent_id="researcher",
        database_url=f"sqlite:///{tmp_path / 'file-intake.db'}",
    )
    transport = DispatchTransport(
        feishu=FakeFeishu(),  # type: ignore[arg-type]
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        attachment_ingestor=FakeIngestor(),  # type: ignore[arg-type]
    )
    coordinator = Coordinator(
        settings,
        store=Store(settings.database_url),
        transport=transport,
    )
    agent = coordinator.register(
        AgentRegistration(
            id="researcher",
            display_name="Research Agent",
            role="research",
            endpoint="https://agent.internal/execute",
            permissions=["task:execute", "attachment:read"],
        )
    )
    agent.status = AgentStatus.online
    coordinator.store.upsert_agent(agent)
    app = create_app(settings=settings, coordinator=coordinator)
    body = json.dumps(
        {
            "header": {"token": "verify-token", "event_id": "evt_file"},
            "event": {
                "sender": {
                    "sender_type": "user",
                    "sender_id": {"open_id": "ou_owner"},
                },
                "message": {
                    "chat_id": "oc_allowed",
                    "message_id": "om_file",
                    "message_type": "post",
                    "content": json.dumps(
                        {
                            "content": [
                                [
                                    {
                                        "tag": "a",
                                        "text": "budget.docx",
                                        "href": "https://tenant.feishu.cn/file/drive_token",
                                    }
                                ]
                            ]
                        }
                    ),
                },
            },
        }
    ).encode()
    timestamp = str(int(time.time()))
    nonce = "nonce"
    signature = hashlib.sha256(
        timestamp.encode() + nonce.encode() + b"encrypt-key" + body
    ).hexdigest()
    headers = {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as file_client:
        response = await file_client.post("/webhooks/feishu", content=body, headers=headers)
        duplicate = await file_client.post("/webhooks/feishu", content=body, headers=headers)
        run_id = response.json()["run_id"]
        for _ in range(50):
            run = coordinator.get_run(run_id)
            if run and run.state in {"succeeded", "failed"}:
                break
            await __import__("asyncio").sleep(0.01)

    assert response.status_code == 200
    assert response.json()["attachments"] == 1
    assert duplicate.json()["duplicate"] is True
    assert received_payloads[0]["attachments"][0]["text"] == "Rent: 100000"  # type: ignore[index]
    assert replies == [("oc_allowed", "Budget file processed", "om_file")]
