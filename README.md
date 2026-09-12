# Pushover Plugin for Agent Zero

A production-quality Agent Zero plugin that lets your agents send push
notifications through [Pushover](https://pushover.net/). The plugin ships
with an agent-callable notification tool, a dedicated Setup page, and
configuration persistence following the modern Agent Zero plugin
conventions.

> Local plugin: this plugin lives at `/a0/usr/plugins/pushover/` and does
> not modify any Agent Zero core files.

## Features

- Agent-callable `pushover_notify` tool with `send`, `test`,
  `receipt_status`, `cancel`, and `cancel_by_tag` actions.
- Dedicated **Pushover Setup** page reachable from External Services.
- Per-user masking of credentials on the Setup page; secrets are stored
  with Agent Zero's normal plugin configuration mechanism.
- Connection testing (application token + user key validation).
- "Send Test Notification" button that delivers a real Pushover message
  using the configured defaults.
- Notification defaults (title, priority, sound, device, TTL, URL, URL
  title, tags, HTML/monospace formatting).
- Full priority range: `lowest`, `low`, `normal`, `high`, `emergency`.
- Emergency notifications with configurable retry/expire, with receipt
  IDs returned to the agent.
- Optional device selection.
- Dynamic sound list loaded from Pushover.
- API usage widget (`/1/apps/limits.json`) when Pushover returns it; the
  plugin degrades gracefully when unavailable.
- Advanced settings (HTTP timeout, debug logging) in a collapsed section.
- Reset Configuration control with a confirmation dialog.
- Help section linked to the Pushover account and app creation pages.
- No external Python dependencies - uses only the standard library.
- TLS verification is always on; HTTP timeouts are bounded.
- Credentials are masked in responses, logs, and error messages.

## Installation

The plugin is loaded automatically by Agent Zero once it is present in
`/a0/usr/plugins/pushover/`. No manual install command is required.

1. Open the Agent Zero UI and navigate to **Settings &rarr; Plugins**.
2. Make sure **Pushover** is enabled.
3. Open the **Pushover Setup** page from the plugin card or from
   **Settings &rarr; External Services**.

If you are installing from a Git URL or ZIP, copy the plugin directory
into `/a0/usr/plugins/pushover/` and reload the WebUI. The framework
will call `hooks.install()` automatically; there is no separate `Execute`
button to press.

## Setup

The end-to-end walkthrough lives in
[`SETUP.md`](./SETUP.md). That document covers Pushover account
creation, User Key retrieval, Application/API Token creation, plugin
installation, on-Setup-page configuration, verification, default tuning,
agent-driven sending, and a full troubleshooting matrix. The compressed
reminder below is enough for repeat users; reach for SETUP.md whenever
you hit a question or a non-obvious failure mode.

### Pushover account setup

1. Create a [Pushover](https://pushover.net/) account (one-time, the
   Pushover apps exist for iOS, Android, and Desktop).
2. Sign in to the Pushover dashboard. Your **User Key** is shown at the
   top of the dashboard.
3. Create an application/API token by visiting
   [pushover.net/apps/build](https://pushover.net/apps/build). Pick any
   name and description; copy the **API Token / Key** that the page
   shows after the application is created.

### Agent Zero Setup page

1. Open the Pushover Setup page.
2. Paste the **Application / API Token** and **User / Group Key**.
3. Click **Save Configuration**. The credential fields clear
   automatically; the Setup page shows the masked values.
4. Click **Test Connection** to verify the credentials against Pushover.
5. Click **Send Test Notification** to deliver a real test message.

For deep-dive help, see [`SETUP.md`](./SETUP.md) — it adds a
troubleshooting table, an FAQ covering credential recovery and proxy
support, and Docker/network notes. For an in-page Help block, the Setup
page itself renders a 6-step quick-link list near its footer.

## Testing the connection

Use either the **Test Connection** button on the Setup page or call
`POST /api/plugins/pushover/test`. The endpoint:

- Validates the application token via `GET /1/apps/limits.json`.
- Sends a lowest-priority test notification to validate the user key.
- Returns structured results without ever exposing the saved token.

## Sending test notifications

Use the **Send Test Notification** button or
`POST /api/plugins/pushover/test_notify`. The handler uses the
configured defaults (title, priority, sound, device, TTL, formatting).

## Agent tool usage

The plugin exposes a single tool, `pushover_notify`. The minimum call is:

```json
{
  "action": "send",
  "message": "Backup completed successfully."
}
```

A full call looks like:

```json
{
  "action": "send",
  "message": "Deployment completed.",
  "title": "Deployment",
  "priority": "high",
  "sound": "magic",
  "device": "iphone",
  "url": "https://agent.example.com",
  "url_title": "Open Agent Zero",
  "ttl": 3600,
  "html": false,
  "monospace": false
}
```

### Supported actions

| Action | Required args | Description |
| --- | --- | --- |
| `send` | `message` | Send a Pushover notification. |
| `test` | none | Send the default "Test Notification" from the Setup page. |
| `receipt_status` | `receipt` | Return acknowledgement info for an emergency notification. |
| `cancel` | `receipt` | Cancel an outstanding emergency notification. |
| `cancel_by_tag` | none | Returns a clear refusal; Pushover does not support tag-based cancellation. |

### Priorities

The plugin accepts both the friendly names and the numeric Pushover
values:

| Friendly | Numeric | Description |
| --- | --- | --- |
| `lowest` | -2 | No sound, no vibration. |
| `low` | -1 | Quiet alert. |
| `normal` | 0 | Default. |
| `high` | 1 | Bypasses quiet hours. |
| `emergency` | 2 | Repeats until acknowledged. |

The agent tool policy instructs the agent to use `normal` for routine
informational pushes, `high` only when explicitly requested, and
`emergency` only when the user has asked for it explicitly. The agent
never escalates a message on its own.

## Emergency notifications

For an emergency notification you must supply `priority=emergency` (or
the numeric `2`). The plugin automatically pairs it with the configured
`retry` and `expire` values (recommended defaults: `retry=60`,
`expire=3600`). Pushover returns a `receipt` ID, which you should pass
to `receipt_status` or `cancel` later.

- `retry` must be at least `30` seconds; maximum `86400`.
- `expire` may be `0` (never expire) or `30..10800` seconds.
- Emergency notifications repeat at the retry interval until the user
  acknowledges them or the expiration time elapses.

## Devices

The optional **Device** field accepts values such as `iphone`, `ipad`,
or a comma-separated list such as `iphone,ipad`. Leaving the field
blank sends the notification to every device on the user's account.

## Sounds

The Setup page loads the available Pushover sounds when connected. The
default option, "User default", omits the `sound` parameter so the
recipient's Pushover preference applies. Choose any other entry to
override the recipient's default with a specific sound.

## TTL

TTL controls how long the notification remains valid; Pushover's default
is to keep the notification until the device receives it. Set a value in
seconds (e.g. `3600` = one hour). Maximum is `604800` (7 days). Empty
falls back to Pushover's default behaviour.

## API limits

The Setup page fetches usage information from Pushover's
`/1/apps/limits.json` endpoint and shows a small progress indicator. The
indicator updates only when the endpoint returns data. A failure to
retrieve usage information **never** prevents notification sending;
the tool and the Setup page degrade gracefully.

## Security

- Tokens and user keys are never logged. The Setup page shows them only
  in masked form (`****ABCD`).
- TLS verification is always enabled.
- HTTP 4xx responses never trigger automatic retries; the tool returns a
  descriptive error so the agent can fix the configuration.
- Networks errors are reported with category (timeout, DNS, TLS).
- Debug logging never prints the configured token or user key.
- Reset is destructive and requires explicit confirmation.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| "Pushover is not configured yet" | Open the Setup page and add credentials. |
| "Invalid Pushover application token" | Recreate the token on pushover.net/apps/build. |
| "Invalid Pushover user key" | Copy the User Key from the Pushover dashboard. |
| "Pushover request timed out" | Increase the **Advanced Settings &rarr; HTTP timeout** or check the network. |
| "Pushover DNS resolution failed" | The container/host cannot reach `api.pushover.net`. |
| "Pushover API quota exceeded" | Pushover returned `429`; wait or upgrade the application limit. |
| Test Connection green but no notification arrives | The user key is valid but Pushover could not deliver - check the Pushover app on the device. |

## Uninstallation

Disable and remove the plugin from Settings &rarr; Plugins. The plugin's
`hooks.uninstall()` clears the stored Pushover configuration.

## Files

```
usr/plugins/pushover/
├── plugin.yaml
├── default_config.yaml
├── README.md
├── LICENSE
├── CHANGELOG.md                 # version history (Keep-a-Changelog format)
├── SETUP.md                      # detailed end-to-end setup walkthrough + troubleshooting
├── thumbnail.png                 # 128x128 PNG (< 2 KB) for the Plugin Hub Index entry
├── hooks.py
├── helpers/
│   ├── __init__.py
│   ├── pushover_client.py
│   ├── config_helper.py
│   └── validation.py
├── tools/
│   └── pushover_notify.py
├── api/
│   ├── test.py
│   ├── validate.py
│   ├── sounds.py
│   ├── limits.py
│   ├── status.py
│   ├── save.py
│   ├── test_notify.py
│   └── reset.py
├── prompts/
│   └── fw.pushover.tool.md
├── webui/
│   ├── main.html                 # dedicated Pushover Setup page (Plugins card)
│   ├── config.html               # External Services panel entry (Settings → Pushover)
│   └── setup-store.js
├── .gitignore                    # excludes __pycache__, .toggle-*, build/, etc.
├── index.yaml                    # Plugin-Hub submission entry (read by agent0ai/a0-plugins,
│                                 # not by the runtime)
└── dist/                         # generated by `bash scripts/build_release.sh`
└── tests/
    ├── __init__.py
    ├── test_client.py
    ├── test_validation.py
    ├── test_tool.py
    └── test_emergency_default.py
```

## Versioning

This plugin follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
and a [Keep-a-Changelog](https://keepachangelog.com/en/1.1.0/) entry is
added for every release. Concretely:

- **MAJOR** bumps for breaking changes (tool surface, API contract, or
  persisted-config-schema breaks).
- **MINOR** bumps for new backwards-compatible features.
- **PATCH** bumps for bug fixes and additive asset/documentation-only
  changes (such as the `thumbnail.png` shipped in 1.0.1).

Every change — even doc-only — must:

1. Bump `version:` in `plugin.yaml`.
2. Add a dated entry in `CHANGELOG.md` under the new version heading.
3. Pass the existing test suite (`python -m unittest discover -s tests
   -p 'test_*.py'`).

The current version is read from the top of `plugin.yaml`.
