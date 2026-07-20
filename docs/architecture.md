# Architecture

```text
Feishu event/webhook -> Coordinator -> AgentRegistry (roles + membership)
                              |                |
                              v                v
                         TaskStore       HealthMonitor -> recovery callback
                              |
                              v
              WorkflowRunner (serial | parallel) -> FeishuClient (native @)
```

The Feishu transport is deliberately small. A vendor-specific worker adapter can call `coordinator.report()` after executing in Hermes, CodeX, Qoder, WorkBuddy or another runtime. This keeps execution permissions separate from dispatch permissions.

`queued -> running -> succeeded|failed|cancelled|timed_out` is the worker lifecycle. Hermes may then record `accepted -> co_reviewed -> delivery_authorized -> delivered`. Each transition is audited in memory by default; production deployments should replace `TaskStore` with SQLite or Postgres.

An envelope is HMAC-signed over canonical fields and expires. A receiver must also check that the sender open ID is registered for the same `oc_...` group and that the Feishu event genuinely mentions the receiver. Unsigned or stale bot messages are rejected, never dispatched.
