from __future__ import annotations

import json

import httpx
import pytest
from typer.testing import CliRunner

from hermes_a2a.cli import app
from hermes_a2a.demo import DEMO_TOKEN, DemoError, run_local_demo, run_remote_demo
from hermes_a2a.demo_agent import create_demo_agent


@pytest.mark.asyncio
async def test_local_demo_runs_real_http_agent_contract() -> None:
    result = await run_local_demo(timeout_seconds=5)

    assert result["mode"] == "local"
    assert result["state"] == "succeeded"
    assert result["agents"] == ["researcher", "reviewer"]
    assert result["tasks"]["collect"]["agent_id"] == "researcher"
    assert result["tasks"]["collect"]["route_decision"]["selected_agent_id"] == "researcher"
    assert result["tasks"]["review"]["agent_id"] == "reviewer"
    assert result["registry_lifecycle"] == {
        "agent_id": "reviewer",
        "revisions": [1, 2],
        "actions": ["registered", "updated", "deleted"],
    }
    assert all(item["state"] == "succeeded" for item in result["tasks"].values())


def test_demo_cli_prints_machine_readable_result() -> None:
    result = CliRunner().invoke(app, ["demo", "--timeout-seconds", "5"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["state"] == "succeeded"
    assert payload["mode"] == "local"


@pytest.mark.asyncio
async def test_demo_agent_rejects_attachments() -> None:
    app = create_demo_agent("researcher")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://demo-agent"
    ) as client:
        response = await client.post(
            "/execute",
            json={"run_id": "run-demo", "task": {"id": "collect"}, "attachments": [{}]},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "the zero-credential demo rejects attachments"


@pytest.mark.asyncio
async def test_remote_demo_rejects_external_url() -> None:
    with pytest.raises(DemoError, match="bundled local or Compose"):
        await run_remote_demo("https://example.invalid", DEMO_TOKEN)


def test_remote_demo_cli_requires_token() -> None:
    result = CliRunner().invoke(app, ["demo", "--base-url", "http://hermes:8080"])

    assert result.exit_code == 1
    assert "HERMES_DEMO_TOKEN is required" in result.output
