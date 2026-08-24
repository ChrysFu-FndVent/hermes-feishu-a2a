# Changelog

## 0.4.0 - 2026-08-24

- Added declarative and runtime Agent registration ownership with revisions, timestamps,
  authenticated CRUD, lifecycle audit events and desired-state reconciliation.
- Added deterministic capability, permission, transport and metadata routing with per-candidate
  explanations and persisted route decisions.
- Added optional Agent endpoint host allowlisting, HTTPS enforcement and unsafe URL rejection.
- Added non-destructive `init`, offline/connected `doctor` and JSON configuration validation.
- Extended the zero-credential CLI and Compose demonstrations to prove capability routing and the
  runtime registry lifecycle.

## 0.3.0 - 2026-08-04

- Added a deterministic `hermes-a2a demo` command that runs a real local HTTP Agent workflow with
  temporary state and no Feishu credentials or external services.
- Added a Docker Compose demonstration with bundled researcher and reviewer Agents.
- Added macOS, Windows and Linux CLI demo coverage plus a Linux Compose smoke test.

## 0.2.0 - 2026-07-20

- Added bounded Feishu message-resource and Drive file downloads.
- Added PDF, DOCX and text extraction with file size, type and character limits.
- Added deterministic file-message routing to a configured intake Agent.
- Added duplicate-event and bot-loop protection plus result replies in Feishu.

## 0.1.2 - 2026-07-20

- Added native install and test coverage for macOS, Windows and Linux.
- Fixed Agent config preloading, Feishu request signing, post encoding and asynchronous results.
- Replaced deployment instructions and examples with platform-neutral, executable guidance.
- Removed internal incident notes, named-team templates and README generation tooling.

## 0.1.1 - 2026-07-20

- Expanded API, setup and deployment guidance.
- Fixed the GitHub Container Registry namespace so multi-platform images publish under the correct account owner.
- Centralized the API-reported version on the package `__version__` value.

## 0.1.0 - 2026-07-19

- Initial release of the Hermes coordinator.
- Added Agent registry, heartbeats, health sweep and role/capability metadata.
- Added serial and dependency-aware parallel workflow execution with retries.
- Added signed Feishu webhook ingress, token client and native mention posts.
- Added SQLite persistence boundary, CLI validation, Docker deployment and examples.
- Added Feishu permission and operations documentation.
