# Feishu permissions and event setup

This guide intentionally uses placeholders. Replace `cli_xxx`, `ou_xxx` and
`oc_xxx` with values from your own tenant; never paste app secrets into a public
issue or repository.

## Coordinator app

In the developer console, create the Hermes app and enable the narrowest scopes
needed by your workflow:

| Capability | Typical scope family | Why |
| --- | --- | --- |
| Receive messages | `im:message.receive_v1` event subscription | Inbound group events |
| Read messages | `im:message:readonly` | Recover context and audit replies |
| Send/reply | `im:message:send` / tenant equivalent | Final Hermes replies and native mentions |
| Read chat metadata | `im:chat:read` | Validate chat membership and names |
| Read members | `im:chat.members:read` | Resolve stable `open_id` values |
| Manage members (optional) | `im:chat.members:write_only` | Only if Hermes provisions a group |
| Manage chat (optional) | `im:chat:update` | Only if Hermes updates metadata |

Scope names vary between Feishu/Lark tenants and API versions. Treat the
developer console's current scope list as authoritative and record the exact
approved list in your change log.

## Agent apps

An execution Agent usually needs message receive, message read and message send
only when it is allowed to post directly. This project recommends **not** granting
direct send to WorkBuddy-style Agents: let the connector post the final text so
the app identity is deterministic. Add member-management scopes only to a
dedicated provisioning app, never to every worker.

## Webhook

1. Set the callback URL to `https://your-host.example/webhooks/feishu`.
2. Set `HERMES_FEISHU_VERIFICATION_TOKEN` and, if enabled by the tenant,
   `HERMES_FEISHU_ENCRYPT_KEY` in the deployment secret store.
3. Subscribe to `im.message.receive_v1`.
4. Allow only the intended `oc_...` chats using `HERMES_FEISHU_ALLOWED_CHAT_IDS`.
5. Confirm the challenge request in a staging deployment before publishing.
6. Monitor 401 signature failures and 230002 membership failures separately.

The sample endpoint authenticates the raw request body with timestamp, nonce and
HMAC before parsing. If your tenant uses a different signed envelope, implement
that variant in `security.py` and add a fixture before changing the endpoint.

## Common errors

- `230002`: the bot/app is not in the group or the app is outside its availability range.
- `99991679` or missing scope: add the exact scope in the developer console and
  republish; user-delegated scopes also require a fresh OAuth grant.
- Duplicate replies: check that an Agent is not both calling a CLI sender and
  returning a final connector response.
- Wrong sender identity: inspect the app ID on the outgoing message and remove
  default CLI profiles from Agent runtime instructions.
