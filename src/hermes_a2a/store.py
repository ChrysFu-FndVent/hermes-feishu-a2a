from __future__ import annotations

import sqlite3
from json import JSONDecodeError
from pathlib import Path
from threading import RLock
from time import time

from .models import AgentRecord, AgentRegistryEvent, AgentStatus, WorkflowDefinition, WorkflowRun


class Store:
    """Small persistence boundary; replace this with Postgres without touching orchestration."""

    def __init__(self, database_url: str = "sqlite:///./data/hermes.db"):
        self._lock = RLock()
        self.agents: dict[str, AgentRecord] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.runs: dict[str, WorkflowRun] = {}
        self.events: set[str] = set()
        self.agent_registry_events: list[AgentRegistryEvent] = []
        self._db: sqlite3.Connection | None = None
        if database_url.startswith("sqlite:///"):
            path = Path(database_url.removeprefix("sqlite:///"))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, received_at REAL NOT NULL)"
            )
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS agent_registry_events "
                "(id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            self._db.commit()
            self._load()

    def upsert_agent(self, agent: AgentRecord) -> AgentRecord:
        with self._lock:
            self.agents[agent.id] = agent
            self._save("agents", agent.id, agent.model_dump_json())
            return agent

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        return self.agents.get(agent_id)

    def list_agents(self) -> list[AgentRecord]:
        return list(self.agents.values())

    def delete_agent(self, agent_id: str) -> AgentRecord:
        with self._lock:
            agent = self.agents.pop(agent_id)
            if self._db is not None:
                self._db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
                self._db.commit()
            return agent

    def save_agent_registry_event(self, event: AgentRegistryEvent) -> AgentRegistryEvent:
        with self._lock:
            self.agent_registry_events.append(event)
            if self._db is not None:
                self._db.execute(
                    "INSERT INTO agent_registry_events (id, agent_id, payload) VALUES (?, ?, ?)",
                    (event.id, event.agent_id, event.model_dump_json()),
                )
                self._db.commit()
            return event

    def list_agent_registry_events(self, agent_id: str) -> list[AgentRegistryEvent]:
        return [event for event in self.agent_registry_events if event.agent_id == agent_id]

    def set_agent_status(
        self, agent_id: str, status: AgentStatus, error: str | None = None
    ) -> AgentRecord:
        agent = self.agents[agent_id]
        agent.status = status
        agent.last_error = error
        self.upsert_agent(agent)
        return agent

    def save_workflow(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        self.workflows[workflow.id] = workflow
        self._save("workflows", workflow.id, workflow.model_dump_json())
        return workflow

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.workflows.get(workflow_id)

    def save_run(self, run: WorkflowRun) -> WorkflowRun:
        self.runs[run.run_id] = run
        self._save("runs", run.run_id, run.model_dump_json())
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.runs.get(run_id)

    def claim_event(self, event_id: str) -> bool:
        """Return true exactly once for a Feishu event/message identifier."""
        with self._lock:
            if event_id in self.events:
                return False
            if self._db is not None:
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO events (id, received_at) VALUES (?, ?)",
                    (event_id, time()),
                )
                self._db.commit()
                if cursor.rowcount == 0:
                    self.events.add(event_id)
                    return False
            self.events.add(event_id)
            return True

    def _save(self, table: str, key: str, payload: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            f"INSERT OR REPLACE INTO {table} (id, payload) VALUES (?, ?)", (key, payload)
        )
        self._db.commit()

    def _load(self) -> None:
        """Restore the in-memory indexes after a process restart."""
        if self._db is None:
            return
        with self._lock:
            for key, payload in self._db.execute("SELECT id, payload FROM agents"):
                try:
                    self.agents[key] = AgentRecord.model_validate_json(payload)
                except (ValueError, JSONDecodeError):
                    continue
            for key, payload in self._db.execute("SELECT id, payload FROM workflows"):
                try:
                    self.workflows[key] = WorkflowDefinition.model_validate_json(payload)
                except (ValueError, JSONDecodeError):
                    continue
            for key, payload in self._db.execute("SELECT id, payload FROM runs"):
                try:
                    self.runs[key] = WorkflowRun.model_validate_json(payload)
                except (ValueError, JSONDecodeError):
                    continue
            for (payload,) in self._db.execute(
                "SELECT payload FROM agent_registry_events ORDER BY rowid"
            ):
                try:
                    self.agent_registry_events.append(
                        AgentRegistryEvent.model_validate_json(payload)
                    )
                except (ValueError, JSONDecodeError):
                    continue

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
