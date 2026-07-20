# Troubleshooting

## Hermes does not react

Check that the event subscription is enabled, the callback is reachable, the
signature token matches, and the `chat_id` is in the allow-list. Inspect HTTP 401,
chat filtering and the Feishu event delivery retry log.

## One Agent is silent

Check `/agents`, then send a heartbeat. An Agent is marked offline after two
heartbeat intervals. Verify its `open_id`, group membership and app availability
range; display names are not stable identifiers.

## Another Agent's name appears on a reply

This is an identity collision. Search the Agent runtime for direct `lark-cli` or
Feishu API sends, inspect the outgoing app ID, and make the connector the only
sender. Remove default CLI profiles from prompts and rotate any leaked token.

## Duplicate final replies

A task must return text once. Do not send a message from inside the Agent and then
return the same content for connector delivery. Use the run ID and idempotency key
when integrating an external queue.

## Workflows stuck in queued/running

Check `/metrics`, Agent heartbeats, task dependencies and timeout/retry settings.
A dependency cycle is rejected by the engine when no task is ready.

For the complete identity incident analysis and recovery sequence, see
[`identity-boundary-postmortem.md`](identity-boundary-postmortem.md).
