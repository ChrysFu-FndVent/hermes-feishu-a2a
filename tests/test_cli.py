from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hermes_a2a.cli import app

runner = CliRunner()


def test_init_creates_a_non_destructive_zero_credential_project(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--directory", str(tmp_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert sorted(payload["created"]) == [
        ".env",
        ".gitignore",
        "compose.yaml",
        "config/agents.yaml",
        "examples/capability-routing.yaml",
    ]
    assert "HERMES_INTERNAL_API_TOKEN=" in (tmp_path / ".env").read_text()
    assert "required_capabilities: [research]" in (
        tmp_path / "examples/capability-routing.yaml"
    ).read_text()
    assert "HERMES_INTERNAL_API_TOKEN" not in result.output

    second = runner.invoke(app, ["init", "--directory", str(tmp_path)])

    assert second.exit_code == 0
    assert json.loads(second.output)["preserved"] == payload["created"]


def test_validate_config_accepts_offline_project_and_supports_json(tmp_path: Path) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text("agents: []\n", encoding="utf-8")

    result = runner.invoke(app, ["validate-config", "--path", str(config), "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"ok": True, "agents": [], "errors": []}


def test_doctor_offline_has_stable_checks_and_skips_network(tmp_path: Path) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text("agents: []\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["doctor", "--offline", "--config", str(config), "--data-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["ok"] is True
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["python"]["status"] == "pass"
    assert checks["agent_config"]["status"] == "pass"
    assert checks["remote_health"]["status"] == "skip"
    assert checks["remote_registry"]["status"] == "skip"
