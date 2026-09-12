# Changelog

All notable changes to the Pushover plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_(no changes yet)_

## [1.1.14] - 2026-09-12

### Changed
- **Setup page credential inputs now show the masked display
  inline** (e.g. `****…esmm` for the application token,
  `****…vhD9` for the user/group key) instead of being empty.
  The user asked for partial visibility — they want to see
  *something* in the field to confirm what's saved, but never the
  full plaintext. The masked form is rendered into the input by
  `setup-store.js:refresh()` and `setup-store.js:save()`, and the
  `.po-saved-badge` below the input continues to render the same
  masked form for redundancy and screen-reader accessibility.
- On focus, the credential input clears so the user can immediately
  type a replacement value without first backspacing over the
  mask. On blur, if the field is still empty, the masked form is
  restored. Two new helpers — `handleCredentialFocus()` and
  `handleCredentialBlur()` — implement this transition
  idempotently.

### Defense-in-depth (unchanged from 1.1.11)
- `api/save.py`'s `_MASKED_INPUT_RE` regex continues to silently
  drop any asterisk-heavy input on Save. So an unsubmitted-mask
  click is a no-op for credentials, never a corruption. The
  re-introduction of the masked-form-into-input pattern is safe
  only because that defensive regex is in place.

### Notes
- This is a UX-only release. No API contract changes for tools,
  no schema changes, no settings UI changes outside the Setup
  page's two credential inputs.
- The `<input type="text" autocomplete="off" …>` declarations are
  retained so browser password managers are still hinted not to
  refilled the field. The 1.1.13 stale-bytecode self-heal in
  `hooks.py:_ensure_helpers_readable()` is unaffected.
- The 1.1.10 Test Connection endpoint, the 1.1.11
  anti-corruption guard, and the 1.1.13 bytecode heal all
  remain in place and continue to work.

## [1.1.13] - 2026-09-12

### Critical
- **Fix `AttributeError: 'PushoverClient' object has no attribute
  'validate_credentials'`** that broke the Setup page's **Test
  Connection** button. The class method existed in source but the
  running Agent Zero runtime was loading a stale ``__pycache__/push_
  zero_client.cpython-3XX.pyc`` because the source file's mode had
  drifted to ``0600 root-owned`` (the runtime runs as a non-root
  user, so Python could not ``stat()`` the source to invalidate the
  bytecode cache). Stale bytecode = old class = missing method =
  AttributeError on every Test Connection click.

