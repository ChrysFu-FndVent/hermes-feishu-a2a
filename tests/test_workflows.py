from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from hermes_a2a.models import (
    AgentRegistration,
    AgentSelector,
    AgentStatus,
    TaskSpec,
    WorkflowDefinition,
    WorkflowRun,
)
from hermes_a2a.registry import AgentRegistry
from hermes_a2a.store import Store
from hermes_a2a.workflows import WorkflowEngine


class FakeTransport:
    def __init__(self, outputs: dict[str, str] | None = None, failures: int = 0) -> None:
        self.outputs = outputs or {}
        self.failures = failures
        self.calls: list[str] = []

    async def dispatch(self, agent, task, run_id):
        self.calls.append(task.id)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary failure")
        await asyncio.sleep(0)
        return self.outputs.get(task.id, f"done:{task.id}")


def make_store(tmp_path: Path) -> Store:
    return Store(f"sqlite:///{tmp_path / 'test.db'}")


def test_store_restores_agents_and_workflows(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'restore.db'}"
    first = Store(database_url)
    register(first)
    workflow = WorkflowDefinition(
        id="persisted", name="persisted", tasks=[TaskSpec(id="task", title="task", prompt="task")]
    )
    first.save_workflow(workflow)
    first.close()

    restored = Store(database_url)
    assert restored.get_agent("worker") is not None
    assert restored.get_workflow("persisted") == workflow
    restored.close()


def register(store: Store, agent_id: str = "worker") -> None:
    from hermes_a2a.config import Settings
    from hermes_a2a.coordinator import Coordinator

    Coordinator(Settings(internal_api_token="test"), store=store).register(
        AgentRegistration(
            id=agent_id,
            display_name=agent_id,
            role="worker",
            endpoint="https://agent.example/execute",
        )
    )
    store.agents[agent_id].status = AgentStatus.online


def test_task_rejects_ambiguous_explicit_and_selector_assignment() -> None:
    with pytest.raises(ValueError, match="either agent_id or selector"):
        TaskSpec(
            id="ambiguous",
            title="Ambiguous",
            prompt="Ambiguous",
            agent_id="worker",
            selector=AgentSelector(required_capabilities=["testing"]),
        )


@pytest.mark.asyncio
async def test_serial_dependencies_and_result(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    register(store)
    transport = FakeTransport()
    engine = WorkflowEngine(store, transport)
    workflow = WorkflowDefinition(
        id="serial",
        name="serial",
        mode="serial",
        tasks=[
            TaskSpec(id="first", title="first", prompt="one", agent_id="worker"),
            TaskSpec(
                id="second", title="second", prompt="two", agent_id="worker", depends_on=["first"]
            ),
        ],
    )

    result = await engine.run(workflow, WorkflowRun(workflow_id=workflow.id))

    assert result.state == "succeeded"
    assert transport.calls == ["first", "second"]
    assert result.final_output == "done:first\n\ndone:second"


@pytest.mark.asyncio
async def test_parallel_skips_dependents_after_failure(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    register(store)
    transport = FakeTransport(failures=1)
    engine = WorkflowEngine(store, transport)
    workflow = WorkflowDefinition(
        id="parallel",
        name="parallel",
        mode="parallel",
        tasks=[
            TaskSpec(id="bad", title="bad", prompt="bad", agent_id="worker", retries=0),
            TaskSpec(
                id="dependent",
                title="dependent",
                prompt="dependent",
                agent_id="worker",
                depends_on=["bad"],
            ),
        ],
    )

    result = await engine.run(workflow, WorkflowRun(workflow_id=workflow.id))

    assert result.state == "failed"
    assert result.task_results["bad"].state == "failed"
    assert result.task_results["dependent"].state == "skipped"
    assert transport.calls == ["bad"]


@pytest.mark.asyncio
async def test_retry_recovers_and_marks_agent_online(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    register(store)
    transport = FakeTransport(failures=1)
    engine = WorkflowEngine(store, transport)
    workflow = WorkflowDefinition(
        id="retry",
        name="retry",
        tasks=[
            TaskSpec(id="retry-task", title="retry", prompt="retry", agent_id="worker", retries=1)
        ],
    )

    result = await engine.run(workflow, WorkflowRun(workflow_id=workflow.id))

    assert result.state == "succeeded"
    assert result.task_results["retry-task"].attempts == 2
    assert store.get_agent("worker").status == AgentStatus.online


@pytest.mark.asyncio
async def test_task_selector_routes_and_persists_decision(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    registry = AgentRegistry(store)
    registry.register_runtime(
        AgentRegistration(
            id="engineer",
            display_name="Engineer",
            role="implementation",
            capabilities=["coding", "testing"],
            endpoint="https://engineer.internal/execute",
        )
    )
    store.set_agent_status("engineer", AgentStatus.online)
    transport = FakeTransport()
    engine = WorkflowEngine(store, transport, registry=registry)
    workflow = WorkflowDefinition(
        id="routed",
        name="routed",
        tasks=[
            TaskSpec(
                id="implement",
                title="Implement",
                prompt="Implement the change",
                selector=AgentSelector(required_capabilities=["coding"]),
            )
        ],
    )

    result = await engine.run(workflow, WorkflowRun(workflow_id=workflow.id))

    task_result = result.task_results["implement"]
    assert result.state == "succeeded"
    assert task_result.agent_id == "engineer"
    assert task_result.route_decision is not None
    assert task_result.route_decision.selected_agent_id == "engineer"
    assert transport.calls == ["implement"]


@pytest.mark.asyncio
async def test_dispatch_rechecks_endpoint_policy_for_persisted_agents(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    permissive_registry = AgentRegistry(store)
    permissive_registry.register_runtime(
        AgentRegistration(
            id="legacy-http",
            display_name="Legacy HTTP",
            role="legacy",
            endpoint="http://legacy.internal/execute",
        )
    )
    store.set_agent_status("legacy-http", AgentStatus.online)
    transport = FakeTransport()
    engine = WorkflowEngine(
        store,
        transport,
        registry=AgentRegistry(store, endpoint_require_https=True),
    )
    workflow = WorkflowDefinition(
        id="endpoint-recheck",
        name="endpoint recheck",
        tasks=[
            TaskSpec(
                id="blocked",
                title="Blocked",
                prompt="Do not dispatch",
                agent_id="legacy-http",
            )
        ],
    )

    result = await engine.run(workflow, WorkflowRun(workflow_id=workflow.id))

    assert result.state == "failed"
    assert result.task_results["blocked"].error == "HTTP Agent endpoints must use HTTPS"
    assert transport.calls == []
