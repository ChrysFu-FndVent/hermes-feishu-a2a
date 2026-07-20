# Changelog

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
