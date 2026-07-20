from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from .config import Settings, load_agent_config

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
