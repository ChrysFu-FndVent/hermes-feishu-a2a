from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import typer
import uvicorn

from .config import Settings, load_agent_config
from .demo import DemoError, run_local_demo, run_remote_demo
from .diagnostics import run_doctor
from .registry import validate_agent_endpoints
from .scaffold import initialize_project

app = typer.Typer(help="Hermes Feishu A2A coordinator tools")


@app.command("serve")
def serve(host: str | None = None, port: int | None = None) -> None:
    settings = Settings()
    uvicorn.run(
        "hermes_a2a.api:create_app",
        host=host or settings.host,
        port=port or settings.port,
        log_level=settings.log_level.lower(),
        factory=True,
    )


@app.command("validate-config")
def validate_config(
    path: Path = typer.Option(Path("config/agents.yaml"), exists=True),
    production: bool = typer.Option(False, help="Also require production Feishu credentials."),
    json_output: bool = typer.Option(False, "--json", help="Emit a stable JSON result."),
) -> None:
    settings = Settings()
    errors = settings.validate_for_production() if production else []
    try:
        agents = load_agent_config(path)
    except (OSError, ValueError) as exc:
        agents = []
        errors.append(str(exc))
    errors.extend(
        validate_agent_endpoints(
            agents,
            endpoint_allowed_hosts=settings.agent_endpoint_allowed_hosts,
            endpoint_require_https=settings.agent_endpoint_require_https,
        )
    )
    ids = [agent.id for agent in agents]
    result = {"ok": not errors, "agents": ids, "errors": errors}
    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        if errors:
            raise typer.Exit(1)
        return
    if errors:
        for error in errors:
            typer.echo(f"ERROR: {error}")
        raise typer.Exit(1)
    typer.echo(json.dumps({"ok": True, "agents": ids}, ensure_ascii=False, indent=2))


@app.command("init")
def init_project(
    directory: Path = typer.Option(Path("."), file_okay=False),
    force: bool = typer.Option(False, help="Replace files created by this command."),
) -> None:
    """Create a zero-credential, self-hosted Hermes project."""
    result = initialize_project(directory.resolve(), force=force)
    typer.echo(result.model_dump_json(indent=2))


@app.command("doctor")
def doctor(
    config: Path = typer.Option(Path("config/agents.yaml")),
    data_dir: Path = typer.Option(Path("data"), file_okay=False),
    offline: bool = typer.Option(False, help="Skip all network checks."),
    base_url: str | None = typer.Option(None, help="Running Hermes base URL."),
    timeout_seconds: float = typer.Option(5, min=0.1, max=30),
) -> None:
    """Run read-only local and optional remote diagnostics."""
    settings = Settings()
    report = run_doctor(
        config_path=config,
        data_dir=data_dir,
        offline=offline,
        base_url=base_url,
        token=settings.internal_api_token.get_secret_value() or None,
        timeout_seconds=timeout_seconds,
        endpoint_allowed_hosts=settings.agent_endpoint_allowed_hosts,
        endpoint_require_https=settings.agent_endpoint_require_https,
    )
    typer.echo(report.model_dump_json(indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command("demo")
def demo(
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Bundled Compose Hermes URL; omit it to run an isolated local demonstration.",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="HERMES_DEMO_TOKEN",
        help="Bundled Compose demo token. It is not a production credential.",
    ),
    timeout_seconds: float = typer.Option(20, min=1, max=120),
) -> None:
    """Run a deterministic multi-Agent workflow without Feishu credentials."""
    try:
        if base_url:
            if token is None:
                raise DemoError("--token or HERMES_DEMO_TOKEN is required with --base-url")
            result = asyncio.run(run_remote_demo(base_url, token, timeout_seconds))
        else:
            result = asyncio.run(run_local_demo(timeout_seconds))
    except (DemoError, httpx.HTTPError, OSError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
