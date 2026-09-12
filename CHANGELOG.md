# Changelog

All notable changes to the Pushover plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_(no changes yet)_

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
  The `github:` value defaults to `TODO-OWNER/pushover` so
  accidental publication is impossible until the user overwrites
  it.
- **Local git repository** initialised inside
  `/a0/usr/plugins/pushover/`, with every production file
  staged and a single GPG-less commit. The commit author uses a
  neutral placeholder identity so the user can `git commit
  --amend --reset-author` (or the equivalent `user.name`/`email`
  `git config`) before `git remote add origin … && git push`.
- **Portable release artefact** at
  `/a0/usr/plugins/pushover/dist/pushover-1.0.5.tar.gz` so the
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
- Agent-callable tool `pushover_notify` with actions `send`, `test`,
  `receipt_status`, `cancel`, `cancel_by_tag`.
- Dedicated Setup page at `webui/setup.html` with first-run onboarding,
  Test Connection, Send Test Notification, Notification Defaults,
  Emergency configuration, API Usage, Advanced Settings, Reset Setup,
  and Help sections.
- Persistent plugin configuration via
  `helpers.plugins.get_plugin_config` / `save_plugin_config`.
- HTTPS Pushover client at `helpers/pushover_client.py` (urgency,
  sounds, limits, receipts, cancellation, masked credentials,
  humanised errors, DNS/timeout/TLS handling).
- Validation helper `helpers/validation.py` covering message, title,
  priority, sound, device, URL, URL title, TTL, HTML/monospace
  conflict, tags, and emergency retry/expire bounds.
- API handlers under `api/`:
  - `POST /api/plugins/pushover/validate`
  - `POST /api/plugins/pushover/test`
  - `GET  /api/plugins/pushover/sounds`
  - `GET  /api/plugins/pushover/limits`
  - `POST /api/plugins/pushover/save`
  - `POST /api/plugins/pushover/reset`
  - `GET  /api/plugins/pushover/status`
  - `POST /api/plugins/pushover/test_notify`
- Lifecycle hooks (`hooks.py`) for `install`, `pre_update`, `uninstall`.
- System-prompt fragment `prompts/fw.pushover.tool.md`.
- Test suite (49 tests across `test_client.py`, `test_validation.py`,
  `test_tool.py`, `test_config_helper.py`, `test_emergency_default.py`).

### Security
- Credentials never logged in raw form; identifiers masked after save
  (`mask_identifier`).
- TLS verification enforced via `ssl.create_default_context()`.
- HTML and monospace formatting cannot be enabled simultaneously.
- Emergency retry and expire bounds enforced before every send.
