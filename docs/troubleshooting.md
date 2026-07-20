# Troubleshooting

## Installation fails

Confirm Python 3.11 or newer with `python --version`. On Windows, use
`py -3.11` and the `.venv\Scripts\python.exe` commands from the README. On macOS or
Linux, use `.venv/bin/python`. Do not mix a system `pip` with the project virtual
environment.

## Configuration validation fails

Run `hermes-a2a validate-config --path config/agents.yaml` and address every reported
item. Placeholder values such as `replace-me`, `cli_xxx`, `oc_xxx` and `ou_xxx` are
rejected for production configuration.

HTTP Agents require an `endpoint`. Feishu Agents require both `open_id` and
`metadata.chat_id`.

## `/readyz` returns 503

The process is running, but required production settings are missing or still contain
placeholders. Inspect the JSON response for the exact variable names. Use `/healthz`
only as a process liveness check.

## Docker cannot write the database

Use the repository's named-volume Compose configuration. If a customized deployment
bind-mounts a host directory, make that directory writable by container UID `10001`.

## Feishu webhook returns 401

Verify that the app's encrypt key and verification token match `.env`. A reverse proxy
must forward the request body unchanged; signature verification happens before JSON
parsing.

## An event is accepted but no workflow starts

This is expected unless an integration adapter converts the event into a workflow API
request. The coordinator validates and exposes the Feishu ingress boundary but does
not include a natural-language planner.

## An Agent remains offline

Agent records loaded from `config/agents.yaml` start offline. The Agent adapter must
send `POST /agents/{id}/heartbeat` with `status: online` and the internal token.

## A Feishu task times out

Confirm that the Agent received the native `at` post and that its adapter called
`POST /events/agent-result` with the exact `run_id`, `task_id` and assigned `agent_id`.
Late or mismatched callbacks cannot complete the pending task.

## A workflow is stuck or fails

Inspect `/runs/{run_id}` and `/metrics`. Check Agent heartbeats, dependency IDs,
endpoint reachability, timeout settings and retry counts. A dependency cycle fails
when no pending task can become ready.
