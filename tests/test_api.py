from __future__ import annotations

import hashlib
import hmac
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
        json={"id": "codex", "display_name": "CodeX", "role": "coding"},
    )
    assert created.status_code == 200
    assert created.json()["status"] == "offline"


@pytest.mark.asyncio
async def test_webhook_signature_and_chat_allow_list(client: httpx.AsyncClient) -> None:
    body = json.dumps({"type": "event", "event": {"message": {"chat_id": "oc_demo"}}}).encode()
    timestamp = str(int(time.time()))
    nonce = "nonce"
    signature = hmac.new(
        b"verify-token", timestamp.encode() + nonce.encode() + body, hashlib.sha256
    ).hexdigest()
    response = await client.post(
        "/webhooks/feishu",
        content=body,
        headers={
            "X-Lark-Timestamp": timestamp,
            "X-Lark-Nonce": nonce,
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
        json={"id": "codex", "display_name": "CodeX", "role": "coding"},
    )
    app = client._transport.app
    coordinator = app.state.coordinator
    workflow = WorkflowDefinition(
        id="callback-test",
        name="callback-test",
        tasks=[TaskSpec(id="task", title="task", prompt="task", agent_id="codex")],
    )
    coordinator.store.save_workflow(workflow)
    run = WorkflowRun(workflow_id=workflow.id)
    run.task_results["task"] = TaskResult(task_id="task", state=TaskState.running, agent_id="codex")
    coordinator.store.save_run(run)
    response = await client.post(
        "/events/agent-result",
        headers=headers,
        json={"run_id": run.run_id, "task_id": "task", "agent_id": "wrong", "output": "spoof"},
    )
    assert response.status_code == 403
