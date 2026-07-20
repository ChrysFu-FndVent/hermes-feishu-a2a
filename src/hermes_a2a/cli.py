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
        factory=True,
    )


@app.command("validate-config")
def validate_config(path: Path = typer.Option(Path("config/agents.yaml"), exists=True)) -> None:
    settings = Settings()
    errors = settings.validate_for_production()
    agents = load_agent_config(path)
    ids = [str(item.get("id", "")) for item in agents]
    if len(ids) != len(set(ids)):
        raise typer.BadParameter("agent ids must be unique")
    if errors:
        for error in errors:
            typer.echo(f"ERROR: {error}")
        raise typer.Exit(1)
    typer.echo(json.dumps({"ok": True, "agents": ids}, ensure_ascii=False, indent=2))


@app.command("init-group")
def init_group(output: Path = typer.Option(Path("group-announcement.md"))) -> None:
    template = Path(__file__).parents[2] / "config" / "group-announcement.md"
    output.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    typer.echo(f"wrote {output}")
