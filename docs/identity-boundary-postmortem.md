# Identity-boundary postmortem

This project records the failure mode that motivated the coordinator design:
one Agent runtime used a default `lark-cli` profile belonging to another bot.
When that runtime sent a message directly, Feishu displayed the wrong sender and
the intended Agent appeared silent. A second failure mode was an Agent producing
another Agent's response because the group had no single delivery owner.

## Required controls

1. Registration binds a stable local `agent_id` to the Feishu `app_id`/`open_id`
   and the approved chat scope.
2. Workers return structured results to Hermes. They do not invoke `lark-cli`,
   copy another Agent's text, or send a second final reply.
3. Hermes (or one explicitly configured connector) owns final delivery. The
   outgoing message is logged with `run_id`, `task_id`, `agent_id` and app ID.
4. A heartbeat timeout changes the Agent to `offline`; dispatch retries and
   degraded state are visible through `/metrics` and `/runs/{run_id}`.
5. Regression tests must use distinct app IDs and assert both message identity
   and exactly-one final delivery.

## Recovery checklist

- Rotate any secret that was exposed in shell history or logs.
- Remove default CLI profiles from service accounts and use explicit credentials.
- Confirm the bot is a member of the target group; Feishu error `230002` means
  membership or availability is wrong, not that a retry will fix it.
- Re-register the Agent, send a heartbeat, and run a one-task synthetic workflow.
- Inspect the app ID and message ID in Feishu before re-enabling parallel work.
