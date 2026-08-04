from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import typer
import uvicorn

from .config import Settings, load_agent_config
from .demo import DemoError, run_local_demo, run_remote_demo

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
def validate_config(path: Path = typer.Option(Path("config/agents.yaml"), exists=True)) -> None:
    settings = Settings()
    errors = settings.validate_for_production()
    try:
        agents = load_agent_config(path)
    except (OSError, ValueError) as exc:
        agents = []
        errors.append(str(exc))
    ids = [agent.id for agent in agents]
    if errors:
        for error in errors:
            typer.echo(f"ERROR: {error}")
        raise typer.Exit(1)
    typer.echo(json.dumps({"ok": True, "agents": ids}, ensure_ascii=False, indent=2))


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
