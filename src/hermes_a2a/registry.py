from __future__ import annotations

from fnmatch import fnmatch
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

from .models import (
    AgentRecord,
    AgentRegistration,
    AgentRegistryEvent,
    AgentSelector,
    AgentStatus,
    Heartbeat,
    RegistrationOwner,
    RouteCandidate,
    RouteDecision,
    utc_now,
)
from .store import Store


class AgentOwnershipError(ValueError):
    pass


class AgentEndpointPolicyError(ValueError):
    pass


class AgentRevisionConflict(ValueError):
    pass


class AgentRegistry:
    """Own durable Agent registrations and the rules for changing them."""

    def __init__(
        self,
        store: Store,
        endpoint_allowed_hosts: list[str] | None = None,
        endpoint_require_https: bool = False,
    ):
        self.store = store
        self._lock = RLock()
        self.endpoint_allowed_hosts = endpoint_allowed_hosts or []
        self.endpoint_require_https = endpoint_require_https

    def register_runtime(self, registration: AgentRegistration) -> AgentRecord:
        with self._lock:
            current = self.store.get_agent(registration.id)
            if current and current.managed_by == RegistrationOwner.declarative:
                raise AgentOwnershipError(
                    f"agent {registration.id} is managed by declarative configuration"
                )
            return self._upsert_registration_and_audit(
                registration,
                RegistrationOwner.runtime,
                "updated" if current else "registered",
                current,
            )

    def register_declarative(self, registration: AgentRegistration) -> AgentRecord:
        with self._lock:
            self._validate_endpoint(registration)
            current = self.store.get_agent(registration.id)
            if current and current.managed_by == RegistrationOwner.runtime:
                raise AgentOwnershipError(
                    f"agent {registration.id} is managed by the runtime control interface"
                )
            if current and self._registration_matches(current, registration):
                if current.managed_by == RegistrationOwner.legacy:
                    current.managed_by = RegistrationOwner.declarative
                    current.updated_at = utc_now()
                    saved = self.store.upsert_agent(current)
                    self._record_event(saved, "updated")
                    return saved
                return current
            return self._upsert_registration_and_audit(
                registration,
                RegistrationOwner.declarative,
                "updated" if current else "registered",
                current,
            )

    def sync_declarative(
        self, registrations: list[AgentRegistration]
    ) -> list[AgentRecord]:
        with self._lock:
            incoming_ids = {registration.id for registration in registrations}
            conflicts = sorted(
                agent.id
                for agent in self.store.list_agents()
                if agent.id in incoming_ids and agent.managed_by == RegistrationOwner.runtime
            )
            if conflicts:
                raise AgentOwnershipError(
                    "runtime registrations conflict with declarative configuration: "
                    + ", ".join(conflicts)
                )
            synced = [self.register_declarative(registration) for registration in registrations]
            stale = [
                agent
                for agent in self.store.list_agents()
                if agent.managed_by == RegistrationOwner.declarative
                and agent.id not in incoming_ids
            ]
            for agent in stale:
                self.store.delete_agent(agent.id)
                self._record_event(agent, "deleted")
            return synced

    def update_runtime(
        self,
        agent_id: str,
        registration: AgentRegistration,
        expected_revision: int | None = None,
    ) -> AgentRecord:
        with self._lock:
            if registration.id != agent_id:
                raise ValueError("path agent id must match registration id")
            current = self.store.get_agent(agent_id)
            if current is None:
                raise KeyError(agent_id)
            if current.managed_by == RegistrationOwner.declarative:
                raise AgentOwnershipError(
                    f"agent {agent_id} is managed by declarative configuration"
                )
            if expected_revision is not None and current.revision != expected_revision:
                raise AgentRevisionConflict(
                    f"expected revision {expected_revision}, current revision {current.revision}"
                )
            return self._upsert_registration_and_audit(
                registration, RegistrationOwner.runtime, "updated", current
            )

    def delete_runtime(self, agent_id: str) -> AgentRecord:
        with self._lock:
            current = self.store.get_agent(agent_id)
            if current is None:
                raise KeyError(agent_id)
            if current.managed_by == RegistrationOwner.declarative:
                raise AgentOwnershipError(
                    f"agent {agent_id} is managed by declarative configuration"
                )
            deleted = self.store.delete_agent(agent_id)
            self._record_event(deleted, "deleted")
            return deleted

    def history(self, agent_id: str) -> list[AgentRegistryEvent]:
        return self.store.list_agent_registry_events(agent_id)

    def heartbeat(self, agent_id: str, heartbeat: Heartbeat) -> AgentRecord:
        with self._lock:
            agent = self.store.get_agent(agent_id)
            if agent is None:
                raise KeyError(agent_id)
            agent.status = heartbeat.status
            agent.load = heartbeat.load
            agent.last_heartbeat_at = utc_now()
            agent.last_error = (
                heartbeat.message if heartbeat.status == AgentStatus.degraded else None
            )
            agent.consecutive_failures = (
                0 if heartbeat.status == AgentStatus.online else agent.consecutive_failures
            )
            if heartbeat.capabilities is not None:
                agent.capabilities = heartbeat.capabilities
            return self.store.upsert_agent(agent)

    def ensure_dispatch_allowed(self, agent: AgentRecord) -> None:
        self._validate_endpoint(agent)

    def route(self, selector: AgentSelector) -> RouteDecision:
        candidates = [self._evaluate(agent, selector) for agent in self.store.list_agents()]
        candidates.sort(
            key=lambda item: (
                not item.eligible,
                item.score if item.score is not None else float("inf"),
                item.agent_id,
            )
        )
        selected = next((candidate for candidate in candidates if candidate.eligible), None)
        explanation = (
            "no eligible Agent matched the selector"
            if selected is None
            else (
                f"selected {selected.agent_id}: satisfied all constraints with "
                f"status {selected.status} and score {selected.score:.2f}"
            )
        )
        return RouteDecision(
            selector=selector,
            selected_agent_id=selected.agent_id if selected else None,
            explanation=explanation,
            candidates=candidates,
        )

    def _upsert_registration_and_audit(
        self,
        registration: AgentRegistration,
        managed_by: RegistrationOwner,
        action: Literal["registered", "updated", "deleted"],
        current: AgentRecord | None,
    ) -> AgentRecord:
        self._validate_endpoint(registration)
        record = AgentRecord(
            **registration.model_dump(),
            managed_by=managed_by,
            revision=current.revision + 1 if current else 1,
            status=current.status if current else AgentStatus.offline,
            registered_at=current.registered_at if current else utc_now(),
            updated_at=utc_now(),
            last_heartbeat_at=current.last_heartbeat_at if current else None,
            load=current.load if current else None,
            last_error=current.last_error if current else None,
            consecutive_failures=current.consecutive_failures if current else 0,
        )
        saved = self.store.upsert_agent(record)
        self._record_event(saved, action)
        return saved

    def get(self, agent_id: str) -> AgentRecord | None:
        return self.store.get_agent(agent_id)

    def list(self) -> list[AgentRecord]:
        return self.store.list_agents()

    def _record_event(
        self, record: AgentRecord, action: Literal["registered", "updated", "deleted"]
    ) -> None:
        self.store.save_agent_registry_event(
            AgentRegistryEvent(
                agent_id=record.id,
                action=action,
                revision=record.revision,
                managed_by=record.managed_by,
            )
        )

    @staticmethod
    def _registration_matches(record: AgentRecord, registration: AgentRegistration) -> bool:
        current = AgentRegistration.model_validate(record.model_dump())
        return current == registration

    def _validate_endpoint(self, registration: AgentRegistration) -> None:
        if registration.transport != "http" or registration.endpoint is None:
            return
        parsed = urlsplit(registration.endpoint)
        if self.endpoint_require_https and parsed.scheme != "https":
            raise AgentEndpointPolicyError("HTTP Agent endpoints must use HTTPS")
        hostname = parsed.hostname or ""
        if self.endpoint_allowed_hosts and not any(
            fnmatch(hostname, pattern) for pattern in self.endpoint_allowed_hosts
        ):
            raise AgentEndpointPolicyError(f"Agent endpoint host {hostname} is not allowed")

    @staticmethod
    def _evaluate(agent: AgentRecord, selector: AgentSelector) -> RouteCandidate:
        reasons: list[str] = []
        routable = {AgentStatus.online}
        if selector.allow_degraded:
            routable.add(AgentStatus.degraded)
        if agent.status not in routable:
            reasons.append(f"status {agent.status} is not routable")
        missing_capabilities = sorted(set(selector.required_capabilities) - set(agent.capabilities))
        if missing_capabilities:
            reasons.append(f"missing capabilities: {', '.join(missing_capabilities)}")
        missing_permissions = sorted(set(selector.required_permissions) - set(agent.permissions))
        if missing_permissions:
            reasons.append(f"missing permissions: {', '.join(missing_permissions)}")
        if selector.transport and agent.transport != selector.transport:
            reasons.append(f"transport {agent.transport} does not match {selector.transport}")
        if agent.id in selector.exclude_agent_ids:
            reasons.append("agent is explicitly excluded")
        metadata_mismatches = sorted(
            key for key, value in selector.metadata_equals.items() if agent.metadata.get(key) != value
        )
        if metadata_mismatches:
            reasons.append(f"metadata does not match: {', '.join(metadata_mismatches)}")
        if reasons:
            return RouteCandidate(
                agent_id=agent.id,
                eligible=False,
                status=agent.status,
                load=agent.load,
                consecutive_failures=agent.consecutive_failures,
                reasons=reasons,
            )
        status_score = {
            AgentStatus.online: 0.0,
            AgentStatus.busy: 100.0,
            AgentStatus.degraded: 200.0,
        }[agent.status]
        score = status_score + (agent.load * 10 if agent.load is not None else 11)
        score += min(agent.consecutive_failures, 100)
        return RouteCandidate(
            agent_id=agent.id,
            eligible=True,
            status=agent.status,
            load=agent.load,
            consecutive_failures=agent.consecutive_failures,
            score=score,
            reasons=["all constraints satisfied"],
        )
