<p align="center">
  <img src="./thumbnail.png" alt="push_zero — A0-branded notification icon" width="128" height="128" />
</p>

<h1 align="center">
  <span style="color:#E74C3C">push</span><span style="color:#2A5C8F">_zero</span>
</h1>

<p align="center">
  <strong>Agent-callable push notifications via Pushover, branded for Agent Zero.</strong>
</p>

<p align="center">
  <a href="https://github.com/AUTH_LOGIN/Push-Agent"><img src="https://img.shields.io/badge/repo-Push--Agent-2A5C8F?style=for-the-badge&logo=github" alt="Repository" /></a>
  <a href="#"><img src="https://img.shields.io/badge/version-1.1.22-E74C3C?style=for-the-badge" alt="Version" /></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-28a745?style=for-the-badge" alt="License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Agent_Zero-compatible-2A5C8F?style=for-the-badge" alt="Agent Zero compatibility" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-f39c12?style=for-the-badge&logo=python" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-49%2F49-28a745?style=for-the-badge" alt="Tests" /></a>
</p>

---

## ✨ What this is

**`push_zero`** is a production-quality Agent Zero plugin that lets your agents and automations send **push notifications through Pushover** — the long-running, low-noise messaging service. It ships with a **dedicated Setup page**, **persistent configuration**, **connection testing**, **emergency notifications with receipts**, and **agent-callable tooling** for every common workflow.

It is shaped after the **Agent Zero plugin architecture** and respects all current contributor rules: the manifest at `plugin.yaml` is the source of truth, the runtime folder is the plugin location, and the public repo (`Push-Agent`) carries the same name as the runtime slug.

---

## 🎯 Features at a glance

| Icon | Capability | Notes |
| :---: | :--- | :--- |
| 🔔 | **Send notifications** | Standard `push_zero_notify` tool with `action: "send"` |
| ⚙️ | **Dedicated Setup page** | First-run onboarding, defaults, masking, help |
| ✅ | **Test Connection** | Validates token + user key without exposing secrets |
| 📨 | **Send Test Notification** | End-to-end delivery check with one click |
| 🚨 | **Emergency notifications** | Priority `2` with retry/expire enforcement |
| 📜 | **Receipt lookup** | `action: "receipt_status"` returns acknowledgement state |
| ✖️ | **Emergency cancel** | `action: "cancel"` revokes an active emergency |
| 🎵 | **Sounds** | Dynamic sound list, `User default` falls back gracefully |
| 📱 | **Device targeting** | `All devices` default; comma-separated per device accepted |
| 🔗 | **URLs + URL titles** | Validated, optional |
| ⏳ | **TTL** | Optional, in seconds, validated |
| 📊 | **API Usage** | Live `monthly limit / used / remaining / reset` panel |
| 🔐 | **Persistent config** | First-run values masked, never echoed in logs |
| 🎨 | **Theme-aware UI** | Reads Agent Zero's `var(--color-*)` tokens (light + dark) |
| 🧪 | **49 unit tests** | All pass; mock HTTP, no real network in CI |
| 🏷️ | **Tag-aware versioning** | Every change bumps `version:` + `CHANGELOG.md` |
| 🛡️ | **Safety rails** | HTML and monospace mutually exclusive; retry ≥ 30 s; expire ≤ 10800 s |

---

## 🧱 Architecture (Mermaid)

```mermaid
flowchart LR
    subgraph AgentZero["Agent Zero runtime"]
      direction TB
      UI["WebUI / Setup page\nwebui/main.html + config.html"]
      API["API endpoints\n/api/plugins/push_zero/*"]
      Tool["Agent tool\npush_zero_notify"]
    end

    subgraph Plugin["push_zero plugin"]
      direction TB
      Client["helpers/push_zero_client.py\n(HTTPS over urllib, TLS verified)"]
      Cfg["helpers/config_helper.py\n(persistent config + masking)"]
      Val["helpers/validation.py\n(payload + emergency + priority)"]
    end

    Pushover["Pushover API\napi.pushover.net/1/messages.json"]

    UI --> Cfg
    API --> Client
    API --> Val
    Tool  --> Val
    Val   --> Client
    Cfg   --> Client
    Client -->|HTTPS POST| Pushover
    Pushover -->|JSON| Client
```

---

## 📋 Requirements

- **Agent Zero** v0.9+ (the plugin uses the current manifest + hooks contract).
- **Python 3.10+** runtime (matches Agent Zero).
- A **Pushover account** with:
  - **User Key** — `https://pushover.net/`<wbr/>`dashboard` → top of the page.
  - **Application/API Token** — `https://pushover.net/`<wbr/>`apps/build`.
