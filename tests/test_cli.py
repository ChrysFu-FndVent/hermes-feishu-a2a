from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from hermes_a2a.cli import app
from hermes_a2a.diagnostics import run_doctor

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
    assert "image: ghcr.io/chrysfu/hermes-feishu-a2a:0.4.2" in (
        tmp_path / "compose.yaml"
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


def test_validate_config_applies_production_endpoint_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text(
        """agents:
  - id: external
    display_name: External
    role: test
    endpoint: https://evil.net/execute
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_INTERNAL_API_TOKEN", "strong-internal-api-token-32-characters")
    monkeypatch.setenv("HERMES_AGENT_ENDPOINT_ALLOWED_HOSTS", "*.internal")

    result = runner.invoke(
        app, ["validate-config", "--path", str(config), "--production", "--json"]
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["errors"] == ["Agent endpoint host evil.net is not allowed"]


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


def _mock_doctor_client(
    monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport
) -> None:
    client_type = httpx.Client

    def client_factory(*args, **kwargs):
        return client_type(*args, **kwargs, transport=handler)

    monkeypatch.setattr("hermes_a2a.diagnostics.httpx.Client", client_factory)


def test_doctor_remote_checks_succeed_with_authenticated_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text("agents: []\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/agents":
            assert request.headers["X-Hermes-Token"] == "doctor-token"
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"status": "ok"})

    _mock_doctor_client(monkeypatch, httpx.MockTransport(handler))

    report = run_doctor(
        config_path=config,
        data_dir=tmp_path,
        offline=False,
        base_url="http://hermes.internal",
        token="doctor-token",
        timeout_seconds=0.5,
    )

    assert report.ok is True
    assert {check.name: check.status for check in report.checks} == {
        "python": "pass",
        "agent_config": "pass",
        "data_directory": "pass",
        "remote_health": "pass",
        "remote_readiness": "pass",
        "remote_registry": "pass",
    }


def test_doctor_remote_timeout_is_a_bounded_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text("agents: []\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    _mock_doctor_client(monkeypatch, httpx.MockTransport(handler))

    report = run_doctor(
        config_path=config,
        data_dir=tmp_path,
        offline=False,
        base_url="http://hermes.internal",
        token="doctor-token",
        timeout_seconds=0.1,
    )

    checks = {check.name: check for check in report.checks}
    assert report.ok is False
    assert checks["remote_health"].status == "fail"
    assert "timed out" in checks["remote_health"].message


def test_doctor_remote_invalid_token_fails_only_identity_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text("agents: []\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/agents":
            return httpx.Response(401, json={"detail": "invalid internal token"})
        return httpx.Response(200, json={"status": "ok"})

    _mock_doctor_client(monkeypatch, httpx.MockTransport(handler))

    report = run_doctor(
        config_path=config,
        data_dir=tmp_path,
        offline=False,
        base_url="http://hermes.internal",
        token="invalid-token",
        timeout_seconds=0.5,
    )

    checks = {check.name: check for check in report.checks}
    assert report.ok is False
    assert checks["remote_health"].status == "pass"
    assert checks["remote_readiness"].status == "pass"
    assert checks["remote_registry"].status == "fail"
    assert "401" in checks["remote_registry"].message


def test_doctor_applies_local_endpoint_policy(tmp_path: Path) -> None:
    config = tmp_path / "agents.yaml"
    config.write_text(
        """agents:
  - id: insecure
    display_name: Insecure
    role: test
    endpoint: http://agent.internal/execute
""",
        encoding="utf-8",
    )

    report = run_doctor(
        config_path=config,
        data_dir=tmp_path,
        offline=True,
        base_url=None,
        token=None,
        timeout_seconds=0.5,
        endpoint_allowed_hosts=["*.internal"],
        endpoint_require_https=True,
    )

    checks = {check.name: check for check in report.checks}
    assert report.ok is False
    assert checks["agent_config"].status == "fail"
    assert checks["agent_config"].message == "HTTP Agent endpoints must use HTTPS"
