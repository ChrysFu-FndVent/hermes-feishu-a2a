from __future__ import annotations

import os
import platform
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .config import load_agent_config
from .registry import validate_agent_endpoints


class DiagnosticCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail", "skip"]
    message: str
    hint: str = ""
    elapsed_ms: float = Field(ge=0)


class DoctorReport(BaseModel):
    ok: bool
    checks: list[DiagnosticCheck]


def run_doctor(
    *,
    config_path: Path,
    data_dir: Path,
    offline: bool,
    base_url: str | None,
    token: str | None,
    timeout_seconds: float,
    endpoint_allowed_hosts: list[str] | None = None,
    endpoint_require_https: bool = False,
) -> DoctorReport:
    checks = [
        _timed("python", _check_python),
        _timed(
            "agent_config",
            lambda: _check_agent_config(
                config_path, endpoint_allowed_hosts, endpoint_require_https
            ),
        ),
        _timed("data_directory", lambda: _check_data_directory(data_dir)),
    ]
    if offline:
        checks.extend(
            [
                _skip("remote_health", "offline mode; network check skipped"),
                _skip("remote_readiness", "offline mode; network check skipped"),
                _skip("remote_registry", "offline mode; network check skipped"),
            ]
        )
    elif base_url is None:
        checks.extend(
            [
                _skip("remote_health", "no --base-url was provided"),
                _skip("remote_readiness", "no --base-url was provided"),
                _skip("remote_registry", "no --base-url was provided"),
            ]
        )
    else:
        checks.extend(_remote_checks(base_url, token, timeout_seconds))
    return DoctorReport(ok=not any(check.status == "fail" for check in checks), checks=checks)


CheckResult = tuple[Literal["pass", "warn", "fail", "skip"], str, str]


def _timed(name: str, check: Callable[[], CheckResult]) -> DiagnosticCheck:
    started = perf_counter()
    status, message, hint = check()
    return DiagnosticCheck(
        name=name,
        status=status,
        message=message,
        hint=hint,
        elapsed_ms=(perf_counter() - started) * 1000,
    )


def _check_python() -> CheckResult:
    version = platform.python_version()
    supported = tuple(map(int, platform.python_version_tuple()[:2])) >= (3, 11)
    return (
        "pass" if supported else "fail",
        f"Python {version}",
        "Install Python 3.11 or later." if not supported else "",
    )


def _check_agent_config(
    path: Path,
    endpoint_allowed_hosts: list[str] | None,
    endpoint_require_https: bool,
) -> CheckResult:
    try:
        agents = load_agent_config(path)
    except (OSError, ValueError) as exc:
        return "fail", str(exc), "Fix the Agent registry YAML and rerun validate-config."
    errors = validate_agent_endpoints(
        agents,
        endpoint_allowed_hosts=endpoint_allowed_hosts,
        endpoint_require_https=endpoint_require_https,
    )
    if errors:
        return "fail", errors[0], "Fix the Agent endpoint policy and rerun validate-config."
    return "pass", f"loaded {len(agents)} Agent registrations", ""


def _check_data_directory(path: Path) -> CheckResult:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    writable = probe.is_dir() and os.access(probe, os.W_OK)
    return (
        "pass" if writable else "fail",
        f"writable parent: {probe}" if writable else f"not writable: {probe}",
        "Choose a writable HERMES_DATABASE_URL directory." if not writable else "",
    )


def _skip(name: str, message: str) -> DiagnosticCheck:
    return DiagnosticCheck(name=name, status="skip", message=message, elapsed_ms=0)


def _remote_checks(
    base_url: str, token: str | None, timeout_seconds: float
) -> list[DiagnosticCheck]:
    headers = {"X-Hermes-Token": token} if token else {}
    checks: list[DiagnosticCheck] = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds) as client:
        checks.append(_http_check(client, "remote_health", "/healthz"))
        checks.append(_http_check(client, "remote_readiness", "/readyz"))
        if token:
            checks.append(_http_check(client, "remote_registry", "/agents", headers=headers))
        else:
            checks.append(
                DiagnosticCheck(
                    name="remote_registry",
                    status="warn",
                    message="token not provided; authenticated registry check skipped",
                    hint="Set HERMES_INTERNAL_API_TOKEN in the environment.",
                    elapsed_ms=0,
                )
            )
    return checks


def _http_check(
    client: httpx.Client, name: str, path: str, headers: dict[str, str] | None = None
) -> DiagnosticCheck:
    started = perf_counter()
    try:
        response = client.get(path, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return DiagnosticCheck(
            name=name,
            status="fail",
            message=str(exc),
            hint="Check the URL, service logs, token, and endpoint policy.",
            elapsed_ms=(perf_counter() - started) * 1000,
        )
    return DiagnosticCheck(
        name=name,
        status="pass",
        message=f"HTTP {response.status_code}",
        elapsed_ms=(perf_counter() - started) * 1000,
    )