### Fixed
- Added a defensive ``_ensure_helpers_readable()`` helper to
  ``hooks.py``. It normalises ``helpers/*.py`` to mode ``0o644``
  (matching the surrounding plugin tree) and removes stale
  ``__pycache__/<module>.cpython-*.pyc`` entries for the modules
  the runtime imports at request time. It is invoked from both
  ``install()`` and ``pre_update()`` so the runtime self-heals on
  every lifecycle event — future root edits cannot recreate the
  staleness.
- All helper modules are now listed in a single
  ``_HELPER_MODULES`` constant at the top of ``hooks.py``, so the
  self-heal can be extended without surgery.

### Notes
- ``config.json`` handling is unchanged: it is still preserved
  across updates via the existing backup-and-restore path.
- No API contract changes for tools, no schema changes, no
  settings UI changes.
- The 1.1.10 ``validate_credentials`` endpoint fix (Test
  Connection → ``/1/users/validate.json``) now actually reaches
  the running client again, because the stale bytecode that was
  shadowing it has been removed.

## [1.1.12] - 2026-09-12

### Changed
- **Thumbnail replaced.** Both copies of the thumbnail
  (`/a0/usr/plugins/push_zero/thumbnail.png` and
  `/a0/usr/plugins/push_zero/webui/thumbnail.png`) have been regenerated
  from a user-supplied 1254×1254 RGB source image, resized to
  **128×128 px** with LANCZOS downsampling, quantized to a 32-colour
  adaptive palette, and written byte-identically to both locations.
  Final size is in the low single-digit KB range, well within the
  Hub's 20 KB ceiling. Pixel-sampled to confirm the rendered icon
  matches the user-supplied source.

### Notes
- Asset-only release. No API contract changes, no settings UI
  changes, no tool behaviour changes, no test changes.
- The thumbnail is rendered in three surfaces by Agent Zero:
  the Plugins card, the External Services entry, and (when
  published) the Hub listing. All three consume
  `webui/thumbnail.png` directly. The root copy
  (`thumbnail.png`) is preserved for first-class project visibility.
- Version 1.1.11's credential-corruption fix is unaffected.

## [1.1.11] - 2026-09-12

### Critical
- **Stop saving the masked credential back into the input field.**
  The previous 1.1.7 UX change had `webui/setup-store.js:save()`
  and `refresh()` pre-populate the credential `input` with the
  masked display (`****AB12`). On the next Save (e.g. after
  changing any unrelated field), `api/save.py` would treat that
  masked display as a real credential and silently overwrite the
  saved token / user key with the masked form, eventually emptying
  them after several cycles. Fixed by:
  * Removing the input-pre-population from `save()` and `refresh()`
    in `webui/setup-store.js`. The masked display is still shown
    to the user via the `.po-saved-badge` element in `main.html`,
    just **outside** the input fields.
  * Adding a defensive regex guard (`_MASKED_INPUT_RE`) in
    `api/save.py` that silently drops any input that looks like a
    masked display. This protects against any future regression
    that puts the masked form back into the input.

### Fixed
- The "credentials disappear after every save" symptom. The token
  and user key in `config.json` are no longer silently overwritten
  by the masked display. If your saved token was already corrupt
  from earlier saves, re-enter your real Application Token and
  User (or Group) Key on the Setup page.

### Defense-in-depth
- Server-side `_MASKED_INPUT_RE` regex matches any input that
  starts with one or more `*` and contains no other alphanumeric
  characters. Anything matching is treated as empty by the save
  handler, so the real saved value is preserved.

## [1.1.10] - 2026-09-12

### Fixed
- **Test Connection no longer reports a misleading "resource not
  found".** The Setup page's "Test Connection" button previously
  called `POST /1/apps/limits.json` to validate the application
  token. That endpoint only validates the token, returns a 200
  response without checking the user (or group) key, and could
  surface a misleading 404 with a generic "resource not found"
  body when the application had been disabled, the endpoint had
  been rate-limited, or the URL had drifted for any other reason.
  Two call paths (`api/test.py` step 1 and
  `helpers/push_zero_client.py:validate_connection`) now use
  Pushover's dedicated **`POST /1/users/validate.json`** endpoint
  instead, which validates both the application token AND the
  user (or group) key in a single non-destructive call, does NOT
  leave a notification behind, and does NOT count against the
  application's monthly quota.

  The Setup page now reports a single "Credentials" result on
  success ("Application token and user (or group) key are
  valid.") and splits the failure case into clearly-named
  "Application Token" / "User Key" results so the user knows
  exactly which credential needs to be corrected.

### Added
- **`PUSHOVER_VALIDATE_PATH`** constant in
  `helpers/push_zero_client.py` (the canonical path for the
  validation endpoint; single source of truth for future changes).
- **`PushoverClient.validate_credentials()`** method: thin
  wrapper that POSTs `token` + `user` to `/1/users/validate.json`
  and returns the standard `PushoverResult` envelope. Re-exported
  in `__all__` so tools and API handlers can call it directly.

### Notes
- The previous step-2 message-send smoke test (`POST /1/messages.json`
  with `priority=-2`) was removed because the new validate endpoint
  already confirms the user key works. Removing it also avoids
  the previous behaviour of leaving a real (lowest-priority) test
  notification behind on every Test Connection click, which users
  sometimes found surprising.
- The `get_app_limits()` method is unchanged and is still used by
  the Setup page's **API Usage** panel — that's the right endpoint
  for retrieving the application's monthly quota.

## [1.1.9] - 2026-09-12

### Added
- **Automated version-label sync.** New `scripts/sync_version.py`
  reads the canonical `version:` field from `plugin.yaml` and
  rewrites any tracked file that contains a stale literal version
  string. Currently covers the shields.io version badge and the
  `Shipped at vX.Y.Z` subtitle in `README.md`. Idempotent:
  running it twice with the same `plugin.yaml` version produces
  the same content. Supports three modes:

  - `python3 scripts/sync_version.py` (dry-run, shows planned diffs)
  - `python3 scripts/sync_version.py --apply` (writes changes)
  - `python3 scripts/sync_version.py --check` (CI-friendly exit
    code; `0` when in sync, `1` when drift is detected)

  The script intentionally avoids touching `plugin.yaml`,
  `CHANGELOG.md`, or any test code so it cannot accidentally
  rewrite release history or runtime configuration. The allowlist
  lives at the top of the script and is the single source of
  truth for which files carry version-bearing strings.

### Fixed
- **Drift between README version badge and `plugin.yaml`.**
  The README's shields.io version badge and "Shipped at vX.Y.Z"
  subtitle were hard-coded to `1.1.4` and had drifted through
  five subsequent releases (1.1.5 .. 1.1.8). The sync script
  brings them back in sync to `1.1.9` and prevents future drift
  via the `--check` CI hook.

### Notes
- Tooling and docs only. No runtime, configuration, route, theme,
  or API behaviour changed. The 49-test suite carries forward
  unchanged.

## [1.1.8] - 2026-09-12

### Changed
- **Thumbnail updated to a user-supplied Pushover + Agent Zero
  branded mark.** The previous 1.1.3 thumbnail was a stylized
  coral panel with an Agent Zero "zero" ring and chevron. The
  new thumbnail uses a tightly-cropped 128×128 square from the
  centre of a user-supplied marketing banner, focusing on the
  distinctive Pushover app tile (rounded blue square, italic
  white P) with the red notification bell badge.

  - Crop window: `510, 60, 1000, 550` from the 1672×941 source
    (a 490×490 box centred on the Pushover tile).
  - Resized to 128×128 with LANCZOS downsampling.
  - Quantized to a 32-colour adaptive palette and saved as an
    optimized PNG (compress_level=9). Final size: **3 175 bytes
    (~3.1 KB)**, well under the A0 community ceiling of
    20 KB.
  - Both copies (repo-root `thumbnail.png` and
    `webui/thumbnail.png`) are byte-identical (sha256
    `8830d51243bd7ea96104ea394159a23ebb1404cfe84acd335f01f9597550dbc4`)
    so the icon displays identically in the Plugins card, the
    External-Services entry, and the Hub listing.

### Notes
- Asset-only PATCH. No runtime, configuration, route, theme, or
  API behaviour changed. The on-disk `config.json` is not
  touched by this change.
- The 49-test suite carries forward unchanged; the thumbnail
  is consumed only by the WebUI and Hub tooling, never by the
  test suite.

## [1.1.7] - 2026-09-12

### Fixed
- **Setup page no longer appears to wipe saved credentials.**
  After saving, the credential input fields were deliberately
  cleared to keep plaintext out of the DOM, but the visible
  helper text ("Stored locally. Cleared from this page after
  save.") and the tiny greyed-out "Currently set: ****XXXX"
  hint were easy to miss, so the credentials **looked**
  wiped even though they were still safely on disk. The API
  handler in `api/save.py` already preserved existing values
  correctly: empty fields were interpreted as "leave the saved
  value untouched", so first-time saves required both fields but
  subsequent saves did not overwrite anything.

  1.1.7 fixes the user-visible symptom by making the saved
  state impossible to miss:

  1. New `.po-saved-badge` style in `webui/main.html` — a
     prominent green pill with a checkmark and the masked
     value (e.g. "✓ Saved as ****AB12 · type a new value to
     replace"), placed directly under each credential input.
     The pill replaces the misleading "Cleared from this page
     after save" copy and the easy-to-miss "Currently set:"
     hint.
  2. `setup-store.js` `refresh()` now populates
     `fields.token` and `fields.user` with the masked display
     after loading the status response, so navigating away and
     back to the Setup page visibly shows the saved values.
  3. `setup-store.js` `save()` now sets the input values to
     the new masked display (e.g. `****AB12`) instead of
     clearing them, so the user sees the save was successful
     and can type to overwrite. Plaintext is never placed in
     the DOM; only the masked form is shown.

### Notes
- UX-only change. No runtime, configuration, route, theme, or
  API behaviour changed. The on-disk `config.json` is never
  modified by this fix; the previous versions already
  preserved the credentials correctly (this only changes what
  the page shows after save or on reload).
- The 49-test suite carries forward unchanged. The
  `test_setup_store.py` / `test_validation.py` paths do not
  cover the JS Alpine store, so no test changes are needed.

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

## [1.1.15] - 2026-09-12

### Critical
- **send_message now normalises the priority field before submission.** Pushover's `/1/messages.json` endpoint rejects any priority value that is not one of `{-2, -1, 0, 1, 2}`; earlier versions POSTed the payload's `priority` value verbatim, so callers passing friendly names (e.g. `"normal"`, `"emergency"`, `"high"`) received a 400 with `errors=['priority is invalid']`. The friendly-name -> integer conversion is now applied inside `send_message()`, so callers can safely pass any of `lowest | low | normal | high | emergency` (case-insensitive) or the integer form. Unknown values raise `ValueError` before any HTTP traffic, surfacing a clear error to the caller.

### Tests
- New `tests/test_client.py` cases cover `lowest/low/normal/high/emergency` -> `-2/-1/0/1/2`, integer passthrough, numeric strings, and unknown-string rejection.

### Notes
- No API contract change for tools; behaviour is strictly more permissive.
- No change to credit/quota usage.
- No change to priority-default-on-omission behaviour (Pushover still applies the system default when the field is absent).

## [1.1.16] - 2026-09-12

### Fixed
- **Mobile layout (iOS/Android browsers):** the Setup page rendered incorrectly below 700px viewport width. Buttons in the Connection Setup panel ("Test Connection"/"Send Test Notification") overflowed horizontally, the action row refused to shrink (inline `flex-shrink:0`), and long labels wrapped over neighbouring panels. Added a `@media (max-width: 700px)` block to both `webui/main.html` and `webui/config.html` that:
  - Stacks connection-card buttons vertically with full width and centered labels.
  - Forces the connection `po-status-card` to a vertical layout so the action row sits below the status detail.
  - Constrains `.po-grid` to a single column on narrow screens.
  - Sets `font-size: 16px` on form fields (iOS no-zoom-on-focus rule).
  - Reduces padding/margins of `.po-page`, `.po-section`, `.po-saved-badge`, and `.po-field-hint` for mobile.
  - Wraps footer action bars ("Save Configuration"/"Reset Pushover Configuration") to a vertical stack.
- **Duplicate "Currently set" rendering on the legacy config page:** `webui/config.html` was rendering the masked credential value twice — once in the masked input (1.1.14 partial-reveal) and once again as a plain `<div class="po-muted">Stored locally...Currently set: ****X</div>` block right below it. Removed the redundant plain-text blocks; the 1.1.14 badge ("Saved as ****X · type a new value to replace") is now the single source of truth.

### Notes
- No API or tool contract changes. Pure CSS / markup cleanup.
- Does not affect dark/light theme switching — uses the same neutral pointer variables as before.
- The host's "Plugin Settings" footer (Reset to default / Save / Cancel) is rendered by the Agent Zero host framework, not by this plugin, and is therefore outside the scope of this fix.
