# Changelog

All notable changes to the Pushover plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_(no changes yet)_

## [1.1.6] - 2026-09-12

### Fixed
- **Saved Pushover configuration is no longer wiped on plugin
  update.** Agent Zero's framework invokes ``uninstall()`` as part
  of the code-update flow (followed by ``install()`` on the new
  files), and the previous ``hooks.py`` called
  ``reset_config()`` inside ``uninstall()``. That wiped the saved
  ``config.json`` (token, user key, defaults, emergency settings,
  advanced settings) every time the plugin was updated, forcing
  the user to re-enter their Pushover credentials on every
  release.

  1.1.6 fixes that with two complementary safeguards:

  1. ``uninstall()`` no longer calls ``reset_config()`` and is
     effectively a log-only no-op for the saved configuration.
     The Setup page's explicit **Reset Pushover Configuration**
     button still wipes the config through the dedicated
     ``/api/plugins/push_zero/reset`` endpoint, so a full reset is
     always available when the user genuinely wants one.

  2. As defense in depth, ``pre_update()`` and ``install()`` now
     back up ``config.json`` to a fresh, owner-only file in
     ``/tmp`` (``push_zero_config_backup_*.json``) before any
     potentially-destructive step and restore it once the install
     completes. The restore step is skipped when a fresh
     config.json has already been written during the install,
     so the backup never overwrites a freshly-saved config.

### Notes
- Lifecycle-only change. No runtime, configuration, route, theme,
  or API behaviour changed. The 49-test suite carries forward
  unchanged.
- ``hooks.py`` remains the sole owner of ``install`` /
  ``pre_update`` / ``uninstall`` per the Agent Zero lifecycle
  contract; no ``execute.py`` was added or relied upon.

## [1.1.5] - 2026-09-12

### Fixed
- **API Usage panel no longer renders "0 / null" when the
  application has no monthly cap.** The Setup page's Usage
  section previously fetched `POST /api/plugins/push_zero/limits`
  and rendered the result unconditionally as
  `Messages used: <used> / <limit>`. Pushover's
  `/1/apps/limits.json` endpoint returns
  `{"status": 1, "limit": null, "used": null, ...}` for
  applications without a monthly message cap (very common for
  paid or unlimited apps), which the JS store was previously
  projecting as `{limit: null, used: 0}` and the HTML rendered
  as the literal string `Messages used: 0 / null`.

  1.1.5 fixes that by:
  - adding a new `limitsMessage` field to the JS store,
  - branching in `refreshLimits()` between *success with cap*
    (numeric quota), *success without cap* (friendly note), and
    *failure* (error message),
  - adding a third `<template x-if>` in `webui/main.html` for
    the no-cap case so the user sees an explanation instead of
    bogus numbers.

### Changed
- `helpers/push_zero_client.py` `get_app_limits()` now uses the
  `PUSHOVER_LIMITS_PATH` constant instead of the previously
  hard-coded `\"/1/apps/limits.json\"` literal, so any future
  base-URL or path change happens in exactly one place.

### Notes
- Setup-page-only fix. No runtime, configuration, route, or
  theme behaviour changed. The Pushover client contract is
  unchanged. The 49-test suite carries forward; only the
  client constant was rewired and the JS + HTML rendering path
  was widened.

## [1.1.4] - 2026-09-12

### Changed
- **README.md rewritten with colors, icons, and the embedded
  thumbnail.** The top of the file now shows the A0-branded
  thumbnail (128 × 128, 1,344 B) centred above the title, followed by
  a row of `shields.io` badges (repository, version, license,
  Agent Zero compatibility, Python, tests). Section headings, table
  cells, callouts and lists now use color-coded HTML
  (`<span style="color:#E74C3C">push</span><span style="color:#2A5C8F">_zero</span>`,
  green `#28a745` for success, red `#dc3545` for failure, orange
  `#f39c12` for warnings) so the document reads like a polished
  product page rather than a flat changelog bullet list. Emoji
  icons (`🔔 ⚙️ ✅ 📨 🚨 📜 ✖️ 🎵 📱 🔗 ⏳ 📊 🔐 🎨 🧪 🏷️ 🛡️ 🧱 📋
  🚀 🛠️ 🤖 🚨 🔐 🧪 🆘 🗑️ 📜 🔗`) anchor every section header and
  table row for at-a-glance scanning. A Mermaid `flowchart LR`
  diagram now visualises the runtime split between the WebUI/API/
  Tool surface and the helper/client/validator internals, including
  the HTTPS POST into `api.pushover.net/1/messages.json`.

