from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import BaseModel, Field

from . import __version__


class InitResult(BaseModel):
    ok: bool = True
    created: list[str] = Field(default_factory=list)
    preserved: list[str] = Field(default_factory=list)


def initialize_project(directory: Path, *, force: bool = False) -> InitResult:
    directory.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    files = {
        ".env": _environment(token),
        ".gitignore": ".env\ndata/\n",
        "config/agents.yaml": "# Runtime Agents can also register through the authenticated API.\nagents: []\n",
        "examples/capability-routing.yaml": _workflow_example(),
        "compose.yaml": _compose_file(),
    }
    result = InitResult()
    for relative, content in files.items():
        target = directory / relative
        if target.exists() and not force:
            result.preserved.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        result.created.append(relative)
    return result


def _environment(token: str) -> str:
    return f"""HERMES_ENV=development
HERMES_HOST=127.0.0.1
HERMES_PORT=8080
HERMES_DATABASE_URL=sqlite:///./data/hermes.db
HERMES_INTERNAL_API_TOKEN={token}
HERMES_AGENTS_CONFIG_PATH=config/agents.yaml
HERMES_FEISHU_WEBHOOK_SIGNATURE_REQUIRED=false
"""


def _workflow_example() -> str:
    return """name: capability-routing
mode: serial
tasks:
  - id: research
    title: Gather evidence
    selector:
      required_capabilities: [research]
    prompt: Gather evidence and clearly distinguish facts from assumptions.
"""


def _compose_file() -> str:
    return f"""services:
  hermes:
    image: ghcr.io/chrysfu-fndvent/hermes-feishu-a2a:{__version__}
    env_file: .env
    environment:
      HERMES_HOST: 0.0.0.0
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - hermes-data:/app/data
      - ./config/agents.yaml:/app/config/agents.yaml:ro

volumes:
  hermes-data:
"""
