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
from hermes_a2a.models import TaskResult, TaskSpec, TaskState, WorkflowDefinition, WorkflowRun
from hermes_a2a.store import Store


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