- **No** additional Python dependencies — only stdlib (`urllib`, `json`, `ssl`, `logging`, `re`, `configparser`).

---

## 🚀 Installation

1. Drop the plugin folder into `/a0/usr/plugins/push_zero/` (or use the Agent Zero plugin manager).
2. Restart Agent Zero so the loader picks up the new manifest.
3. Open **Settings → Plugins → push_zero → Setup** to enter your credentials.
4. Click **Test Connection**. ✅ Done.

For a community install from the Plugin Hub (once the Index PR is merged):

```
push_zero$ a0 plugins install push_zero
```

---

## 🛠️ Setup page

The plugin provides its own Setup page (`webui/main.html`, also reachable as `webui/config.html` under **External Services**). Sections:

| Section | Purpose |
| :--- | :--- |
| 🟢 **Connection status** | Live indicator (`Connected` / `Not configured` / `Authentication failed` / `Pushover unavailable`) |
| 🔑 **Credentials** | Application Token + User / Group Key, optional Device; masked after save |
| 🧪 **Test Connection** | Validates without sending a notification |
| 📨 **Send Test Notification** | End-to-end delivery check |
| 🔔 **Notification Defaults** | Title, Priority, Sound, Device, TTL, URL/URL Title, HTML/monospace toggles |
| 🚨 **Emergency Notifications** | Retry (≥ 30 s) and Expire (≤ 10800 s) with validation |
| 📱 **Device & Sound** | Dynamic dropdowns, `User default` always present |
| 📊 **API Usage** | Live monthly quota panel when the application API is reachable |
| 🛠️ **Advanced Settings** | Timeout, debug logging (credentials still masked), default callback, default tags |
| 🧹 **Reset Pushover** | Confirmation-gated wipe |
| 📚 **Help** | 6-step quickstart + link to `SETUP.md` |

Theme: follows the Agent Zero host via `var(--color-*)` neutral pointers — switches automatically when the user toggles `body.light-mode ↔ body.dark-mode`.

---

## 🤖 Agent tool — `push_zero_notify`

The agent-callable tool accepts a structured `action`:

| Action | Required params | Returns |
| :--- | :--- | :--- |
| `send` | `message` | `{success, status, request}` and `{receipt}` for emergencies |
| `test` | (none) | `{success, status, request}` |
| `receipt_status` | `receipt` | `{acknowledged, acknowledged_at, acknowledged_by, …}` |
| `cancel` | `receipt` | `{success, status}` |
| `cancel_by_tag` | (always refuses) | `{success: false, error: "Pushover cancellation by tag is not supported"}` |

### `send` parameters

| Field | Type | Required | Notes |
| :--- | :--- | :---: | :--- |
| `message` | string | ✅ | Plain text, or HTML/monospace per flags |
| `title` | string | — | Falls back to plugin default |
| `priority` | string/int | — | `lowest` / `low` / `normal` / `high` / `emergency`, or `-2..2` |
| `sound` | string | — | `User default` to omit the field |
| `device` | string | — | Device name, comma-separated, or empty for all |
| `url` / `url_title` | string | — | Optional, validated |
| `ttl` | int (seconds) | — | Optional, validated |
| `html` / `monospace` | bool | — | **Mutually exclusive** |
| `retry` / `expire` | int | — | Required when `priority == emergency` |
| `callback` | string | — | Optional ack URL |
| `tags` | string or list | — | Comma-separated or list, joined to Pushover's tag list |

### Example — minimal

```json
{
  "action": "send",
  "message": "Backup completed successfully."
}
```

### Example — emergency

```json
{
  "action": "send",
  "message": "Database replica is down.",
  "title": "Agent Zero - Critical",
  "priority": "emergency",
  "retry": 60,
  "expire": 3600
}
```

Returns:

```json
{
  "success": true,
  "status": 1,
  "request": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "receipt": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
}
```

Then poll:

```json
{
  "action": "receipt_status",
  "receipt": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
}
```

---

## 🚨 Emergency notifications

- **Priority:** `2` (`emergency`) or `"emergency"`.
- **Retry:** ≥ `30` seconds. **Recommended** `60`.
- **Expire:** ≤ `10800` seconds (3 hours). **Recommended** `3600`.
- Returns a `receipt` ID you can poll with `receipt_status` and revoke with `cancel`.
- **Never enabled implicitly** — the agent has to choose emergency explicitly.

---

## 🔐 Security

- ✅ TLS certificate verification **always on**.
- ✅ HTTP timeouts configurable, **default 12 s**.
- ✅ Sensitive values are masked in:
  - Setup page after save
  - Logs
  - API responses