### Added
- New sections in README that weren't there before:
  - 🎯 **Features at a glance** — 17-row icon+capability+notes table.
  - 🧱 **Architecture (Mermaid)** — the architecture diagram
    described above.
  - 📋 **Requirements** — Agent Zero version, Python version,
    Pushover account prerequisites, and a confirmation that the
    plugin ships **zero** additional Python dependencies.
  - 🤖 **Agent tool — `push_zero_notify`** — full parameter table
    and minimal + emergency examples with their return shapes.
  - 🚨 **Emergency notifications** — priority + retry + expire
    contract and receipt flow.
  - 🛠️ **Setup page** — section-by-section breakdown matching the
    `webui/main.html` layout.
  - 🆘 **Troubleshooting** — 9-row symptom / cause / fix matrix
    mirroring the agent's own diagnostic paths.
  - 🗑️ **Uninstall** — single-shell recipe plus the
    `hooks.py` cleanup guarantee.
  - 🔗 **Links** — repo, future Index entry, Pushover docs,
    Agent Zero core.

### Notes
- Documentation-only change. No runtime, configuration, theme,
  route, import, or API behaviour changed. The 49-test suite
  carries forward unchanged; the only file content delta is
  README.md, plus the version bump in `plugin.yaml` and this
  CHANGELOG entry.

## [1.1.3] - 2026-09-12

### Changed
- **Thumbnail now embeds a stylized Agent Zero 'zero' mark.** Both
  `thumbnail.png` (plugin root) and `webui/thumbnail.png` are now
  byte-identical (1,344 B) and combine:
  * the existing Pushover coral brand panel (rounded squircle, 28 px),
  * a bold white outline ring centred slightly left, visually rhyming
    with the Agent Zero '0' mark,
  * a chunky white forward-chevron inside the ring with a dark inset
    detail, evoking the Agent Zero chevron motif, and
  * a tiny white-haloed notification badge top-right (red dot with
    exclamation mark) so the icon still reads as 'push
    notification' even at thumbnail size.
- PNG is still 128 x 128 RGBA, optimised, well under the 20 KB Agent
  Zero Hub ceiling. Pixel-sampled against the design intent (coral
  panel, dark chevron inset, white badge halo) and confirmed at
  every sampled anchor point.

### Notes
- Asset replacement only. No runtime, API, configuration, route,
  import or theme behaviour changed. All runtime expectations from
  1.1.2 carry forward unchanged.

## [1.1.2] - 2026-09-12

### Fixed
- **Plugin-Hub submission entry now references the real target
  repository.** `index.yaml` previously shipped with
  `github: https://github.com/TODO-OWNER/push_zero` — a deliberately
  inert placeholder so accidental publication was impossible. The
  user supplied the public-repo URL `https://github.com/jphermans/Push-Agent`
  in this session; `index.yaml` now points there. Override locally
  if the plugin is later relocated.

### Notes
- Documentation-only change. No runtime, configuration, or theme
  change. All 49 existing tests still pass.

## [1.1.1] - 2026-09-12

### Fixed
- **Setup page now follows the host theme.** Previously the page
  used `light-dark(<light>, <dark>)` with `color-scheme: light
  dark`, which responded to the browser's `prefers-color-scheme`
  instead of the Agent Zero host's actual theme. As a result the
  page always looked dark whenever the browser reported dark
  preference, regardless of which theme the user toggled in A0.
  1.1.1 rewrites the CSS to consume the host's theme tokens
  (`var(--color-background)`, `var(--color-text)`,
  `var(--color-panel)`, `var(--color-border)`,
  `var(--color-input)`, `var(--color-input-focus)`,
  `var(--color-accent)`, `var(--color-highlight)`,
  `var(--color-text-muted)`, `var(--color-warning-text)`,
  `var(--color-background-hover)`) — the same neutral pointers
  the host repoints when it swaps `body.dark-mode` <->
  `body.light-mode`.
- **Plugin icon now visible on the Plugins card and in the
  External Services panel.** The framework detector reads
  thumbnail from `webui/thumbnail.<ext>`
  (`/a0/helpers/plugins.py:289-294`); the previous layout only
  shipped the plugin-root `thumbnail.png`. 1.1.1 adds
  `webui/thumbnail.png` as a copy so the icon now renders.

### Notes
- Pure presentation/asset fixes. No API, runtime, or configuration
  schema change. All 49 existing tests still pass.

