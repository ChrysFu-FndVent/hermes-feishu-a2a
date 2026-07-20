from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(StrEnum):
    online = "online"
    busy = "busy"
    degraded = "degraded"
    offline = "offline"


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


class AgentRecord(AgentRegistration):
    status: AgentStatus = AgentStatus.offline
    registered_at: datetime = Field(default_factory=utc_now)
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class Heartbeat(BaseModel):
    status: AgentStatus = AgentStatus.online
    load: float | None = Field(default=None, ge=0, le=1)
    capabilities: list[str] | None = None
    message: str | None = Field(default=None, max_length=500)


class TaskSpec(BaseModel):
    id: str = Field(
        default_factory=lambda: f"task-{uuid4().hex[:8]}", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$"
    )
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=10000)
    agent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    retries: int = Field(default=1, ge=0, le=5)


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
