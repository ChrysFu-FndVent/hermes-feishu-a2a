# Contributing

Thanks for contributing to Hermes Feishu A2A.

## Workflow

1. Create a focused branch from the default branch.
2. Explain the user-visible behavior and the threat model for integration changes.
3. Add or update tests for normal, timeout and identity-failure paths.
4. Run `ruff check .`, `pytest` and `python scripts/check_secrets.py`.
5. Keep examples placeholder-only. Do not commit Feishu credentials, tokens,
   message exports or screenshots containing private IDs.

## Pull requests

Describe the affected API, migration/rollback path and compatibility impact. A
maintainer may request a staging webhook test before merging transport changes.
