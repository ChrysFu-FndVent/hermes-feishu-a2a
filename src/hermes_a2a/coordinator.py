from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .config import Settings
from .models import (
    AgentRecord,
    AgentRegistration,
    AgentStatus,
    Heartbeat,
    WorkflowDefinition,
    WorkflowRun,
)
from .store import Store
from .transport import DispatchTransport, FeishuClient
from .workflows import WorkflowEngine, now

logger = logging.getLogger(__name__)
RunCompletion = Callable[[WorkflowRun], Awaitable[None]]


class Coordinator:
    """Own Agent routing, task lifecycle, health state, and persisted run results."""

    def __init__(
        self,
        settings: Settings,
        store: Store | None = None,
        transport: DispatchTransport | None = None,
    ):
        self.settings = settings
        self.store = store or Store(settings.database_url)
        self.transport = transport or DispatchTransport(feishu=FeishuClient(settings))
        self.engine = WorkflowEngine(
            self.store,
            self.transport,
            settings.default_task_timeout_seconds,
            settings.max_concurrency,
        )
        self._jobs: set[asyncio.Task[WorkflowRun]] = set()

    def register(self, registration: AgentRegistration) -> AgentRecord:
        current = self.store.get_agent(registration.id)
        record = AgentRecord(
            **registration.model_dump(),
            status=current.status if current else AgentStatus.offline,
            registered_at=current.registered_at if current else now(),
            last_heartbeat_at=current.last_heartbeat_at if current else None,
        )
        return self.store.upsert_agent(record)

    def heartbeat(self, agent_id: str, heartbeat: Heartbeat) -> AgentRecord:
        agent = self.store.get_agent(agent_id)
        if not agent:
            raise KeyError(agent_id)
        agent.status = heartbeat.status
        agent.last_heartbeat_at = now()
        agent.last_error = heartbeat.message if heartbeat.status == AgentStatus.degraded else None
        agent.consecutive_failures = (
            0 if heartbeat.status == AgentStatus.online else agent.consecutive_failures
        )
        if heartbeat.capabilities is not None:
            agent.capabilities = heartbeat.capabilities
        return self.store.upsert_agent(agent)

    def health_sweep(self) -> list[AgentRecord]:
        changed: list[AgentRecord] = []
        for agent in self.store.list_agents():
            if agent.last_heartbeat_at is None:
                continue
            age = (now() - agent.last_heartbeat_at).total_seconds()
            if age > agent.heartbeat_interval_seconds * 2 and agent.status != AgentStatus.offline:
                agent.status = AgentStatus.offline
                agent.last_error = "heartbeat timeout"
                changed.append(self.store.upsert_agent(agent))
        return changed

    def submit(
        self, workflow: WorkflowDefinition, on_complete: RunCompletion | None = None
    ) -> WorkflowRun:
        self.store.save_workflow(workflow)
        run = WorkflowRun(workflow_id=workflow.id)
        self.store.save_run(run)

        async def execute() -> WorkflowRun:
            completed = await self.engine.run(workflow, run)
            if on_complete is not None:
                try:
                    await on_complete(completed)
                except Exception:
                    logger.exception("workflow completion callback failed run_id=%s", run.run_id)
            return completed

        job = asyncio.create_task(execute())
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.store.get_run(run_id)

    def metrics(self) -> dict[str, int]:
        agents = self.store.list_agents()
        return {
            "agents_total": len(agents),
            "agents_online": sum(agent.status == AgentStatus.online for agent in agents),
            "agents_degraded": sum(agent.status == AgentStatus.degraded for agent in agents),
            "agents_offline": sum(agent.status == AgentStatus.offline for agent in agents),
            "workflows_total": len(self.store.workflows),
            "runs_total": len(self.store.runs),
        }
