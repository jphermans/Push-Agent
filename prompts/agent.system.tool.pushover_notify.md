### tool: `pushover_notify`

Send a Pushover notification to the user when the user has **explicitly asked** for a Pushover notification.

**Use this tool only when the user has clearly requested a Pushover notification**, for example:

- "Let me know via Pushover when this task is finished."
- "Send me a Pushover notification when you're done."
- "Notify me on Pushover when the backup has completed."

**Do not** call this tool for tasks where the user did not request a Pushover notification. Pushover is opt-in and must never be sent automatically.

**Do not** call this tool before the requested task has actually reached its final completion state. The notification must reflect the actual outcome.

**Do not** call this tool while a sub-task, intermediate step, or another operation is still running.

#### Arguments

- `message` (string, required) — the notification body. Plain text only.
- `title` (string, optional) — the notification title. Defaults to `"Agent Zero"` when omitted.

Credentials (Application/API Token, User/Group Key) are read internally from plugin configuration; do not pass them as arguments and never log them.

#### Example (success)

```json
{
  "message": "Task completed successfully: Backup server.",
  "title": "Agent Zero"
}
```

#### Example (failure)

If the user explicitly requested a Pushover notification regardless of success or failure:

```json
{
  "message": "Task failed: Backup server.",
  "title": "Agent Zero"
}
```

#### Response

Success:

```json
{ "success": true, "message": "Pushover notification sent." }
```

Failure (the original task still completes normally):

```json
{ "success": false, "error": "Pushover notification could not be delivered." }
```
