# Hermes Feishu A2A

Hermes Feishu A2A is an auditable reference implementation for using Hermes as the coordinator of a Feishu/Lark multi-agent workgroup. It turns the lessons from a real `AAA工作群` pilot into reusable code: agent registration, signed task envelopes, serial or parallel workflows, result aggregation, health checks, retries, and a least-privilege Feishu integration.

This repository contains no credentials and does not control vendor desktop applications. Each worker is an adapter with a stable contract: receive a task, execute it in its own runtime, report evidence, and optionally recover or retry. Hermes remains the only component that fans work out and delivers an accepted final result.

## Features

- `AgentRegistry` for roles, capabilities, Feishu `open_id` values and health state.
- `TaskStore` with explicit lifecycle transitions, attempts and audit events.
- `WorkflowRunner` for serial pipelines and parallel fan-out.
- HMAC-SHA256 envelopes with expiry, replay protection and constant-time verification.
- Feishu client for tenant tokens, native bot mentions and group-announcement blocks.
- HTTP webhook with challenge handling and signature validation hooks.
- Health monitor with recovery callback and bounded retry policy.
- Config generation/validation scripts, Docker image and cross-platform Node 18+ runtime.

## Quick start

```bash
cp .env.example .env
# Fill .env with the four Feishu credentials and a random A2A_SIGNING_SECRET.
npm test
npm run config:generate -- --force
npm run config:validate
npm start
```

The service listens on `http://127.0.0.1:8787` by default. Configure Feishu's event URL as `https://your-host.example/webhook/feishu`; expose only HTTPS in production. `/healthz` returns a safe operational snapshot without secrets.

## Team model

| Agent | Role | Responsibilities |
| --- | --- | --- |
| Hermes | `leader` | Intake, scope, delegation, acceptance, final summary |
| CodeX | `deputy` | Core execution, co-review, approved final delivery |
| Qoder | `member` | Implementation, local files, diagnostics, tests |
| WorkBuddy | `support` | Research, cross-checks, test gaps, workflow support |

Only Hermes normally fans out work. Workers report to the requester with task ID, status, completed work, evidence, risks and decisions needed. A worker's `succeeded` state is not an authorization to deliver to the human; Hermes acceptance and CodeX co-review are separate gates.

## Configuration

1. Copy `config/agents.example.json` to `config/agents.json` with `npm run config:generate -- --force`.
2. Replace every `oc_...` chat ID and `ou_...` bot open ID with values returned by Feishu APIs. The numeric ID in an announcement URL is not a valid Open API chat ID.
3. Keep role and capability assignments narrow. Use one signing secret per group and store it in a secret manager in production.
4. Run `npm run config:validate config/agents.json` before deployment.

The CLI automatically loads `config/agents.json` when it exists; embedding the same records through `createApplication({ agents })` is useful for tests and custom adapters.

See [`docs/permissions.md`](docs/permissions.md), [`docs/architecture.md`](docs/architecture.md), and [`docs/operations.md`](docs/operations.md) for platform setup, event subscriptions, deployment and incident handling.

## Feishu permissions

Every participating app must be added to the target group and separately configured in the Feishu developer console. Minimum pilot scopes are:

- `im:message` (send/read variants exposed by the tenant);
- `im:message.group_at_msg.include_bot:readonly` for native bot-to-bot @ delivery;
- `im:chat:readonly` and `im:chat.member:readonly` to verify membership;
- `im:chat.announcement:read` to read announcement document blocks;
- bot basic information for resolving `open_id`.

Publish a new app version after changing scopes. Details and console navigation are in [`docs/permissions.md`](docs/permissions.md).

## Workflows

```js
const { WorkflowRunner } = require('hermes-feishu-a2a');
const runner = new WorkflowRunner();
await runner.run({ mode: 'parallel', steps: [{ id: 'moderate-text' }, { id: 'moderate-image' }] }, { execute });
```

Runnable scenarios and demo payloads are in [`examples/`](examples/): content moderation, data analysis, and multi-agent Q&A.

## Docker

```bash
docker compose up --build -d
docker compose logs -f hermes
```

The image runs as the unprivileged `node` user with a read-only filesystem. Put an HTTPS reverse proxy in front and inject secrets through your deployment secret store.

## Security and compatibility

- Secrets belong in environment variables or a managed secret store, never Git or task bodies.
- Verify Feishu webhook signatures and reject stale/replayed event IDs.
- Verify every A2A envelope against its group secret, expiry, sender registry and current group membership.
- Use an explicit human allow-list for sensitive workflows and fail closed when membership cannot be checked.
- Node 18+ is supported on Linux, macOS and Windows; only standard Node modules are used.

## Development

```bash
npm test
node --check src/index.js
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CHANGELOG.md`](CHANGELOG.md). The project is MIT licensed.
