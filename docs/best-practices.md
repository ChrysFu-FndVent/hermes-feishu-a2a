# Best practices

- Keep workflow creation in one authenticated integration and make Agent ownership explicit.
- Give each Agent one narrow role, a stable ID and explicit capabilities.
- Keep declarative and runtime registration ownership separate; change YAML-owned Agents in YAML.
- Require revision preconditions for automated runtime updates and retain registry audit events.
- Use exact capability selectors and review the persisted route decision before widening constraints.
- Set a positive `HERMES_AGENT_ENDPOINT_ALLOWED_HOSTS` policy and require HTTPS where possible.
- Prefer parallel tasks for independent evidence and serial tasks for transformations.
- Set deadlines based on the slowest real Agent, then retry only transient failures.
- Persist run IDs and include them in Agent callbacks so operators can audit a result.
- Use native `at` post elements, not literal `<at>` markup in plain text.
- Treat Agent output as untrusted input and validate callback identities.
- Grant `attachment:read` only to Agents approved to receive extracted file contents.
- Keep file count, compressed/uncompressed size and extracted-text limits conservative.
- Rate-limit inbound events and deduplicate message IDs before dispatching.
- Keep operational metrics free of prompt contents and credentials.
- Test failure paths: no route, stale revision, ownership conflict, disallowed endpoint, offline Agent,
  401 webhook, timeout, duplicate event and bad dependency.
