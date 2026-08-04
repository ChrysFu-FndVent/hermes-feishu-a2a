from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException

from .demo import DEMO_AGENT_IDS, _agent_output


def create_demo_agent(agent_id: str) -> FastAPI:
    if agent_id not in DEMO_AGENT_IDS:
        raise ValueError(f"unknown demo agent: {agent_id}")
    app = FastAPI(title=f"Hermes demo Agent: {agent_id}")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "agent_id": agent_id}

    @app.post("/execute")
    async def execute(payload: dict[str, Any]) -> dict[str, str]:
        task = payload.get("task")
        if not payload.get("run_id") or not isinstance(task, dict) or not task.get("id"):
            raise HTTPException(status_code=400, detail="run_id and task.id are required")
        if payload.get("attachments"):
            raise HTTPException(status_code=400, detail="the zero-credential demo rejects attachments")
        return {"output": _agent_output(agent_id)}

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bundled Hermes demonstration Agent")
    parser.add_argument("--agent-id", choices=DEMO_AGENT_IDS, required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    uvicorn.run(create_demo_agent(args.agent_id), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
