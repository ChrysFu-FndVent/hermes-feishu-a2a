# Best practices

- Keep workflow creation in one authenticated integration and make Agent ownership explicit.
- Give each Agent one narrow role, a stable ID and explicit capabilities.
- Prefer parallel tasks for independent evidence and serial tasks for transformations.
- Set deadlines based on the slowest real Agent, then retry only transient failures.
- Persist run IDs and include them in Agent callbacks so operators can audit a result.
- Use native `at` post elements, not literal `<at>` markup in plain text.
- Treat Agent output as untrusted input and validate callback identities.
- Rate-limit inbound events and deduplicate message IDs before dispatching.
- Keep operational metrics free of prompt contents and credentials.
- Test failure paths: offline Agent, 401 webhook, timeout, duplicate event and bad dependency.
