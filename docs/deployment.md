# Deployment guide

Complete the configuration and validation steps in the README before using any of
these deployment paths.

## Native Python

The package supports Python 3.11 or newer on macOS, Windows and Linux. Use the
platform-specific virtual environment commands in the README and run the executable
from that environment without relying on shell activation.

For a long-running service, configure the operating system's normal process manager
to run `hermes-a2a serve` from the virtual environment:

- Linux: systemd or another supervised service manager.
- macOS: launchd or a supervised process manager.
- Windows: Task Scheduler, NSSM, or another service wrapper approved by the operator.

The repository does not install operating-system service definitions. Configure
restart policy, working directory, environment file and log collection explicitly.

## Docker

`docker compose up --build -d` starts the API with a health check. The Compose file
mounts `config/agents.yaml` read-only and stores SQLite data in the `hermes-data`
named volume.

Docker Desktop must use Linux containers on macOS and Windows. On Linux, Docker
Engine and the Compose v2 plugin are required.

Inspect the resolved configuration before startup:

```bash
docker compose config
```

Back up the data volume before upgrades. `docker compose down` preserves it;
`docker compose down --volumes` deletes it.

## Reverse proxy

Terminate TLS at Caddy, Nginx or a managed load balancer. Forward only
`/webhooks/feishu` from the public internet. Keep `/agents`, `/workflows`, `/runs`
and `/events/agent-result` on a private network and require `X-Hermes-Token`.

Set a request body limit and a short proxy timeout. Workflow execution is
asynchronous: the run endpoint returns a run ID immediately.

File intake requires outbound HTTPS access to the configured Feishu/Lark Open API
domain and to the selected HTTP Agent endpoint. It does not require a larger inbound
proxy body limit because files are downloaded from Feishu after the signed event is
accepted. Tune the `HERMES_FEISHU_FILE_*` limits for the container memory budget.

## Upgrade and rollback

1. Pin the wheel version, release tag or container digest.
2. Back up the SQLite database or persistent volume.
3. Start the new version in staging and verify `/readyz`.
4. Run one HTTP Agent task and one Feishu callback task.
5. Roll back the application and database snapshot together if persisted models
   become incompatible.
