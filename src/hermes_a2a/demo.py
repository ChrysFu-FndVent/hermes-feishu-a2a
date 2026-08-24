from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import SecretStr

from .api import create_app
from .config import Settings
from .coordinator import Coordinator
from .models import AgentRegistration
from .store import Store
from .transport import close_transport

DEMO_TOKEN = "local-demo-token-only-32-characters"
DEMO_AGENT_IDS = ("researcher", "reviewer")


class DemoError(RuntimeError):
    """Raised when the isolated demonstration cannot complete."""


def _agent_output(agent_id: str) -> str:
    if agent_id == "researcher":
        return "Synthetic research complete: three public release-readiness facts collected."
    return "Synthetic review passed: scope, evidence, and delivery checks are consistent."


def _handler_for(agent_id: str) -> type[BaseHTTPRequestHandler]:
    class DemoAgentHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/healthz":
                self.send_error(404)
                return
            self._write_json(200, {"status": "ok", "agent_id": agent_id})

        def do_POST(self) -> None:
            if self.path != "/execute":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                task = payload.get("task", {})
                if not payload.get("run_id") or not isinstance(task, dict) or not task.get("id"):
                    raise ValueError("run_id and task.id are required")
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._write_json(400, {"error": str(exc)})
                return
            self._write_json(200, {"output": _agent_output(agent_id)})

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return DemoAgentHandler


@contextmanager
def local_demo_agents() -> Iterator[dict[str, str]]:
    servers: list[ThreadingHTTPServer] = []
    threads: list[threading.Thread] = []
    endpoints: dict[str, str] = {}
    try:
        for agent_id in DEMO_AGENT_IDS:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(agent_id))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            servers.append(server)
            threads.append(thread)
            endpoints[agent_id] = f"http://127.0.0.1:{server.server_port}/execute"
        yield endpoints
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


async def _run_demo_client(
    client: httpx.AsyncClient,
    *,
    timeout_seconds: float,
    reviewer_endpoint: str,
) -> dict[str, Any]:
    headers = {"X-Hermes-Token": DEMO_TOKEN}
    health = await client.get("/healthz")
    health.raise_for_status()

    reviewer_registration = {
        "id": "reviewer",
        "display_name": "Demo Review Agent",
        "role": "synthetic acceptance review",
        "capabilities": ["review"],
        "transport": "http",
        "endpoint": reviewer_endpoint,
        "permissions": ["task:execute", "result:write"],
    }
    response = await client.post("/agents", headers=headers, json=reviewer_registration)
    response.raise_for_status()

    for agent_id in DEMO_AGENT_IDS:
        response = await client.post(
            f"/agents/{agent_id}/heartbeat",
            headers=headers,
            json={"status": "online"},
        )
        response.raise_for_status()

    workflow_id = f"local-demo-{uuid4().hex[:10]}"
    workflow = {
        "id": workflow_id,
        "name": "Zero-credential multi-Agent demonstration",
        "mode": "parallel",
        "tasks": [
            {
                "id": "collect",
                "title": "Collect synthetic release facts",
                "prompt": "Collect three synthetic facts for a release-readiness brief.",
                "selector": {"required_capabilities": ["research"]},
            },
            {
                "id": "review",
                "title": "Review synthetic release brief",
                "prompt": "Verify the synthetic brief against scope, evidence, and delivery checks.",
                "agent_id": "reviewer",
                "depends_on": ["collect"],
            },
        ],
    }
    created = await client.post("/workflows", headers=headers, json=workflow)
    created.raise_for_status()
    started = await client.post(f"/workflows/{workflow_id}/run", headers=headers)
    started.raise_for_status()
    run_id = str(started.json()["run_id"])

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        response = await client.get(f"/runs/{run_id}", headers=headers)
        response.raise_for_status()
        run = response.json()
        if run["state"] in {"succeeded", "failed"}:
            if run["state"] != "succeeded":
                raise DemoError(f"demonstration failed: {json.dumps(run, ensure_ascii=False)}")
            reviewer_registration["display_name"] = "Updated Demo Review Agent"
            updated = await client.put(
                "/agents/reviewer", headers=headers, json=reviewer_registration
            )
            updated.raise_for_status()
            deleted = await client.delete("/agents/reviewer", headers=headers)
            deleted.raise_for_status()
            history = await client.get("/agents/reviewer/events", headers=headers)
            history.raise_for_status()
            return {
                "demo": "hermes-feishu-a2a",
                "state": run["state"],
                "run_id": run_id,
                "workflow_id": workflow_id,
                "agents": list(DEMO_AGENT_IDS),
                "tasks": {
                    task_id: {
                        "state": result["state"],
                        "agent_id": result["agent_id"],
                        "output": result["output"],
                        "route_decision": result["route_decision"],
                    }
                    for task_id, result in run["task_results"].items()
                },
                "registry_lifecycle": {
                    "agent_id": "reviewer",
                    "revisions": [1, updated.json()["revision"]],
                    "actions": [event["action"] for event in history.json()],
                },
            }
        await asyncio.sleep(0.05)
    raise DemoError(f"demonstration did not finish within {timeout_seconds:g} seconds")


async def run_local_demo(timeout_seconds: float = 20) -> dict[str, Any]:
    with TemporaryDirectory(prefix="hermes-a2a-demo-") as temp_dir, local_demo_agents() as endpoints:
        database_url = f"sqlite:///{Path(temp_dir) / 'demo.db'}"
        settings = Settings(
            env="development",
            internal_api_token=SecretStr(DEMO_TOKEN),
            database_url=database_url,
            agents_config_path=Path(temp_dir) / "agents.yaml",
            feishu_app_id="",
            feishu_app_secret=SecretStr(""),
            feishu_encrypt_key=SecretStr(""),
            feishu_verification_token=SecretStr(""),
            feishu_webhook_signature_required=False,
            feishu_allowed_chat_ids=[],
            feishu_owner_open_ids=[],
            feishu_file_intake_agent_id="",
        )
        coordinator = Coordinator(settings, store=Store(database_url))
        coordinator.register_declarative(
            AgentRegistration(
                id="researcher",
                display_name="Demo Research Agent",
                role="synthetic evidence collection",
                capabilities=["research"],
                endpoint=endpoints["researcher"],
                permissions=["task:execute", "result:write"],
            )
        )
        app = create_app(settings=settings, coordinator=coordinator)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://local-demo"
            ) as client:
                result = await _run_demo_client(
                    client,
                    timeout_seconds=timeout_seconds,
                    reviewer_endpoint=endpoints["reviewer"],
                )
                result["mode"] = "local"
                return result
        finally:
            await close_transport(coordinator.transport)
            coordinator.store.close()


async def run_remote_demo(
    base_url: str, token: str, timeout_seconds: float = 20
) -> dict[str, Any]:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1", "hermes"}:
        raise DemoError("remote demo URL must be the bundled local or Compose HTTP endpoint")
    if token != DEMO_TOKEN:
        raise DemoError("remote demo token must match the bundled Compose demonstration token")
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=5) as client:
        result = await _run_demo_client(
            client,
            timeout_seconds=timeout_seconds,
            reviewer_endpoint="http://reviewer:9002/execute",
        )
        result["mode"] = "compose"
        return result
