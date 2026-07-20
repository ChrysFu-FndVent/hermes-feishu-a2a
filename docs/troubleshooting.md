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

Normal text events require an integration adapter because the coordinator does not
include a natural-language planner. For file events, set
`HERMES_FEISHU_FILE_INTAKE_AGENT_ID`, register that Agent, and send its online
heartbeat. The setting must match the Agent ID exactly and the Agent must have
`attachment:read` permission.

## A Feishu file cannot be read

- A direct message attachment requires the `im:resource` scope.
- A URL with `/file/{token}` requires the application-identity scope
  `drive:file:download` (or the broader `drive:drive:readonly`) and file access for the
  app identity.
- Publish a new app version and obtain tenant approval after adding scopes.
- Supported formats are PDF, DOCX, TXT, Markdown, CSV and JSON by default.
- Image-only PDFs have no extractable text and require an external OCR adapter.
- Inspect the task error through `GET /runs/{run_id}`; download and parser failures
  include the actionable scope, size or format reason.

## An Agent remains offline

Agent records loaded from `config/agents.yaml` start offline. The Agent adapter must
send `POST /agents/{id}/heartbeat` with `status: online` and the internal token.

## A Feishu task times out

Confirm that the Agent received the native `at` post and that its adapter called
`POST /events/agent-result` with the exact `run_id`, `task_id` and assigned `agent_id`,
or replied in the task message thread from its registered `open_id`. Late, unrelated
or identity-mismatched replies cannot complete the pending task.

## A workflow is stuck or fails

Inspect `/runs/{run_id}` and `/metrics`. Check Agent heartbeats, dependency IDs,
endpoint reachability, timeout settings and retry counts. A dependency cycle fails
when no pending task can become ready.
