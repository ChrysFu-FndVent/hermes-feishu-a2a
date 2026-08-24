# Registry and routing refresh

## Confirmed outcome

- Add declarative and persistent runtime Agent registration ownership.
- Add authenticated runtime create, read, update, delete, and audit interfaces.
- Add deterministic capability and constraint matching with an inspectable route decision.
- Preserve explicit `agent_id` workflows and existing endpoints.
- Add project initialization, configuration validation, and local/remote diagnostics to the CLI.
- Keep Feishu, model providers, and observability systems optional; keep the zero-credential demo.
- Keep the bilingual README synchronized with executable examples.

## Public seams

1. `AgentRegistry`: registration lifecycle, status, audit history, and route decisions.
2. HTTP control interface: authenticated Agent CRUD, route preview, and audit retrieval.
3. CLI: `init`, `validate-config`, and `doctor` commands.

## Compatibility and security

- Existing records without ownership metadata load as runtime registrations.
- Existing `POST /agents`, heartbeat, explicit workflow assignment, and config files remain valid.
- Declarative registrations cannot be mutated or deleted through runtime control endpoints.
- HTTP Agent endpoints reject embedded credentials and support an optional host allowlist.
- Route decisions are deterministic and persist with task results.

## Acceptance

- New behavior is covered through the three public seams above.
- Ruff, strict mypy, secret scan, all tests, Python 3.11-3.14, macOS/Windows/Linux CLI,
  zero-credential Compose, package build, and multi-architecture image checks pass.
- Changes land through a pull request and publish the next minor SemVer release after merge.
