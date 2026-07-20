from __future__ import annotations

import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from . import __version__
from .attachments import parse_feishu_message
from .config import Settings, get_settings, load_agent_config
from .coordinator import Coordinator
from .models import (
    AgentRecord,
    AgentRegistration,
    AgentResultEvent,
    Heartbeat,
    TaskSpec,
    WorkflowDefinition,
    WorkflowRun,
)
from .security import decrypt_feishu_event, verify_webhook_signature
from .transport import close_transport

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, coordinator: Coordinator | None = None) -> FastAPI:
    resolved = settings or get_settings()
    control = coordinator or Coordinator(resolved)
    if coordinator is None and resolved.agents_config_path.is_file():
        for registration in load_agent_config(resolved.agents_config_path):
            control.register(registration)
    if resolved.feishu_file_intake_agent_id:
        intake_agent = control.store.get_agent(resolved.feishu_file_intake_agent_id)
        if not intake_agent:
            raise ValueError("HERMES_FEISHU_FILE_INTAKE_AGENT_ID must reference a registered Agent")
        if "attachment:read" not in intake_agent.permissions:
            raise ValueError("the Feishu file intake Agent requires attachment:read permission")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await close_transport(control.transport)
        control.store.close()

    app = FastAPI(title="Hermes Feishu A2A", version=__version__, lifespan=lifespan)
    app.state.coordinator = control
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
            "role": "workflow coordinator",
            "version": __version__,
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        errors = resolved.validate_for_production() if resolved.env == "production" else []
        if errors:
            raise HTTPException(status_code=503, detail=errors)
        return {"status": "ready", "agents": control.metrics()["agents_total"]}

    @app.get("/metrics")
    async def metrics() -> dict[str, int]:
        control.health_sweep()
        return control.metrics()

    @app.get("/agents", dependencies=[Depends(require_internal)])
    async def list_agents() -> list[AgentRecord]:
        return control.store.list_agents()

    @app.post("/agents", response_model=AgentRecord, dependencies=[Depends(require_internal)])
    async def register_agent(registration: AgentRegistration) -> AgentRecord:
        return control.register(registration)

    @app.post(
        "/agents/{agent_id}/heartbeat",
        response_model=AgentRecord,
        dependencies=[Depends(require_internal)],
    )
    async def heartbeat(agent_id: str, heartbeat: Heartbeat) -> AgentRecord:
        try:
            return control.heartbeat(agent_id, heartbeat)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc

    @app.post(
        "/workflows", response_model=WorkflowDefinition, dependencies=[Depends(require_internal)]
    )
    async def create_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
        control.store.save_workflow(workflow)
        return workflow

    @app.post("/workflows/{workflow_id}/run", dependencies=[Depends(require_internal)])
    async def run_workflow(workflow_id: str) -> dict[str, str]:
        workflow = control.store.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="workflow not found")
        run = control.submit(workflow)
        return {"run_id": run.run_id, "state": run.state}

    @app.get("/runs/{run_id}", dependencies=[Depends(require_internal)])
    async def get_run(run_id: str) -> Any:
        run = control.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.post("/events/agent-result", dependencies=[Depends(require_internal)])
    async def agent_result(event: AgentResultEvent) -> dict[str, bool]:
        run = control.get_run(event.run_id)
        if not run or event.task_id not in run.task_results:
            raise HTTPException(status_code=404, detail="task run not found")
        result = run.task_results[event.task_id]
        if result.agent_id != event.agent_id:
            raise HTTPException(status_code=403, detail="agent is not assigned to this task")
        if control.transport.resolve_result(
            event.run_id,
            event.task_id,
            output=event.output,
            error=event.error,
            success=event.success,
        ):
            return {"accepted": True}
        raise HTTPException(status_code=409, detail="task is not waiting for an Agent result")

    @app.post("/webhooks/feishu")
    async def feishu_webhook(
        request: Request, x_lark_signature: str | None = Header(default=None)
    ) -> dict[str, Any]:
        body = await request.body()
        if resolved.feishu_webhook_signature_required and not verify_webhook_signature(
            body,
            timestamp=request.headers.get("X-Lark-Request-Timestamp")
            or request.headers.get("X-Lark-Timestamp"),
            nonce=request.headers.get("X-Lark-Request-Nonce")
            or request.headers.get("X-Lark-Nonce"),
            signature=x_lark_signature,
            encrypt_key=resolved.feishu_encrypt_key.get_secret_value(),
            tolerance_seconds=resolved.webhook_tolerance_seconds,
        ):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
        try:
            parsed: object = json.loads(body or b"{}")
            if not isinstance(parsed, dict):
                raise ValueError("webhook payload must be a JSON object")
            payload: dict[str, Any] = parsed
            if payload.get("encrypt") and resolved.feishu_encrypt_key.get_secret_value():
                payload = decrypt_feishu_event(
                    payload["encrypt"], resolved.feishu_encrypt_key.get_secret_value()
                )
        except (JSONDecodeError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="invalid webhook payload") from exc
        expected_token = resolved.feishu_verification_token.get_secret_value()
        header = payload.get("header", {})
        received_token = payload.get("token") or (
            header.get("token") if isinstance(header, dict) else None
        )
        if expected_token and (
            not isinstance(received_token, str)
            or not hmac.compare_digest(expected_token, received_token)
        ):
            raise HTTPException(status_code=401, detail="invalid verification token")
        if payload.get("type") == "url_verification" or payload.get("challenge"):
            return {"challenge": payload.get("challenge", "")}
        event = payload.get("event", {})
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="invalid event object")
        message = event.get("message", {})
        if not isinstance(message, dict):
            raise HTTPException(status_code=400, detail="invalid message object")
        chat_id = message.get("chat_id")
        if resolved.feishu_allowed_chat_ids and chat_id not in resolved.feishu_allowed_chat_ids:
            return {"accepted": False, "reason": "chat_not_allowed"}
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}) if isinstance(sender, dict) else {}
        sender_open_id = sender_id.get("open_id") if isinstance(sender_id, dict) else None
        registered_open_ids = {
            agent.open_id for agent in control.store.list_agents() if agent.open_id
        }
        if resolved.feishu_owner_open_ids and (
            sender_open_id not in resolved.feishu_owner_open_ids
            and sender_open_id not in registered_open_ids
        ):
            return {"accepted": False, "reason": "sender_not_allowed"}
        logger.info(
            "feishu event accepted chat_id=%s message_id=%s",
            chat_id,
            message.get("message_id"),
        )
        text, attachments = parse_feishu_message(message)
        parent_message_ids = [
            value
            for value in (message.get("parent_id"), message.get("root_id"))
            if isinstance(value, str) and value
        ]
        if (
            sender_open_id in registered_open_ids
            and text
            and control.transport.resolve_feishu_reply(
                parent_message_ids,
                sender_open_id,
                text,
            )
        ):
            return {"accepted": True, "agent_result": True}
        if len(attachments) > resolved.feishu_file_max_count:
            return {
                "accepted": False,
                "reason": "too_many_attachments",
                "attachments": len(attachments),
            }
        intake_agent_id = resolved.feishu_file_intake_agent_id
        sender_type = sender.get("sender_type") if isinstance(sender, dict) else None
        is_agent_sender = sender_type == "app" or sender_open_id in registered_open_ids
        message_id = message.get("message_id")
        if not (
            intake_agent_id
            and attachments
            and isinstance(chat_id, str)
            and isinstance(message_id, str)
            and not is_agent_sender
        ):
            return {"accepted": True, "attachments": len(attachments)}

        event_id = header.get("event_id") if isinstance(header, dict) else None
        dedupe_id = str(event_id or message_id)
        if not control.store.claim_event(dedupe_id):
            return {"accepted": True, "duplicate": True, "attachments": len(attachments)}

        workflow = WorkflowDefinition(
            id=f"feishu-file-{message_id}",
            name=f"Feishu file intake {message_id}",
            chat_id=chat_id,
            created_by=sender_open_id,
            tasks=[
                TaskSpec(
                    id="process-files",
                    title="Process Feishu files",
                    prompt=(
                        text[:10000]
                        or "Read the attached files and provide the requested analysis."
                    ),
                    agent_id=intake_agent_id,
                    attachments=attachments,
                )
            ],
        )

        async def reply_with_result(completed: WorkflowRun) -> None:
            feishu = control.transport.feishu
            if feishu is None:
                return
            if completed.state == "succeeded":
                reply = completed.final_output or "The attached files were processed successfully."
            else:
                errors = [
                    result.error for result in completed.task_results.values() if result.error
                ]
                reply = f"File processing failed: {errors[0] if errors else completed.error or 'unknown error'}"
            await feishu.send_text(
                chat_id,
                reply[: resolved.feishu_file_result_reply_chars],
                reply_to=message_id,
            )

        run = control.submit(workflow, on_complete=reply_with_result)
        return {
            "accepted": True,
            "attachments": len(attachments),
            "workflow_id": workflow.id,
            "run_id": run.run_id,
        }

    return app
