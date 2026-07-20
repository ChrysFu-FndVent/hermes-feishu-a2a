# Operations

## Local, VM and Docker deployment

Install Node 18 or newer on Linux, macOS or Windows, copy `.env.example` to `.env`, and run the test suite. For production, use Docker Compose or a process supervisor (systemd, launchd or Windows service), expose only an HTTPS reverse proxy, and inject secrets from a secret manager.

```bash
npm ci
npm test
npm run config:validate config/agents.json
node src/cli.js serve
```

## Health and recovery

`HealthMonitor` checks every registered agent on the configured interval. Supply a real `check(agent)` and `recover(agent, error)` callback from the worker adapter. Mark an agent unhealthy after a failed check, stop new assignments to it, retry only idempotent tasks, and escalate after the retry budget. Never retry a side-effecting task without an idempotency key.

## Troubleshooting

- **Bot receives no @:** verify the target app is in the group, the bot-mention receive scope is published, and the outbound payload is a `post` message with an `at` node, not plain `@Name` text.
- **Announcement read fails:** verify `im:chat.announcement:read`, use the `oc_...` chat ID, publish the new version, and refresh the tenant token.
- **401 webhook:** compare verification token/encrypt key with `.env`, ensure the reverse proxy preserves `X-Lark-*` headers, and reject stale requests.
- **Repeated tasks:** persist processed event/message IDs in a durable database before execution; the default in-memory set is for development only.
- **Agent unhealthy:** inspect network reachability, token expiry and worker adapter logs. Recovery should be bounded and observable.