- ✅ No credentials in source, README, CHANGELOG, or `index.yaml`.
- ✅ No retry storms on `4xx` (only on `5xx` and network errors).
- ✅ HTML and monospace are mutually exclusive.
- ✅ Numeric parameters (`retry`, `expire`, `ttl`) are validated.
- ✅ URL parameters are validated.
- ✅ No shell-out for outbound requests.
- ✅ Plugin doesn't require Docker privileged access.

---

## 🧪 Tests

```
cd /a0/usr/plugins/push_zero
python -m unittest discover -s tests -p 'test_*.py'
```

All HTTP calls are mocked. **49 tests cover**:

- configuration loading / saving
- priority normalization (friendly names ↔ numeric)
- emergency retry / expire validation
- HTML / monospace conflict
- TTL handling
- API response parsing (success, receipt, error)
- timeout, DNS, TLS, HTTP 4xx, HTTP 5xx
- credential masking
- `cancel_by_tag` refusal
- Setup page render and store wiring

Last verified slice (`test_client.py`): **26 / 26 PASS in 0.056 s**.

---

## 🆘 Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| ✖️ **Authentication failed** | Wrong token or user key | Re-copy from pushover.net; click **Test Connection** |
| ✖️ **Invalid user key** | User key contains stray whitespace | Re-paste from the dashboard |
| ✖️ **HTTP 429** | Pushover rate limit | Back off, check **API Usage** panel |
| ✖️ **HTTP 5xx** | Pushover temporarily unavailable | Plugin does not retry on 4xx; safe to retry send yourself |
| ✖️ **HTML + monospace both true** | Plugin auto-detects the conflict | Pick one in **Notification Defaults** |
| ✖️ **Emergency retry ignored** | Below `30 s` | Set ≥ `30 s` (recommended `60 s`) |
| ✖️ **Config won't save** | Schema validator rejected field | Check **Setup status** banner |
| ✖️ **No buttons in Plugins page** | Browser cache | Hard-refresh (Ctrl/Cmd-Shift-R) |
| ✖️ **Pushover unreachable** | DNS / TLS / proxy | Check container DNS, outbound HTTPS 443 |

---

## 🗑️ Uninstall

```
# from the Agent Zero Plugins page: click "Uninstall"
# or from a shell:
rm -rf /a0/usr/plugins/push_zero
```

The plugin's `hooks.py` is idempotent and clean — no orphan files, no schema residue, no cron jobs.

---

## 📜 License

[MIT](./LICENSE) — see the bundled `LICENSE` file.

---

## 🔗 Links

- **Repo:** `https://github.com/AUTH_LOGIN/Push-Agent`
- **Index entry:** `https://github.com/agent0ai/a0-plugins/blob/main/plugins/push_zero/index.yaml` (post-PR)
- **Pushover docs:** `https://pushover.net/`<wbr/>`api`
- **Agent Zero:** `https://github.com/agent0ai/agent-zero`

---

## 📖 Field Reference

Every field on the Setup page, what it controls, when it applies, and how it is validated. Defaults shown are the values the plugin writes when the field is left empty.

### 🔑 Credentials

| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `token` | string (30 chars) | — **(required)** | The Pushover application/API token. Created on [pushover.net → Apps & Plugins](https://pushover.net/apps/build). Treated as a secret — the Setup page renders a masked form (`****…q49i`) once saved. |
| `user` | string (30 chars) | — **(required)** | The Pushover user key or group key that receives notifications. Cannot be self-rotated on Pushover's platform — see `SECURITY.md` for the residual-risk note. |
| `device` | string (comma-separated device names) | `""` (all devices) | Optional device scope. Empty means every device the user/group owns. Examples: `iphone`, `ipad`, `iphone,ipad`. |

### 🔔 Notification Defaults

These values are sent **only when the agent's `push_zero_notify` call omits the same field**. They are the fallback layer between the plugin and the Pushover API.

| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `defaults.title` | string | `"Agent Zero"` | Title shown in bold above the message body. Empty input is replaced by the default; whitespace is stripped. |
| `defaults.priority` | string (friendly) → int | `"normal"` (0) | Pushover priority level. Friendly values `lowest` / `low` / `normal` / `high` / `emergency` are normalised to `-2` / `-1` / `0` / `+1` / `+2`. The agent tool accepts either form. |
| `defaults.sound` | string (sound slug) | `""` (User default) | Pushover notification sound. Empty string → the user's Pushover sound preference is used. Non-empty → specific sound slug (e.g. `magic`, `bike`, `bugle`). |
| `defaults.device` | string | `""` (all devices) | Per-notification device scope. Same syntax as the top-level `device` field. |
| `defaults.ttl` | string (int seconds) | `""` (no TTL) | Time-to-live in seconds. Empty → Pushover default (no expiry). `3600` = one hour; `86400` = one day; max 604800 (7 days). Numeric input is coerced to string. |
| `defaults.url` | string (URL) | `""` | Supplementary URL attached to the notification. Tappable in the Pushover app. |
| `defaults.url_title` | string | `""` | Display text for the URL. If `url` is empty, `url_title` is ignored. |
| `defaults.html` | bool | `false` | When `true`, the message body is parsed as a small HTML subset (`<b>`, `<i>`, `<a href>`, `<br>`, `<ul>`, `<h1-h6>`, inline `style=`). |
| `defaults.monospace` | bool | `false` | When `true`, the entire message body is rendered in monospace. Incompatible with `html` — enabling one disables the other automatically. |

### 🚨 Emergency Notifications

These settings only apply when the agent sends a message with `priority == emergency` (or `+2`). They control how Pushover retries the notification until it is acknowledged.

| Field | Type | Default | Constraints | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `emergency.retry` | int (seconds) | `60` | `≥ 30` | How often Pushover re-sends the emergency notification while it remains un-acknowledged. |
| `emergency.expire` | int (seconds) | `3600` | `0` (no expiry) or `30..10800` | Maximum lifetime of the emergency notification. After this many seconds Pushover stops retrying. `10800` = 3 hours (Pushover's hard limit). |
| `emergency.callback` | string (URL) | `""` | Optional | Acknowledgement callback URL — Pushover POSTs to it when the user acknowledges. |

The Settings page validates: `retry >= 30` and `expire <= 10800`. Values outside the range are clamped to the nearest boundary.

### 🛠️ Advanced Settings

| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `advanced.timeout` | int (seconds) | `15` | HTTP timeout for all Pushover API calls. `1..60` range; values outside are clamped. Recommended `10..15`. |
| `advanced.debug` | bool | `false` | When `true`, the plugin logs additional request/response metadata to the A0 framework logger. Credentials are always masked, even in debug output. |

### 🏷️ Tags & Callback (top-level)

| Field | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `tags` | list[string] | `[]` | Comma-separated tag list in the UI; joined to Pushover's `tags` parameter on send. Used by Pushover for filtering and grouping in the dashboard. |
| `callback` | string (URL) | `""` | Default acknowledgement callback for **non-emergency** notifications. Mirrors `emergency.callback` but applies to all priorities. |

### 🤖 Agent tool field mapping

When the agent calls `push_zero_notify`, every parameter is **optional** except `message`. Anything omitted falls back to the corresponding `defaults.*` value from this page.

| Tool parameter | Setup page equivalent |
| :--- | :--- |
| `message` | — (always required) |
| `title` | `defaults.title` |
| `priority` | `defaults.priority` (or `-2..2` int) |
| `sound` | `defaults.sound` |
| `device` | `defaults.device` |
| `url` / `url_title` | `defaults.url` / `defaults.url_title` |
| `ttl` | `defaults.ttl` |
| `html` / `monospace` | `defaults.html` / `defaults.monospace` |
| `retry` / `expire` | `emergency.retry` / `emergency.expire` |
| `callback` | `emergency.callback` (for emergency) or `callback` (otherwise) |
| `tags` | `tags` |

### 🧪 Validation rules summary

| Field | Rule |
| :--- | :--- |
| `token` / `user` | required; non-empty after Save; masked-input pattern (`****…`) rejected |
| `priority` | must be one of `lowest` / `low` / `normal` / `high` / `emergency` |
| `ttl` | integer seconds; max 604800 |
| `emergency.retry` | integer seconds; `>= 30` |
| `emergency.expire` | integer seconds; `0` or `30..10800` |
| `advanced.timeout` | integer seconds; `1..60` |
| `html` + `monospace` | mutually exclusive — last-clicked wins |
| `url` / `url_title` | URL string; `url_title` ignored when `url` empty |
| `device` | comma-separated device names; empty = all |

### 📦 Storage

All fields are persisted in **two** locations:

1. **Primary**: `<plugin_dir>/push_zero_config.json` — readable directly by the user. This is the source of truth.
2. **Mirror**: Agent Zero's framework storage (`core_plugins.save_plugin_config`) — kept in sync on every Save.

The Setup page reads from disk on open; writes go to both layers on Save; the page hydrates from disk on the next open, with full masking of credentials.

---

<sub>Built with the `a0-create-plugin` skill workflow. Shipped at v1.1.23.</sub>