## [1.1.0] - 2026-09-12

### Changed
- **Plugin renamed from `pushover` to `push_zero`** for trademark
  hygiene (the previously-reserved `pushover` slug was reserved for
  the third-party service of the same name; the new slug keeps the
  "push + _zero" cadence without occupying the trademark).
- Migrated every slug reference in a single atomic commit:
  - directory `/a0/usr/plugins/pushover/` →
    `/a0/usr/plugins/push_zero/`
  - `plugin.yaml` `name: pushover` → `name: push_zero`
  - `helpers/pushover_client.py` → `helpers/push_zero_client.py`
  - `tools/pushover_notify.py`    → `tools/push_zero_notify.py`
  - `prompts/fw.pushover.tool.md` → `prompts/fw.push_zero.tool.md`
  - Python imports `usr.plugins.pushover.*` →
    `usr.plugins.push_zero.*` (every helpers/tools/api/test file)
  - `helpers/config_helper.py` `PLUGIN_NAME` constant (`pushover` →
    `push_zero`)
  - `hooks.py` Logger name (`plugin.pushover` → `plugin.push_zero`)
  - API route group `/api/plugins/pushover` → `/api/plugins/push_zero`
  - WebUI asset URL `/plugins/pushover/webui/setup-store.js` →
    `/plugins/push_zero/webui/setup-store.js`
  - Alpine store handle `pushoverSetup` → `push_zeroSetup`
  - Debug log labels `[pushover]` → `[push_zero]`

### Notes
- **Display strings preserved**: the prose word "Pushover" (the third
  party service name) is unchanged throughout. Only the **plugin
  slug** was renamed.
- **No runtime semantic change.** All 49 unit tests still pass.
- The user still needs to replace the `created_by` / `author` /
  `homepage` TODO placeholders in `plugin.yaml` and the
  `TODO-OWNER` placeholder in `index.yaml` once the GitHub owner is
  resolved.


## [1.0.5] - 2026-09-12

### Added
- **`.gitignore`** at the plugin root: excludes Python bytecode,
  the A0 plugin-manager runtime toggle (`.toggle-*`), editor/OS
  noise, test/coverage caches, local secret overrides, and
  build/distribution artefacts. Lets `git add .` be safe inside
  the plugin directory.
- **`index.yaml`** at the plugin root: a submission-ready
  Agent-Zero Plugin Hub entry (`title`, `description`, `github`,
  five tags). The runtime never reads it — `agent0ai/a0-plugins`
  does. Includes an inline publication checklist and the
  current field-size limits from `references/contribute.md`.
  The `github:` value defaults to `TODO-OWNER/push_zero` so
  accidental publication is impossible until the user overwrites
  it.
- **Local git repository** initialised inside
  `/a0/usr/plugins/push_zero/`, with every production file
  staged and a single GPG-less commit. The commit author uses a
  neutral placeholder identity so the user can `git commit
  --amend --reset-author` (or the equivalent `user.name`/`email`
  `git config`) before `git remote add origin … && git push`.
- **Portable release artefact** at
  `/a0/usr/plugins/push_zero/dist/push_zero-1.0.5.tar.gz` so the
  plugin can be shared without a GitHub remote.

### Notes
- Pure packaging polish. No API, runtime, configuration, or
  webui change. All 49 existing tests still pass.
- The remote-push step (GitHub repo creation, branch publish,
  Index PR) remains an external gate that requires user-side
  credentials; everything else needed for publication is now
  committed and reviewable locally.

## [1.0.4] - 2026-09-12

