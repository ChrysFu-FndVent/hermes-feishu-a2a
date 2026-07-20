from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from .models import (
    AgentRecord,
    AgentStatus,
    TaskResult,
    TaskSpec,
    TaskState,
    WorkflowDefinition,
    WorkflowRun,
)
from .store import Store
from .transport import DispatchTransport

logger = logging.getLogger(__name__)
TaskDispatcher = Callable[[AgentRecord, TaskSpec, str], Awaitable[str]]


def now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowEngine:
    def __init__(
        self,
        store: Store,
        transport: DispatchTransport,
        timeout_seconds: float = 120,
        max_concurrency: int = 8,
    ):
        self.store = store
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def run(self, workflow: WorkflowDefinition, run: WorkflowRun) -> WorkflowRun:
        run.state = "running"
        run.started_at = now()
        self.store.save_run(run)
        try:
            if workflow.mode == "serial":
                for task in workflow.tasks:
                    if not self._dependencies_succeeded(task, run):
                        run.task_results[task.id] = TaskResult(
                            task_id=task.id, state=TaskState.skipped, error="dependency failed"
                        )
                        continue
                    await self._run_task(task, run)
            else:
                pending = {task.id: task for task in workflow.tasks}
                while pending:
                    ready = [
                        task for task in pending.values() if self._dependencies_done(task, run)
                    ]
                    if not ready:
                        raise RuntimeError("workflow dependency cycle or blocked task")
                    await asyncio.gather(*(self._skip_or_run_task(task, run) for task in ready))
                    for task in ready:
                        pending.pop(task.id)
            run.state = (
                "succeeded"
                if all(
                    result.state in {TaskState.succeeded, TaskState.skipped}
                    for result in run.task_results.values()
                )
                else "failed"
            )
            outputs = [result.output for result in run.task_results.values() if result.output]
            run.final_output = "\n\n".join(outputs)
        except Exception as exc:
            logger.exception("workflow failed run_id=%s", run.run_id)
            run.state = "failed"
            run.error = str(exc)
        finally:
            run.finished_at = now()
            self.store.save_run(run)
        return run

    def _dependencies_done(self, task: TaskSpec, run: WorkflowRun) -> bool:
        return all(dependency in run.task_results for dependency in task.depends_on)

    def _dependencies_succeeded(self, task: TaskSpec, run: WorkflowRun) -> bool:
        return all(run.task_results[item].state == TaskState.succeeded for item in task.depends_on)

    async def _skip_or_run_task(self, task: TaskSpec, run: WorkflowRun) -> None:
        if not self._dependencies_succeeded(task, run):
            run.task_results[task.id] = TaskResult(
                task_id=task.id,
                state=TaskState.skipped,
                agent_id=task.agent_id,
                error="dependency failed",
                finished_at=now(),
            )
            self.store.save_run(run)
            return
        await self._run_task(task, run)

    async def _run_task(self, task: TaskSpec, run: WorkflowRun) -> None:
        result = TaskResult(
            task_id=task.id, state=TaskState.running, agent_id=task.agent_id, started_at=now()
        )
        run.task_results[task.id] = result
        self.store.save_run(run)
        if not task.agent_id:
            result.state = TaskState.failed
            result.error = "task has no agent_id"
            result.finished_at = now()
            return
        agent = self.store.get_agent(task.agent_id)
        if not agent or agent.status == AgentStatus.offline:
            result.state = TaskState.failed
            result.error = f"agent {task.agent_id} is unavailable"
            result.finished_at = now()
            return
        timeout = task.timeout_seconds or self.timeout_seconds
        attempts = task.retries + 1
        async with self.semaphore:
            for attempt in range(1, attempts + 1):
                result.attempts = attempt
                try:
                    result.output = await asyncio.wait_for(
                        self.transport.dispatch(agent, task, run.run_id), timeout
                    )
                    result.state = TaskState.succeeded
                    result.finished_at = now()
                    agent.status = AgentStatus.online
                    agent.consecutive_failures = 0
                    self.store.upsert_agent(agent)
                    return
                except Exception as exc:
                    result.error = str(exc)
                    agent.consecutive_failures += 1
                    agent.last_error = str(exc)
                    if attempt < attempts:
                        await asyncio.sleep(min(2**attempt, 10))
            result.state = TaskState.failed
            result.finished_at = now()
            agent.status = AgentStatus.degraded
            self.store.upsert_agent(agent)
