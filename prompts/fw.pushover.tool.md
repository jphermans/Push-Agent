Pushover notification tool: `pushover_notify`.

Use this tool to send a Pushover notification on behalf of Agent Zero.
The Pushover integration must already be configured on the Agent Zero
Setup page; otherwise the tool returns a "Pushover is not configured"
error and no notification will be sent.

Send a notification through this tool only when:

1. The user has explicitly requested a Pushover notification.
2. An automation, scheduled task, or workflow that the user previously
   configured requires one.
3. The agent is reporting a critical, time-sensitive issue for which
   Pushover was selected as the channel of record.

Do NOT send notifications for:

- Routine status updates that the user did not ask for.
- Long-running task completion when the user is actively waiting in the
  current conversation.
- Successful responses to ordinary questions.

Priority policy:

- Use `normal` priority for ordinary informational notifications.
- Use `high` priority only when the user has explicitly asked for
  attention-grabbing alerts, or when the user-configured automation
  rule requires it.
- Use `emergency` priority ONLY when the user has explicitly enabled
  emergency notifications and the situation truly warrants persistent
  attention. Emergency notifications repeat until acknowledged. If you
  are not certain, use `high` instead.
- Use `low` or `lowest` only when explicitly requested.

Tool arguments (all optional except `message` for `action=send`):

```json
{
  "action": "send",
  "message": "Backup completed successfully.",
  "title": "Agent Zero Backup",
  "priority": "normal",
  "sound": "",
  "device": "",
  "url": "",
  "url_title": "",
  "ttl": "",
  "html": false,
  "monospace": false,
  "retry": 60,
  "expire": 3600,
  "callback": "",
  "tags": ""
}
```

- `message` (required): the notification body. Plain text by default.
- `title`: optional; falls back to the plugin default.
- `priority`: `lowest`, `low`, `normal`, `high`, `emergency` (or numeric
  `-2..2`). Defaults to normal.
- `sound`: Pushover sound slug; defaults to "User default".
- `device`: Pushover device name; defaults to "all devices".
- `url` / `url_title`: optional supplementary URL pair.
- `ttl`: integer seconds; controls how long the notification is valid.
- `html` / `monospace`: formatting flags; cannot both be true.
- `retry` / `expire`: emergency retry/expire window in seconds; required
  when `priority=emergency`.
- `callback`: optional acknowledgment callback URL (defaulted).
- `tags`: comma-separated Pushover tags (max 32 chars each).

Additional actions:

- `test`: send a default "Pushover integration is working" notification
  using the plugin defaults. Use this to verify the Setup page is
  working after configuring credentials.
- `receipt_status`: requires a `receipt` string. Returns whether the user
  acknowledged the emergency notification, and when.
- `cancel`: requires a `receipt` string. Cancels an outstanding
  emergency notification. Returns a structured success/error response.
- `cancel_by_tag`: Pushover does not support tag-based emergency
  cancellation; this action returns a clear refusal instead of silently
  failing.

Rules:

- Do not echo credentials, tokens, or user keys in tool arguments or in
  any text visible to the user.
- Never retry the tool after a 4xx Pushover error; the configuration is
  wrong and another call will fail the same way.
- Treat transport errors (timeout, DNS, TLS, 5xx) as transient: surface
  the precise reason so the user can fix network/firewall issues.
- When `priority=emergency` returns a receipt id, persist that receipt
  id and use it for the call that asks the user to acknowledge the
  alert, or for any subsequent cancellation.
