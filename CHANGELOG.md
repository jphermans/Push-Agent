# Changelog

All notable changes to the Pushover plugin are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [0.0.5] - HTTP 500 on save fully fixed

### Fixed

- **HTTP 500 on save for multi-file secrets setups.** The
  `save_secrets` call was raising an unhandled `RuntimeError` on
  Agent Zero deployments where the secret manager tracks more than
  one secrets file (e.g. global `/a0/usr/.env` plus the project's
  `/a0/usr/projects/<name>/.a0proj/secrets.env`). The secret manager
  refuses to write in that mode so it doesn't have to pick which file
  to mutate. The Pushover save handler now catches that
  `RuntimeError` and falls back to writing the two plugin keys
  (`PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`) directly to the
  project's `.a0proj/secrets.env` file, preserving any other keys
  already in the file. The save endpoint now returns
  `{"success": true, ...}` instead of HTTP 500 on these deployments.

- **Defensive try/except** around every side effect in the save
  handler so a single failure (secrets store, file I/O, snapshot
  building) can never crash the request into an unhandled 500.

## [0.0.4] - Version visible in Setup

### Added

- Plugin version is now displayed in the Setup page header so the user
  can confirm at a glance which release is loaded.
- `helpers.config_helper.PLUGIN_VERSION` constant and `version` key in
  `status_snapshot()` so the value is sourced from a single place.

## [0.0.3] - Icon refresh

### Changed

- Replaced the placeholder notification icon with a more polished
  design that combines an Agent Zero tech aesthetic (cyan/blue
  gradient background, subtle corner network nodes) with a clear
  notification motif (white bell with red status dot). The new
  thumbnail matches the visual language of other Agent Zero plugin
  cards in the Settings page.

## [0.0.2] - Save fix

### Fixed

- **HTTP 500 on save and test notification.** The `save.py` handler
  previously called `helpers.plugins.save_plugin_config` with the
  framework's `project_name` and `agent_profile` attributes. When both
  are empty (the normal state for the Setup page), the framework's
  plugin-config write path triggers a frontend reload and a plugin
  module refresh, which surfaced as HTTP 500 in the browser and which
  also caused the subsequent `Send Test Notification` call to fail
  because the reload invalidated the in-memory handler binding.

- The fix stores non-secret settings (request timeout, default title,
  priority) in a plugin-owned local JSON file at
  `pushover_config.json` instead of going through
  `save_plugin_config`. The framework's `get_plugin_config` is still
  honoured as a fallback for legacy callers, but the local file is the
  canonical source of truth.

- Atomic write of the local config file: a `.tmp` sibling is written
  first and then `os.replace`'d over the live file so partial writes
  never corrupt the saved configuration.

- `parse_env_content` was previously fed back into `save_secrets`,
  which would have written a Python `dict` to the secrets store. The
  save handler now serialises the merged secrets to the `KEY="value"`
  format before calling `save_secrets`, matching the contract of the
  Agent Zero secret store.

## [0.0.1] - Initial release

### Added

- `pushover_notify` agent tool. Accepts a required `message` parameter
  and an optional `title` parameter (default `"Agent Zero"`). Reads
  Pushover credentials from Agent Zero's secret store; never exposes
  them as tool parameters or in tool results.
- Setup UI under Settings → External → Pushover with Status
  indicator, Application/API Token field, User/Group Key field,
  request timeout, default title, **Save Configuration**,
  **Test Connection**, and **Send Test Notification** buttons.
- API handlers:
  - `POST /api/plugins/pushover/save`
  - `POST /api/plugins/pushover/status`
  - `POST /api/plugins/pushover/test_connection`
  - `POST /api/plugins/pushover/test_notification`
- HTTPS-only Pushover client using `urllib` from the Python standard
  library, with TLS verification enabled.
- Lifecycle hooks (`install`, `pre_update`, `uninstall`) in `hooks.py`.
- 24 unit tests covering credential masking, configuration loading,
  Pushover HTTP success/failure/timeout/TLS error paths, and tool
  input validation. All tests mock the Pushover endpoint so no real
  notification is sent from automated tests.
- README, LICENSE and this CHANGELOG.

### Security

- Credentials are written only to Agent Zero's secret store under
  the keys `PUSHOVER_API_TOKEN` and `PUSHOVER_USER_KEY`. They are
  never written to `plugin.yaml`, to disk in plain text, or to logs.
- The plugin UI displays masked credential representations
  (`••••••…xxxx`) once the credentials have been saved.
- Pushover API error messages returned to the agent are sanitised.
  They never include the token, user key, or internal exception
  details.

### Intentionally not implemented in 0.0.1

- Automatic notifications on task completion, failure, startup, or
  scheduled triggers.
- Emergency priority, receipt tracking, receipt polling,
  cancellation, cancel-by-tag, device selection, sounds, TTL,
  callbacks, tags, attachments, HTML formatting, monospace
  formatting, and supplementary URLs.
- A dedicated `execute.py` manual action. The plugin is configured
  entirely through its lifecycle hooks and Setup page.
