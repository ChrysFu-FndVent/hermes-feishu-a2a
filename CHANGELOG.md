# Changelog

## 0.1.1 - 2026-07-20

- Reworked the README with animated project messaging, Mermaid diagrams, API and role references, and expanded setup guidance.
- Fixed the GitHub Container Registry namespace so multi-platform images publish under the correct account owner.
- Centralized the API-reported version on the package `__version__` value.

## 0.1.0 - 2026-07-19

- Initial release of the Hermes coordinator.
- Added Agent registry, heartbeats, health sweep and role/capability metadata.
- Added serial and dependency-aware parallel workflow execution with retries.
- Added signed Feishu webhook ingress, token client and native mention posts.
- Added SQLite persistence boundary, CLI validation, Docker deployment and examples.
- Added identity-boundary, permissions and group-announcement documentation.
