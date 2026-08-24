from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(StrEnum):
    online = "online"
    busy = "busy"
    degraded = "degraded"
    offline = "offline"


class RegistrationOwner(StrEnum):
    declarative = "declarative"
    legacy = "legacy"
    runtime = "runtime"


class AgentRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    capabilities: list[str] = Field(default_factory=list)
    transport: Literal["http", "feishu"] = "http"
    endpoint: str | None = None
    app_id: str | None = None
    open_id: str | None = None
    permissions: list[str] = Field(default_factory=list)
    heartbeat_interval_seconds: int = Field(default=60, ge=10, le=3600)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capabilities", "permissions")
    @classmethod
    def normalize_names(cls, values: list[str]) -> list[str]:
        normalized = sorted({value.strip().lower() for value in values if value.strip()})
        return normalized

    @model_validator(mode="after")
    def validate_transport_target(self) -> AgentRegistration:
        if self.transport == "http":
            if not self.endpoint:
                raise ValueError("HTTP agents require endpoint")
            if not self.endpoint.startswith(("http://", "https://")):
                raise ValueError("HTTP agent endpoint must use http:// or https://")
            parsed = urlsplit(self.endpoint)
            if parsed.username or parsed.password or parsed.fragment:
                raise ValueError("HTTP agent endpoint must not contain credentials or fragments")
            if not parsed.hostname:
                raise ValueError("HTTP agent endpoint must include a host")
        if self.transport == "feishu":
            if not self.open_id:
                raise ValueError("Feishu agents require open_id")
            if not isinstance(self.metadata.get("chat_id"), str) or not self.metadata["chat_id"]:
                raise ValueError("Feishu agents require metadata.chat_id")
        return self


class AgentRecord(AgentRegistration):
    managed_by: RegistrationOwner = RegistrationOwner.legacy
    revision: int = Field(default=1, ge=1)
    status: AgentStatus = AgentStatus.offline
    registered_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_heartbeat_at: datetime | None = None
    load: float | None = Field(default=None, ge=0, le=1)
    last_error: str | None = None
    consecutive_failures: int = 0


class AgentRegistryEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"agent-event-{uuid4().hex[:12]}")
    agent_id: str
    action: Literal["registered", "updated", "deleted"]
    revision: int = Field(ge=1)
    managed_by: RegistrationOwner
    occurred_at: datetime = Field(default_factory=utc_now)


class Heartbeat(BaseModel):
    status: AgentStatus = AgentStatus.online
    load: float | None = Field(default=None, ge=0, le=1)
    capabilities: list[str] | None = None
    message: str | None = Field(default=None, max_length=500)

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return sorted({value.strip().lower() for value in values if value.strip()})


class AgentSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    required_permissions: list[str] = Field(default_factory=list, max_length=32)
    transport: Literal["http", "feishu"] | None = None
    metadata_equals: dict[str, str | int | float | bool] = Field(default_factory=dict)
    exclude_agent_ids: list[str] = Field(default_factory=list, max_length=64)
    allow_degraded: bool = False

    @field_validator("required_capabilities", "required_permissions")
    @classmethod
    def normalize_requirements(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})


class RouteCandidate(BaseModel):
    agent_id: str
    eligible: bool
    status: AgentStatus
    load: float | None = None
    consecutive_failures: int = 0
    score: float | None = None
    reasons: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    selector: AgentSelector
    selected_agent_id: str | None = None
    explanation: str
    candidates: list[RouteCandidate] = Field(default_factory=list)


class AttachmentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["message_resource", "drive_file"]
    name: str | None = Field(default=None, max_length=255)
    message_id: str | None = Field(default=None, max_length=128)
    file_key: str | None = Field(default=None, max_length=256)
    file_token: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_locator(self) -> AttachmentReference:
        if self.kind == "message_resource" and not (self.message_id and self.file_key):
            raise ValueError("message resources require message_id and file_key")
        if self.kind == "drive_file" and not self.file_token:
            raise ValueError("drive files require file_token")
        return self


class ExtractedAttachment(BaseModel):
    name: str
    media_type: str
    text: str
    reference: AttachmentReference


class TaskSpec(BaseModel):
    id: str = Field(
        default_factory=lambda: f"task-{uuid4().hex[:8]}", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$"
    )
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=10000)
    agent_id: str | None = None
    selector: AgentSelector | None = None
    attachments: list[AttachmentReference] = Field(default_factory=list, max_length=8)
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    retries: int = Field(default=1, ge=0, le=5)

    @model_validator(mode="after")
    def validate_assignment(self) -> TaskSpec:
        if self.agent_id is not None and self.selector is not None:
            raise ValueError("task must use either agent_id or selector, not both")
        return self


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: f"wf-{uuid4().hex[:10]}")
    name: str = Field(min_length=1, max_length=160)
    mode: Literal["serial", "parallel"] = "serial"
    tasks: list[TaskSpec] = Field(min_length=1, max_length=100)
    chat_id: str | None = None
    created_by: str | None = None

    @field_validator("tasks")
    @classmethod
    def validate_dependencies(cls, tasks: list[TaskSpec]) -> list[TaskSpec]:
        ids = {task.id for task in tasks}
        if len(ids) != len(tasks):
            raise ValueError("task ids must be unique")
        for task in tasks:
            missing = set(task.depends_on) - ids
            if missing:
                raise ValueError(f"task {task.id} depends on unknown task(s): {sorted(missing)}")
        return tasks


class TaskState(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class TaskResult(BaseModel):
    task_id: str
    state: TaskState
    output: str = ""
    error: str | None = None
    agent_id: str | None = None
    route_decision: RouteDecision | None = None
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRun(BaseModel):
    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:12]}")
    workflow_id: str
    state: Literal["queued", "running", "succeeded", "failed"] = "queued"
    task_results: dict[str, TaskResult] = Field(default_factory=dict)
    final_output: str = ""
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentResultEvent(BaseModel):
    run_id: str
    task_id: str
    agent_id: str
    output: str = ""
    error: str | None = None
    success: bool = True
