# Pushover Plugin — Setup Help

A step-by-step guide to install, configure, verify and use the Pushover
plugin for Agent Zero. Use this when the inline **Pushover Setup** page
in Agent Zero, or the compact `## Setup` section of `README.md`, leaves a
question unanswered.

If anything in this guide stops working, jump to
[Troubleshooting](#troubleshooting) first — most failures are covered
there.

## Table of contents

1. [What you need](#what-you-need)
2. [Create a Pushover account and obtain your User Key](#create-a-pushover-account-and-obtain-your-user-key)
3. [Create an Application/API Token](#create-an-applicationapi-token)
4. [Install the plugin in Agent Zero](#install-the-plugin-in-agent-zero)
5. [Configure credentials on the Setup page](#configure-credentials-on-the-setup-page)
6. [Verify the connection](#verify-the-connection)
7. [Send a real test notification](#send-a-real-test-notification)
8. [Tune notification defaults and emergency settings](#tune-notification-defaults-and-emergency-settings)
9. [Send your first agent-driven notification](#send-your-first-agent-driven-notification)
10. [Optional — multiple devices, sounds, URLs, TTL, tags](#optional--multiple-devices-sounds-urls-ttl-tags)
11. [Troubleshooting](#troubleshooting)
12. [Frequently asked questions](#frequently-asked-questions)

## What you need

- A running instance of Agent Zero (`python run_ui.py`, WebUI running,
  Docker or local install — both supported).
- A free [Pushover](https://pushover.net/) account.
- A **User Key** from Pushover (a 30-character identifier tied to your
  Pushover account).
- An **Application / API Token** ("API Token/Key" in Pushover jargon,
  prefix `a` followed by hex) created from the
  [apps/build](https://pushover.net/apps/build) page.
- The Pushover client installed on at least one device so you can see the
  test notification arrive.

The whole setup takes about five minutes.

## Create a Pushover account and obtain your User Key

1. Visit <https://pushover.net/>.
2. Click **Get Started** or **Login** and follow the sign-up flow
   (email, password, payment confirmation — Pushover is a paid
   one-time Android/iOS app, the API itself is then free of charge).
3. Install the Pushover app on at least one of your devices (iOS, Android
   or Desktop) and sign in there with the same account.
4. Return to the Pushover dashboard. The **User Key** is displayed near
   the top of the dashboard in a "Your User Key" callout. It is exactly
   30 characters long.
5. Copy the User Key to a clipboard. **Treat it like a password** —
   anyone with it can push to all your registered devices.

> **Tip**: Pushover lets you use a *Group Key* instead of a personal User
> Key, so a whole team can share one Pushover subscription. The plugin
> accepts either. To find or create a group go to the Pushover dashboard
> under **Manage Groups**.

## Create an Application/API Token

Pushover requires every sending application to identify itself with a
dedicated API token. One Pushover account can hold many of them, which
lets you audit and revoke per integration.

1. Open <https://pushover.net/apps/build> in the same browser where you
   are logged in.
2. Fill in:
   - **Name** — anything human-readable, e.g. `Agent Zero`.
   - **Description** — optional but recommended.
   - **URL** *(optional)* — the homepage of the integrating system.
   - **Icon** *(optional)* — an upload that becomes the avatar of the
     notification.
3. Tick the **I have read and agree to the terms** checkbox.
4. Click **Create Application**.
5. Pushover shows the freshly-created application's **API Token/Key** —
   a hex string typically prefixed with `a` (for application tokens).
   Copy it. The plugin will store it (masked) and use it as
   `token` in every `POST /1/messages.json` request.

> **Security note**: the API token never appears in plain text in the
> Setup page once saved, never in logs, and never in any tool response.

## Install the plugin in Agent Zero

If you are running Agent Zero from the bundled development checkout, the
plugin is already shipped at `/a0/usr/plugins/push_zero/`. Just enable it:

1. Open the Agent Zero UI.
2. Go to **Settings &rarr; Plugins**.
3. Find **Pushover** in the list and toggle it on.
4. Click the **Pushover Setup** entry that appears on the plugin card
   (or open **Settings &rarr; External Services &rarr; Pushover**).

If you are installing from a remote source (a public repo, a tarball,
or your own fork):

1. Copy the plugin directory into `/a0/usr/plugins/push_zero/` so that
   `plugin.yaml` sits at `/a0/usr/plugins/push_zero/plugin.yaml`.
2. Reload the WebUI (or restart `run_ui.py`). The framework calls
   `hooks.install()` automatically; no manual `Execute` step is needed.
3. Enable the plugin as above.

> The plugin depends only on Python's standard library. There are no
> external packages to install. If a future version adds one, `hooks.py`
> will install it during `install()`.

## Configure credentials on the Setup page

Open the **Pushover Setup** page (first run shows an onboarding card
explaining the four values you need; once you save any values the card
collapses).

Two fields are required:

- **Application / API Token** — paste the value from
  [pushover.net/apps/build](https://pushover.net/apps/build).
- **User / Group Key** — paste your User Key from the Pushover
  dashboard.

One optional field:

- **Device** — leave blank to deliver to all registered devices, or
  enter a comma-separated device name list (e.g. `iphone,ipad`,
  `work-laptop`). Device names must match what the Pushover clients
  display, otherwise the API returns a 4xx with `device not found`.

When you click **Save Configuration**:

- The fields clear themselves so the token cannot be re-read from the
  page, and the Setup page re-renders with **Connection: Connected**.
- The credential is persisted via
  `helpers.plugins.save_plugin_config` under the plugin's namespace.
- The Setup page header shows masked identifiers
  (`User key: ****AB12`, `Application token: ****CD34`) so you can
  confirm storage without exposing the secrets.

## Verify the connection

Click **Test Connection** on the Setup page. Internally this:

1. Sends `GET /1/apps/limits.json` with your token to confirm the
   application API key is valid against Pushover.
2. Sends the user/group key through the message endpoint as a
   lowest-priority notification, so you get to confirm the user key
   without leaving anything visible on your devices.
3. Returns a structured response that the Setup page renders as a
   pass/fail badge — never echoing credentials.

A green pill reading **Connected** with a checkmark is the success
signal. A red pill reading **Authentication failed** means at least one
of your credentials is wrong (the Setup page never tells you *which*
because of security hygiene, but the answers below cover both
cases).

If you prefer scripting the verification, `POST /api/plugins/push_zero/test`
produces the same response as a JSON body you can parse from a CI run.

## Send a real test notification

Click **Send Test Notification** to deliver a real lowest-priority
notification with the title *Agent Zero* and the message *Pushover
integration is working.* to the configured device.

This is the only test action that produces a side effect on Pushover,
so the Setup page exposes it as a separate button with an explicit
*Send* label. Use it to:

- Confirm the Pushover client app on the device you targeted is online.
- Validate the device name (if you entered one).
- Check that your chosen defaults (sound, url, etc.) apply correctly.

If your device is asleep, allow Pushover a few seconds to deliver
after the badge flips to *Test notification sent successfully*. If no
message arrives, walk the troubleshooting table below.

## Tune notification defaults and emergency settings

The same Setup page exposes:

| Section | What it controls |
|---|---|
| **Notification Defaults** | The default `title`, `priority`, `sound`, `device`, `ttl`, `url`, `url_title`, `html`, `monospace` applied whenever the agent calls `push_zero_notify` without explicitly overriding them. |
| **Emergency Notifications** | The `retry` interval (≥ 30 s, default 60 s) and `expire` ceiling (≤ 10 800 s, default 3 600 s) for `priority=emergency` notifications. See *Emergency notifications* in the README for the retry-loop semantics. |
| **Device & Sound** | Lets you pin one device or a comma-separated device list, and pick a default `sound` (selected from `/1/sounds.json` with a `User default` option). |
| **API Usage** | Mirrors of `GET /1/apps/limits.json` — your monthly message budget, current usage, and reset date. Failures here never block sending. |
| **Advanced Settings** | HTTP timeout (10–15 s recommended), `default callback` URL, default `tags` list, and an opt-in `API debug logging` toggle. Even on, debug prints mask every credential field. |

There is also a **Reset Pushover Configuration** action at the bottom
that wipes the saved credentials after a confirmation prompt.

## Send your first agent-driven notification

From the agent chat, ask it to send a Pushover notification — for
example:

> Send a Pushover notification saying the daily backup completed.

The agent calls the `push_zero_notify` tool with `action="send"`. You can
also call it directly from a custom tool chain. The minimum call is:

```json
{
  "action": "send",
  "message": "Daily backup completed.",
  "title": "Agent Zero",
  "priority": "normal"
}
```

To check the receipt of an emergency notification (handy when
`expire=3600` and you need to know if the on-call has acknowledged):

```json
{
  "action": "receipt_status",
  "receipt": "<receipt-id-returned-by-the-original-send>"
}
```

To cancel an active emergency notification (when the upstream outage is
already resolved by another channel):

```json
{
  "action": "cancel",
  "receipt": "<receipt-id>"
}
```

## Optional — multiple devices, sounds, URLs, TTL, tags

- **Multiple devices.** Push a comma list into the `device` field:
  `iphone,ipad,work-laptop`. Names must match what the Pushover client
  shows in its settings page.
- **Sounds.** The Setup page lists every sound returned by
  `GET /1/sounds.json` (with `User default` always available).
- **URLs.** Pass `url` and `url_title` to make the notification
  tappable, e.g. `url="https://agent.example.com/chats/123"` and
  `url_title="Open chat"`.
- **TTL.** Use `ttl` (seconds) to cap how long Pushover retains a
  notification if the device is offline. Leave blank for Pushover's
  default (typically 30 days).
- **Tags.** Provide a list (`["agent-zero", "alerts"]`) or a string
  (`"agent-zero, alerts"`) — quoted spacing is preserved by the
  plugin.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Setup page shows **Not configured** after a save | The `Save Configuration` call did not include both `token` and `user`. | Re-enter both values and click Save again; refresh the page. |
| **Test Connection** returns *Authentication failed* | Either the application token or the user/group key is wrong or revoked. | Re-copy both values from pushover.net; remember tokens are app-specific, not global. |
| **Authentication failed** with everything correct | API token bound to a different Pushover account than the User Key. | Make sure both were issued to the same Pushover login. |
| **Send Test Notification** succeeds but no message arrives | The target device is offline, or Pushover client is not logged in. | Open the Pushover client on the device and confirm the user matches the User Key. |
| Test fails with *device not found* | A name in the `device` field does not match a registered device. | Leave the device field blank, or copy the exact device name from *Settings &rarr; Devices* in the Pushover client. |
| `priority=2 / emergency` rejected with *invalid retry* | You sent retry < 30 seconds or > 86400. | Use at least 30 and at most 86 400 seconds. |
| Emergency notification accepted but never resumes | `expire` was 0 or omitted; Pushover uses 86400 by default which is allowed. | Leave `expire` blank or pick a value ≤ 10 800 seconds. |
| HTML and monospace both checked on | Pushover rejects the request because they conflict. | Pick at most one; the Setup page warns when both are enabled. |
| *Pushover service is currently unavailable* | Pushover's API is hitting a 5xx. | The plugin already retries via your automation — for one-off, click the button again after a minute. |
| *Pushover request timed out* | The configured `advanced.timeout` is too small for your network. | Bump it to 15–20 s in **Advanced Settings**. |
| *Pushover DNS resolution failed* | Your Agent Zero host cannot reach `api.pushover.net`. | Verify outbound DNS/HTTPS from the host, or check your container's network policy. |
| *API quota exceeded* | You hit the monthly message limit. | Wait for the reset date shown in **API Usage**, or upgrade your Pushover subscription. |
| Diagnostic print on the console shows only `Pushover request sent` and never any credentials | This is by design. | Enable **API debug logging** in Advanced Settings for a masked dump of the request fields (token + user are redacted to `****`). |

## Frequently asked questions

**Q: I already have a Pushover account but I forgot my User Key.**
A: Open the Pushover dashboard while signed in — your User Key is shown
near the top. If you lost access to the account, contact Pushover support.

**Q: I saved the wrong device name. Will Pushover return an error?**
A: Yes — `device not found` is a 4xx, surfaced in the Setup page as
*Invalid Pushover device*. Either correct the field or leave it blank
to target every device.

**Q: Can multiple agents share the same Pushover configuration?**
A: Yes — because configuration is plugin-scoped rather than agent-,
project-, or chat-scoped.

**Q: Is the agent allowed to send emergencies unprompted?**
A: The agent tool's system prompt forbids arbitrary `priority=2` without
explicit user request. The plugin itself never auto-escalates.

**Q: How do I uninstall?**
A: Disable and remove the plugin in **Settings &rarr; Plugins**; the
`hooks.uninstall()` hook clears the saved configuration.

**Q: Where is the configuration actually saved?**
A: In Agent Zero's per-plugin scope through
`helpers.plugins.save_plugin_config(push_zero)`. Removing the user file at
the location referenced by `helpers.settings` will also reset it
immediately; the Setup page is the recommended path.

**Q: My Pushover application was revoked; how do I recover?**
A: Create a new application on pushover.net/apps/build, paste its API
token on the Setup page, and click Save Configuration. Pushover's old
API token is invalid and cannot be reactivated.

**Q: Does this work in Docker?**
A: Yes — out-of-the-box, on the same network as the Agent Zero
container. The plugin does not need privileged Docker access.

**Q: Does it support a proxy?**
A: Not yet directly. Configure `HTTP_PROXY` / `HTTPS_PROXY` on the host
or in the Agent Zero container before starting the WebUI; the plugin
honours standard proxy environment variables when present.

**Q: Can the agent accidentally leak the API token in its replies?**
A: The tool's response sanitiser strips the `token` and `user` fields
before the agent sees them, so even an LLM that misuses its context
window cannot exfiltrate them. If you still worry, run `Reset Pushover
Configuration` on the Setup page and rotate the API token at
pushover.net/apps/build.
