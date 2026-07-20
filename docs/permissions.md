# Feishu permissions and events

Use one Feishu custom app per agent. In [Feishu Open Platform](https://open.feishu.cn/app), open the app, choose **Development Configuration -> Permissions & Scopes**, search each scope below, save, then create and publish a new version.

## Minimum scopes

| Scope | Why |
| --- | --- |
| `im:message` (send/read variants exposed by tenant) | Send task, result and status messages |
| `im:message.group_at_msg.include_bot:readonly` | Receive another bot's native @ message |
| `im:chat:readonly` | Read target group metadata |
| `im:chat.member:readonly` | Confirm configured bots are in the group |
| `im:chat.announcement:read` | Read `/open-apis/docx/v1/chats/{oc_id}/announcement/blocks` |
| Bot basic information | Resolve app name and bot `open_id` |

Add only write/admin scopes when a workflow needs them. Group management and bot management are not required to read announcements. The app must be installed in the group; a tenant admin may need to approve permissions.

## Event subscription

In **Events & Callbacks**, choose HTTPS callback mode, set `https://host.example/webhook/feishu`, and subscribe to `im.message.receive_v1`. Set the verification token and encrypt key in `.env`; the service answers the URL challenge and validates signed requests. For high-throughput deployments, use Feishu WebSocket mode in a dedicated adapter and retain the same envelope validation.

## Announcement API note

The API requires the Open API chat ID beginning with `oc_`. The numeric ID shown in a client URL is not interchangeable. The pilot group used `oc_92a5e76f55e6727e2c918d4ae018b363` and announcement token `CfoOdniU2oS8iPxZUNbcNyvenje`; use your own values in configuration.