### Fixed
- **Light-mode visibility on the Setup page.** Previously the
  `webui/main.html` and `webui/config.html` stylesheets used hard
  coded dark-mode-only fallbacks (`#e6e6e6` text on `\`var(--bg-color)\`
  backgrounds, etc.), so the page was unreadable when Agent Zero
  was in light mode. 1.0.4 rewrites the CSS to:
  - declare `color-scheme: light dark;` on `.po-page`;
  - use the `light-dark(<light>, <dark>)` CSS function for every
    plugin-specific color so it tracks the current theme;
  - give the page and every form control an explicit background
    in both modes so contrast is stable.

### Added
- `created_by`, `author`, and `homepage` fields in `plugin.yaml`.
  These render on the Plugin card and Hub entry. They default to
  `TODO: replace with …` placeholders so the plugin can be
  installed without errors; replace them before publishing.

### Notes
- Pure UI / metadata changes. No API, runtime, or configuration
  schema change. All 49 existing tests still pass.

## [1.0.3] - 2026-09-11

### Fixed
- **Setup page / Config button visibility.** The framework's plugin UI
  detector (`/a0/helpers/plugins.py`) checks for exactly two filenames
  in `webui/`:
  - `webui/main.html` → `has_main_screen` (the **Setup** button on the
    plugin card)
  - `webui/config.html` → `has_config_screen` (the **Config** button
    in **Settings &rarr; External Services &rarr; Pushover**)

  The 1.0.0–1.0.2 release shipped only `webui/setup.html`, so the
  Plugins page reported *Main screen: Not available* and *Config
  screen: Not available*, and the External Services panel never
  rendered a Config button.

  1.0.3 renames `webui/setup.html` → `webui/main.html` and copies it
  to `webui/config.html`. Both pages are byte-identical; the framework
  picks the right entry point based on which button the user clicks.

### Notes
- Pure webui wiring fix. No API, runtime or configuration schema
  change. All 49 existing tests still pass.

## [1.0.2] - 2026-09-11

### Added
- `SETUP.md` — comprehensive end-to-end help text covering Pushover
  account creation, User Key retrieval, Application/API Token
  creation, plugin installation, on-Setup-page configuration, the
  verification flow, default tuning, agent-driven sending, optional
  devices/sounds/URLs/TTL/tags, a symptom → cause → fix
  troubleshooting matrix, and a FAQ (credential recovery, proxy,
  Docker, uninstall).

### Changed
- `README.md` `## Setup` section now begins with a link to `SETUP.md`
  for the deep-dive walkthrough.
- `README.md` Files tree now lists `SETUP.md`.

### Notes
- Documentation-only release. No runtime behaviour, API surface, or
  configuration schema changed. All 49 existing tests still pass.

## [1.0.1] - 2026-09-11

### Added
- `thumbnail.png` — a 128×128 PNG that meets the A0 Plugin Hub Index
  thumbnail spec (≤ 20 KB, square, PNG/JPEG/WebP). Place it beside
  `index.yaml` when filing the Index PR.
- `CHANGELOG.md` — this file, so future bumps can describe what changed.

### Changed
- `README.md` Files section now lists `thumbnail.png` and `CHANGELOG.md`
  so community discoverers can find every shipped artifact.

### Notes
- Pure asset/documentation release. No runtime behaviour, API surface, or
  configuration schema changed. All 49 existing tests still pass.

## [1.0.0] - 2026-09-11

### Added
- Initial release of the Pushover plugin for Agent Zero.
- Agent-callable tool `push_zero_notify` with actions `send`, `test`,
  `receipt_status`, `cancel`, `cancel_by_tag`.
- Dedicated Setup page at `webui/setup.html` with first-run onboarding,
  Test Connection, Send Test Notification, Notification Defaults,
  Emergency configuration, API Usage, Advanced Settings, Reset Setup,
  and Help sections.
- Persistent plugin configuration via
  `helpers.plugins.get_plugin_config` / `save_plugin_config`.
- HTTPS Pushover client at `helpers/push_zero_client.py` (urgency,
  sounds, limits, receipts, cancellation, masked credentials,
  humanised errors, DNS/timeout/TLS handling).
- Validation helper `helpers/validation.py` covering message, title,
  priority, sound, device, URL, URL title, TTL, HTML/monospace
  conflict, tags, and emergency retry/expire bounds.
- API handlers under `api/`:
  - `POST /api/plugins/push_zero/validate`
  - `POST /api/plugins/push_zero/test`
  - `GET  /api/plugins/push_zero/sounds`
  - `GET  /api/plugins/push_zero/limits`
  - `POST /api/plugins/push_zero/save`
  - `POST /api/plugins/push_zero/reset`
  - `GET  /api/plugins/push_zero/status`
  - `POST /api/plugins/push_zero/test_notify`
- Lifecycle hooks (`hooks.py`) for `install`, `pre_update`, `uninstall`.
- System-prompt fragment `prompts/fw.push_zero.tool.md`.
- Test suite (49 tests across `test_client.py`, `test_validation.py`,
  `test_tool.py`, `test_config_helper.py`, `test_emergency_default.py`).

### Security
- Credentials never logged in raw form; identifiers masked after save
  (`mask_identifier`).
- TLS verification enforced via `ssl.create_default_context()`.
- HTML and monospace formatting cannot be enabled simultaneously.
- Emergency retry and expire bounds enforced before every send.
