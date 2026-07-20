# Deployment guide

## Local

Use the Quick Start in the README, then run `pytest` and `hermes-a2a validate-config`.
Keep `.env` outside source control and use a disposable Feishu group for tests.

## Docker

`docker compose up --build` runs the API with a health check. Mount `./data` only
for development. Production deployments should use a persistent volume with
restricted permissions or a database implementation behind `Store`.

## Reverse proxy

Terminate TLS at Caddy, Nginx or a managed load balancer. Forward only
`/webhooks/feishu` from the public internet. Keep `/agents`, `/workflows` and
`/runs` on a private network or require the internal token plus network policy.
Set a request body limit and a short upstream timeout; the workflow engine is
asynchronous and returns a run ID immediately.

## Upgrades and rollback

1. Pin the image or package version.
2. Run migrations (if a custom persistent store is used) before switching traffic.
3. Run `/readyz` and a synthetic signed webhook in staging.
4. Roll back the image and database migration together if a workflow schema changes.

The public API is versioned by the project release. Add fields compatibly and do
not remove an Agent permission or task field without a migration note.
