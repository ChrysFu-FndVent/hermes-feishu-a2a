# Hermes Feishu A2A

Hermes Feishu A2A is a self-hostable coordination service for running a small,
auditable AI-agent team inside a Feishu group. Hermes is the group brain and lead:
it decomposes goals, dispatches work, tracks heartbeats, handles retries and
timeouts, and synthesizes the final result. Agent implementations remain
independent; this project only owns routing and workflow state.

## Why this project exists

The hard part of a Feishu agent team is not another prompt. It is identity and
delivery discipline. A model must never use a default CLI profile to send a
message under another bot's identity, an offline agent must not silently disappear,
and an orchestration reply must be distinguishable from progress output. This
project makes those boundaries explicit:

- one registration record per Agent, including `app_id`/`open_id`, role and scope;
- signed webhook ingress and an allow-list of Feishu chat IDs;
- HTTP or Feishu-post dispatch adapters, with no hard-coded local credentials;
- serial and dependency-aware parallel workflows;
- retries, deadlines, degraded/offline health states and durable run records;
- one final result path, with direct Agent message sending disabled by policy.

## Quick start

```bash
cd hermes-feishu-a2a
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
cp .env.example .env
cp config/agents.example.yaml config/agents.yaml
hermes-a2a validate-config --path config/agents.yaml
hermes-a2a serve
```

The service starts at `http://localhost:8080`. Set `HERMES_INTERNAL_API_TOKEN`
and send it as `X-Hermes-Token` for registration and workflow APIs.

```bash
curl http://localhost:8080/healthz
curl -H 'X-Hermes-Token: replace-with-a-long-random-token' http://localhost:8080/agents
```

## Architecture

```text
Feishu event subscription ---> /webhooks/feishu ---> Coordinator (Hermes)
                                                        |
                           +----------------------------+-------------------+
                           |                                                |
                    Agent registry / health                         Workflow engine
                           |                                      serial or parallel DAG
                           +----------------------------+-------------------+
                                                        |
                          HTTP callback or Feishu post adapter ---> Agents
                                                        |
                          /events/agent-result <---------+  (optional callback)
```

The transport is deliberately an interface. A production deployment can replace
the in-memory/HTTP adapter with an internal queue, while the API and workflow
engine remain unchanged.

## Configuration

All settings are environment variables prefixed with `HERMES_`; see
[`.env.example`](.env.example) and [`config/agents.example.yaml`](config/agents.example.yaml).
Never commit `app_secret`, `encrypt_key`, access tokens, or a real internal token.

Important values:

| Variable | Purpose |
| --- | --- |
| `HERMES_FEISHU_APP_ID` | Hermes coordinator app ID (`cli_...`) |
| `HERMES_FEISHU_APP_SECRET` | Hermes app secret, stored only in the deployment secret manager |
| `HERMES_FEISHU_ENCRYPT_KEY` | Event payload decryption key when encrypted events are enabled |
| `HERMES_FEISHU_VERIFICATION_TOKEN` | Webhook HMAC verification token |
| `HERMES_FEISHU_ALLOWED_CHAT_IDS` | Comma-separated `oc_...` allow-list |
| `HERMES_FEISHU_OWNER_OPEN_IDS` | Human owner IDs allowed to initiate workflows |
| `HERMES_INTERNAL_API_TOKEN` | Protects agent registration and workflow APIs |
| `HERMES_SECRET_ENCRYPTION_KEY` | Optional Fernet key for locally persisted secrets |

## Agent contract

An Agent registers with `POST /agents` and heartbeats at least every two minutes.
The coordinator treats two missed heartbeats as offline. A failed dispatch moves
the Agent to `degraded`, retries according to the task policy, and records the
failure in the run state.

```json
{
  "id": "codex",
  "display_name": "CodeX",
  "role": "code implementation and delivery",
  "capabilities": ["coding", "review", "build"],
  "transport": "http",
  "endpoint": "https://codex.internal/agent",
  "permissions": ["task:execute", "result:write"]
}
```

The HTTP endpoint receives `{run_id, task}` and returns `{output}`. Feishu-only
Agents use `transport: feishu`, an `open_id`, and `metadata.chat_id`; Hermes sends
a structured native `at` post. They should return results to Hermes through the
callback endpoint or the configured connector, never through a second CLI sender.

## Feishu developer-console setup

1. Create one Hermes app and one app/bot per Agent in the Feishu developer console.
2. Add each bot to the target group. A bot that is not a member cannot reply to
   the group, even when its scopes are correct.
3. Enable event subscription and choose the long-connection or HTTPS callback
   mode appropriate to the deployment. For HTTPS, point the callback at
   `/webhooks/feishu` and configure the verification token/encryption key.
4. Subscribe to `im.message.receive_v1` for inbound group messages. Filter by
   `chat_id`, sender type and native `mentions`; do not infer identity from a
   display-name string.
5. Grant only the scopes required by each app. A coordinator normally needs
   message read/send and chat read; an Agent should receive the smallest set that
   matches its role.
6. Publish the app, test in a disposable group, and rotate any development secret
   before production.

See [`docs/feishu-permissions.md`](docs/feishu-permissions.md) for the detailed
scope matrix, webhook checklist and failure codes.

## Group initialization

Use [`config/group-announcement.md`](config/group-announcement.md) as the pinned
announcement. It fixes the role model: Hermes is the brain and lead; CodeX,
Qoder and WorkBuddy are execution specialists. The rule that matters most is
delivery ownership: only the connector sends the final response for an Agent.

## Workflows

Workflow YAML files in `examples/` show serial and parallel execution. The engine
honors `depends_on`, `timeout_seconds`, and `retries`; parallel mode runs all ready
tasks concurrently while preserving dependency barriers. A run is complete only
when all required tasks are successful or explicitly skipped due to a failed
dependency.

## Deployment

### Docker

```bash
docker compose up --build -d
docker compose logs -f hermes
```

The compose file mounts `./data` for SQLite. For production, use a managed
PostgreSQL store by implementing the `Store` boundary, place the service behind
TLS, and inject secrets from the platform secret manager.

### macOS/Linux/Windows

The Python service is OS-neutral. Use Python 3.11+, a process manager (systemd,
launchd, or Windows Service), and an HTTPS reverse proxy. The Feishu API domain
and app credentials are the only platform-specific pieces.

## Examples and operations

- Content review: policy, language and technical checks in parallel.
- Data analysis: gather, model, then independently review in serial order.
- Multi-agent Q&A: Hermes plans, WorkBuddy researches, CodeX implements, Qoder runs checks.

See [`docs/best-practices.md`](docs/best-practices.md) and
[`docs/troubleshooting.md`](docs/troubleshooting.md) for operational guidance.
The identity failure that led to the connector-only delivery rule is documented
in [`docs/identity-boundary-postmortem.md`](docs/identity-boundary-postmortem.md).

## Security model

- Raw webhook bytes are authenticated before JSON parsing.
- Allowed chats and owner IDs are explicit configuration, not name matching.
- Internal APIs require a separate token and should be network-restricted.
- Secrets are represented as `SecretStr`, redacted in logs, and can be encrypted
  with Fernet before local persistence.
- No example contains a real Feishu app secret or token.
- The default group policy forbids direct Agent message sends, preventing content
  generated by one Agent from being published under another app profile.

## Development

```bash
pip install -e '.[dev]'
ruff check .
pytest
python scripts/check_secrets.py
```

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request. The
project is MIT-licensed; see [`LICENSE`](LICENSE).
