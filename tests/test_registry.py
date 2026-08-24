from __future__ import annotations

from pathlib import Path

import pytest

from hermes_a2a.models import AgentRegistration, AgentSelector, AgentStatus, Heartbeat
from hermes_a2a.registry import (
    AgentEndpointPolicyError,
    AgentOwnershipError,
    AgentRegistry,
    AgentRevisionConflict,
)
from hermes_a2a.store import Store


def registration(agent_id: str = "researcher") -> AgentRegistration:
    return AgentRegistration(
        id=agent_id,
        display_name="Research Agent",
        role="research",
        capabilities=["research", "writing"],
        endpoint="https://research.internal/execute",
    )


def test_runtime_registration_is_versioned_and_restored(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'registry.db'}"
    first_store = Store(database_url)
    created = AgentRegistry(first_store).register_runtime(registration())

    assert created.managed_by == "runtime"
    assert created.revision == 1
    first_store.close()

    restored_store = Store(database_url)
    restored = AgentRegistry(restored_store).get("researcher")

    assert restored == created
    restored_store.close()


def test_declarative_ownership_and_runtime_lifecycle_are_audited(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'lifecycle.db'}")
    registry = AgentRegistry(store)
    declared = registry.register_declarative(registration("declared"))

    assert declared.managed_by == "declarative"
    with pytest.raises(AgentOwnershipError, match="declarative"):
        registry.register_runtime(registration("declared"))

    created = registry.register_runtime(registration("runtime"))
    replacement = registration("runtime").model_copy(update={"display_name": "Updated Agent"})
    updated = registry.update_runtime("runtime", replacement)
    deleted = registry.delete_runtime("runtime")

    assert created.revision == 1
    assert updated.display_name == "Updated Agent"
    assert updated.revision == 2
    assert deleted == updated
    assert registry.get("runtime") is None
    assert [event.action for event in registry.history("runtime")] == [
        "registered",
        "updated",
        "deleted",
    ]
    store.close()


def test_route_selects_best_eligible_agent_and_explains_rejections(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'routing.db'}")
    registry = AgentRegistry(store)
    registry.register_runtime(registration("loaded"))
    registry.register_runtime(registration("available"))
    registry.register_runtime(
        registration("missing-capability").model_copy(
            update={"capabilities": ["research"]}
        )
    )
    registry.heartbeat("loaded", Heartbeat(status=AgentStatus.online, load=0.9))
    registry.heartbeat("available", Heartbeat(status=AgentStatus.online, load=0.1))
    registry.heartbeat(
        "missing-capability", Heartbeat(status=AgentStatus.online, load=0.0)
    )

    decision = registry.route(
        AgentSelector(required_capabilities=["research", "writing"])
    )

    assert decision.selected_agent_id == "available"
    assert "available" in decision.explanation
    candidates = {candidate.agent_id: candidate for candidate in decision.candidates}
    assert candidates["available"].eligible is True
    assert candidates["loaded"].eligible is True
    assert candidates["missing-capability"].eligible is False
    assert candidates["missing-capability"].reasons == ["missing capabilities: writing"]
    store.close()


def test_route_returns_an_explanation_when_no_agent_matches(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'no-route.db'}")
    registry = AgentRegistry(store)
    registry.register_runtime(registration())

    decision = registry.route(AgentSelector(required_capabilities=["coding"]))

    assert decision.selected_agent_id is None
    assert decision.explanation == "no eligible Agent matched the selector"
    assert decision.candidates[0].reasons == [
        "status offline is not routable",
        "missing capabilities: coding",
    ]
    store.close()


def test_endpoint_policy_restricts_runtime_dispatch_targets(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'endpoint-policy.db'}")
    registry = AgentRegistry(
        store,
        endpoint_allowed_hosts=["*.internal", "localhost"],
        endpoint_require_https=True,
    )

    registry.register_runtime(registration())
    with pytest.raises(AgentEndpointPolicyError, match="not allowed"):
        registry.register_runtime(
            registration("external").model_copy(
                update={"endpoint": "https://unapproved.example/execute"}
            )
        )
    with pytest.raises(AgentEndpointPolicyError, match="HTTPS"):
        registry.register_runtime(
            registration("insecure").model_copy(
                update={"endpoint": "http://localhost:9000/execute"}
            )
        )
    store.close()


def test_declarative_sync_removes_only_stale_declarative_records(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'sync.db'}")
    registry = AgentRegistry(store)
    registry.register_declarative(registration("stale"))
    registry.register_runtime(registration("runtime"))

    synced = registry.sync_declarative([registration("declared")])

    assert [agent.id for agent in synced] == ["declared"]
    assert registry.get("stale") is None
    assert registry.get("runtime") is not None
    assert registry.get("declared").managed_by == "declarative"
    assert registry.history("stale")[-1].action == "deleted"
    store.close()


def test_runtime_update_rejects_a_stale_revision(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'revision.db'}")
    registry = AgentRegistry(store)
    registry.register_runtime(registration())
    registry.update_runtime("researcher", registration(), expected_revision=1)

    with pytest.raises(AgentRevisionConflict, match="expected revision 1, current revision 2"):
        registry.update_runtime("researcher", registration(), expected_revision=1)
    store.close()
