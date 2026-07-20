# Feishu permissions and event setup

Replace every placeholder with values from your own Feishu/Lark tenant. Never put
app secrets, encrypt keys, verification tokens or private IDs in the repository.

## Coordinator app

Create one custom app for Hermes and enable only the capabilities required by the
deployment:

| Capability | Typical scope or event | Purpose |
| --- | --- | --- |
| Receive messages | `im.message.receive_v1` | Deliver group events to the webhook |
| Send messages | `im:message:send` or tenant equivalent | Dispatch Feishu Agent tasks |
| Read chat metadata | `im:chat:read` | Validate target chats |
| Read members | `im:chat.members:read` | Obtain stable `open_id` values |
| Download message files | `im:resource` | Read files attached directly to messages |
| Download cloud-space files | `drive:file:download` | Download shared `/file/...` links with the minimum application-identity scope |
| Receive bot-authored mentions | `im:message.group_at_msg.include_bot:readonly` | Allow Feishu Agents to receive coordinator tasks |

Exact scope names can vary between Feishu and Lark tenants. Use the current developer
console as the source of truth and do not add write scopes that the deployment does
not need.

## Event subscription

1. Set the callback URL to `https://your-host.example/webhooks/feishu`.
2. Configure the same encrypt key and verification token in `.env` and the developer
   console.
3. Subscribe to `im.message.receive_v1`.
4. Add the target `oc_...` IDs to `HERMES_FEISHU_ALLOWED_CHAT_IDS`.
5. Add authorized human `ou_...` IDs to `HERMES_FEISHU_OWNER_OPEN_IDS`.
6. Set `HERMES_FEISHU_FILE_INTAKE_AGENT_ID` when file messages should start a bounded
   single-Agent workflow.
7. Publish the app version, obtain tenant approval, and add the bot to the chat.

The webhook verifies `X-Lark-Signature` as SHA-256 over the request timestamp,
request nonce, encrypt key and raw request body. It accepts both the current
`X-Lark-Request-*` timestamp/nonce headers and the older `X-Lark-*` names. After
decryption, it compares the event verification token and applies chat and sender
allow-lists.

Normal accepted webhook events are not automatically converted into workflows. File
messages are routed deterministically only when `HERMES_FEISHU_FILE_INTAKE_AGENT_ID`
is configured. Other natural-language messages still require an external planner or
deterministic adapter.

Files attached directly to a message are downloaded through the message-resource API.
Links whose URL path is `/file/{token}` use the Drive download API. A granted scope is
not enough by itself: the app identity must also be able to access the specific file.
After adding either scope, publish a new application version and obtain tenant approval.

## Feishu Agent callbacks

When a task targets a Feishu Agent, Hermes sends a native `at` post. The Agent can reply
in that message thread or call `/events/agent-result` with the matching run, task and
Agent IDs. Thread replies are verified using the parent/root message ID and registered
Agent `open_id`. The API callback requires `X-Hermes-Token` and must arrive before the
task timeout.

## Common Feishu errors

- `230002`: the bot is not in the target chat or is outside its availability range.
- `99991679` or missing scope: grant the exact scope, publish a new app version and
  obtain tenant approval again.
- File download `403`, `91403`, or permission denied: confirm `im:resource` or
  `drive:file:download` is approved for the application identity and the file is
  shared with an identity the app can access.
- HTTP 401 from the webhook: compare the encrypt key, verification token, timestamp
  headers and raw-body signature calculation.
- `sender_not_allowed`: add the human owner or registered Agent `open_id` to the
  appropriate configuration.
