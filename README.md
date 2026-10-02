# Pushover (Agent Zero plugin)

`pushover` is a small Agent Zero plugin that lets an agent send a Pushover
notification when the user has **explicitly asked** to be notified. The
plugin keeps the surface area minimal so notifications only happen on
opt-in user instructions.

> **Pushover notifications are not sent automatically.** The agent uses
> Pushover only when the user explicitly requests a notification in the
> same conversation.

---

## 1. What the plugin does

- Adds a single agent-callable tool: `pushover_notify`.
- Provides a Settings → External → Pushover page to enter your
  Pushover Application/API Token and User/Group Key.
- Exposes three buttons: **Save Configuration**, **Test Connection**,
  and **Send Test Notification**.
- Stores credentials in Agent Zero's secret store. Credentials are
  never written to disk in plain text or returned to the browser.

The plugin intentionally does **not** implement automatic
notifications. There is no task-completion hook, no startup hook, no
sub-agent hook, no scheduled hook. Notifications are sent only when
the agent's tool is called as a result of a user request.

## 2. Pushover account setup

You need a Pushover account before configuring the plugin.

1. Create an account at <https://pushover.net/>.
2. From the dashboard, copy your **User Key** (also called the
   "User Key" or "Group Key" if you target a delivery group).
3. Scroll to the bottom of the dashboard and click **Create an
   Application/API Token**.
4. Fill in the application name (anything, e.g. "Agent Zero") and an
   optional description.
5. Pushover will display a 30-character **API Token**. Copy that
   value. Treat it like a password; do not commit it or share it.

## 3. Installation

The plugin ships under `usr/plugins/pushover/` and is discovered by
Agent Zero through its normal plugin mechanism. To install:

1. Copy this directory to `/a0/usr/plugins/pushover/`.
2. Open the Agent Zero WebUI → **Settings** → **External** → **Pushover**.
3. Paste your Application/API Token and User/Group Key.
4. Click **Save Configuration**.
5. Click **Test Connection** to verify the API is reachable.
6. Click **Send Test Notification** to verify Pushover delivers the
   fixed test message.

Credentials are stored in Agent Zero's secret store under
`PUSHOVER_API_TOKEN` and `PUSHOVER_USER_KEY` and persist across
Agent Zero restarts.

## 4. Plugin icon

The plugin ships with a `webui/thumbnail.png` icon that follows Agent
Zero's existing plugin icon conventions: a clean notification/bell
motif on a circle background. No third-party branding is reproduced.

## 5. Agent tool usage

The plugin exposes a single agent tool:

```json
{
  "name": "pushover_notify",
  "parameters": {
    "message": "string (required) — notification body",
    "title": "string (optional) — notification title, defaults to 'Agent Zero'"
  }
}
```

Successful call:

```json
{ "success": true, "message": "Pushover notification sent." }
```

Failed call (the original task still completes normally):

```json
{ "success": false, "error": "Pushover notification could not be delivered." }
```

### When the agent should call it

The agent calls `pushover_notify` only when the user has explicitly
asked to be notified via Pushover. Examples of valid user requests:

- *"Let me know via Pushover when this task is finished."*
- *"Send me a Pushover notification when you're done."*
- *"Notify me on Pushover when the backup has completed."*
- *"Laat me via Pushover weten wanneer je klaar bent."*

When the user has not asked for a Pushover notification, the agent
must not call `pushover_notify`. The tool's prompt fragment makes
this rule explicit.

### Timing

If the user says *"Notify me when you're done."* the agent must:

1. Perform the requested task.
2. Verify the task completed successfully.
3. Call `pushover_notify` only after step 2.
4. Return the normal Agent Zero response.

The agent must not call `pushover_notify` while a sub-task or
intermediate step is still running, or before verifying that the
requested task has reached its final outcome.

## 6. Security

- HTTPS only. The Pushover endpoint is `https://api.pushover.net/1/messages.json`.
- TLS verification is enabled (default Python `ssl` context with
  `CERT_REQUIRED`).
- Credentials are read directly from Agent Zero's secret store and
  are never returned to the browser or the agent after the first save.
- The UI shows only masked credential representations (e.g. `••••••esmm`).
- The agent tool never accepts credentials as arguments.
- API error messages returned to the agent are sanitized. They never
  include the token or user key, and they hide internal details such
  as full URLs or stack traces.
- No Agent Zero core files are modified by this plugin.

## 7. Failure handling

A Pushover failure never causes the user's original Agent Zero task
to fail. The plugin maps transport errors, HTTP errors, malformed
responses, timeouts, and TLS errors to a generic
`"Pushover notification could not be delivered."`-style message and
returns it to the agent as a JSON result. The agent then tells the
user that the original task completed but the Pushover notification
failed.

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Status shows "Not configured" | Secrets are empty | Re-enter your credentials in Setup and click **Save Configuration** |
| Test Connection fails with a generic error | The Pushover API rejected the request or the network is blocked | Check that the Application/API Token is valid (rotating the token on pushover.net invalidates the old one); verify outbound HTTPS to `api.pushover.net` is allowed |
| Send Test Notification succeeds locally but no device receives it | The Pushover user key targets an account that has no active Pushover client | Install and sign in to Pushover on the device you expect to receive the notification |
| Tool returns `"Pushover is not configured"` from the agent | Credentials were never saved, or were removed | Re-enter credentials and click **Save Configuration** |
| Tool returns `"Pushover notification could not be delivered."` | Transient network or API failure | Retry from the agent; the plugin does not retry indefinitely |

## 9. Pushover API used

- Endpoint: `https://api.pushover.net/1/messages.json`
- Method: HTTPS POST
- Required form fields: `token`, `user`, `message`
- Optional form field used: `title`
- Form field always set to `priority=0` (normal priority only)

The plugin does **not** implement emergency notifications, receipt
tracking, receipt polling, cancellation, cancel-by-tag, device
selection, sounds, TTL, callbacks, tags, attachments, API usage
monitoring, HTML formatting, monospace formatting, or supplementary
URLs.

## 10. Uninstallation

1. In Agent Zero's plugin manager, disable **Pushover**.
2. (Optional) delete the secrets `PUSHOVER_API_TOKEN` and
   `PUSHOVER_USER_KEY` from Agent Zero's secret store.
3. Delete `/a0/usr/plugins/pushover/`.

The plugin does not register background services, schedules, or external
dependencies, so removal leaves no orphan state on the host.
