from __future__ import annotations

from pathlib import Path

import pytest

from hermes_a2a.config import Settings, load_agent_config
from hermes_a2a.models import AgentRegistration


def test_production_settings_reject_placeholders() -> None:
    errors = Settings(
        env="production",
        internal_api_token="replace-with-token",
        feishu_app_id="cli_xxx",
        feishu_app_secret="replace-me",
        feishu_encrypt_key="replace-me",
        feishu_verification_token="replace-me",
        feishu_allowed_chat_ids=["oc_xxx"],
        feishu_owner_open_ids=["ou_xxx"],
    ).validate_for_production()

    assert len(errors) == 8


def test_production_settings_allow_http_only_deployment_without_feishu() -> None:
    errors = Settings(
        env="production",
        internal_api_token="strong-internal-api-token-32-characters",
        agent_endpoint_allowed_hosts=["*.internal"],
    ).validate_for_production()

    assert errors == []


def test_agent_config_rejects_placeholder_targets(tmp_path: Path) -> None:
    path = tmp_path / "agents.yaml"
    path.write_text(
        """agents:
  - id: engineer
    display_name: Engineering Agent
    role: coding
    transport: http
    endpoint: https://engineer.example.internal/agent
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="placeholder transport values"):
        load_agent_config(path)


def test_settings_parse_comma_separated_allow_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_FEISHU_ALLOWED_CHAT_IDS", "oc_one,oc_two")
    monkeypatch.setenv("HERMES_FEISHU_OWNER_OPEN_IDS", "ou_one,ou_two")

    settings = Settings(_env_file=None)

    assert settings.feishu_allowed_chat_ids == ["oc_one", "oc_two"]
    assert settings.feishu_owner_open_ids == ["ou_one", "ou_two"]


def test_agent_config_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "agents.yaml"
    path.write_text(
        """agents:
  - id: engineer
    display_name: Engineering Agent
    role: coding
    endpoint: https://first.internal/agent
  - id: engineer
    display_name: Duplicate Agent
    role: coding
    endpoint: https://second.internal/agent
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="agent ids must be unique"):
        load_agent_config(path)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user:password@agent.internal/execute",
        "https://agent.internal/execute#secret-fragment",
    ],
)
def test_agent_registration_rejects_unsafe_endpoint_parts(endpoint: str) -> None:
    with pytest.raises(ValueError, match="credentials or fragments"):
        AgentRegistration(
            id="unsafe",
            display_name="Unsafe",
            role="test",
            endpoint=endpoint,
        )


def test_agent_capabilities_and_permissions_are_normalized() -> None:
    registration = AgentRegistration(
        id="normalized",
        display_name="Normalized",
        role="test",
        capabilities=[" Research ", "research", "WRITING"],
        permissions=[" Task:Execute ", "task:execute"],
        endpoint="https://agent.internal/execute",
    )

    assert registration.capabilities == ["research", "writing"]
    assert registration.permissions == ["task:execute"]
