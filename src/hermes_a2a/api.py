from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from .config import Settings, get_settings
from .coordinator import Coordinator
from .models import AgentRecord, AgentRegistration, AgentResultEvent, Heartbeat, WorkflowDefinition
from .security import decrypt_feishu_event, verify_webhook_signature

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, coordinator: Coordinator | None = None) -> FastAPI:
    resolved = settings or get_settings()
    brain = coordinator or Coordinator(resolved)
    app = FastAPI(title="Hermes Feishu A2A", version="0.1.0")
    app.state.coordinator = brain
    app.state.settings = resolved

    def require_internal(token: str | None = Header(default=None, alias="X-Hermes-Token")) -> None:
        expected = resolved.internal_api_token.get_secret_value()
        if expected and token != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal token"
            )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "hermes-feishu-a2a",
            "role": "Hermes group brain and lead",
            "version": "0.1.0",
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        errors = resolved.validate_for_production() if resolved.env == "production" else []
        if errors:
            raise HTTPException(status_code=503, detail=errors)
        return {"status": "ready", "agents": brain.metrics()["agents_total"]}

    @app.get("/metrics")
    async def metrics() -> dict[str, int]:
        brain.health_sweep()
        return brain.metrics()

    @app.get("/agents", dependencies=[Depends(require_internal)])
    async def list_agents() -> list[AgentRecord]:
        return brain.store.list_agents()

    @app.post("/agents", response_model=AgentRecord, dependencies=[Depends(require_internal)])
    async def register_agent(registration: AgentRegistration) -> AgentRecord:
        return brain.register(registration)

    @app.post(
        "/agents/{agent_id}/heartbeat",
        response_model=AgentRecord,
        dependencies=[Depends(require_internal)],
    )
    async def heartbeat(agent_id: str, heartbeat: Heartbeat) -> AgentRecord:
        try:
            return brain.heartbeat(agent_id, heartbeat)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc

    @app.post(
        "/workflows", response_model=WorkflowDefinition, dependencies=[Depends(require_internal)]
    )
    async def create_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
        brain.store.save_workflow(workflow)
        return workflow

    @app.post("/workflows/{workflow_id}/run", dependencies=[Depends(require_internal)])
    async def run_workflow(workflow_id: str) -> dict[str, str]:
        workflow = brain.store.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="workflow not found")
        run = brain.submit(workflow)
        return {"run_id": run.run_id, "state": run.state}

    @app.get("/runs/{run_id}", dependencies=[Depends(require_internal)])
    async def get_run(run_id: str) -> Any:
        run = brain.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.post("/events/agent-result", dependencies=[Depends(require_internal)])
    async def agent_result(event: AgentResultEvent) -> dict[str, bool]:
        run = brain.get_run(event.run_id)
        if not run or event.task_id not in run.task_results:
            raise HTTPException(status_code=404, detail="task run not found")
        result = run.task_results[event.task_id]
        if result.agent_id != event.agent_id:
            raise HTTPException(status_code=403, detail="agent is not assigned to this task")
        result.output = event.output
        result.error = event.error
        result.state = "succeeded" if event.success else "failed"
        brain.store.save_run(run)
        return {"accepted": True}

    @app.post("/webhooks/feishu")
    async def feishu_webhook(
        request: Request, x_lark_signature: str | None = Header(default=None)
    ) -> dict[str, Any]:
        body = await request.body()
        if resolved.feishu_webhook_signature_required and not verify_webhook_signature(
            body,
            timestamp=request.headers.get("X-Lark-Timestamp"),
            nonce=request.headers.get("X-Lark-Nonce"),
            signature=x_lark_signature,
            token=resolved.feishu_verification_token.get_secret_value(),
            tolerance_seconds=resolved.webhook_tolerance_seconds,
        ):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
        payload: dict[str, Any] = json.loads(body or b"{}")
        if payload.get("encrypt") and resolved.feishu_encrypt_key.get_secret_value():
            payload = decrypt_feishu_event(
                payload["encrypt"], resolved.feishu_encrypt_key.get_secret_value()
            )
        if payload.get("type") == "url_verification" or payload.get("challenge"):
            return {"challenge": payload.get("challenge", "")}
        event = payload.get("event", {})
        message = event.get("message", {})
        chat_id = message.get("chat_id")
        if resolved.feishu_allowed_chat_ids and chat_id not in resolved.feishu_allowed_chat_ids:
            return {"accepted": False, "reason": "chat_not_allowed"}
        logger.info(
            "feishu event accepted chat_id=%s message_id=%s", chat_id, event.get("message_id")
        )
        return {"accepted": True}

    return app
