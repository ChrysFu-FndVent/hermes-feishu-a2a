# Best practices

- Keep Hermes as the only component that decides task ownership and final synthesis.
- Give each Agent one narrow role and explicit capabilities; avoid overlapping names.
- Prefer parallel tasks for independent evidence and serial tasks for transformations.
- Set deadlines based on the slowest real Agent, then retry only transient failures.
- Persist run IDs and include them in Feishu replies so humans can audit a result.
- Use native `at` post elements, not literal `<at>` markup in plain text.
- Treat Agent output as untrusted input: escape it in logs and validate callback payloads.
- Rate-limit inbound events and deduplicate message IDs before dispatching.
- Keep operational metrics free of prompt contents and credentials.
- Test failure paths: offline Agent, 401 webhook, timeout, duplicate event and bad dependency.
