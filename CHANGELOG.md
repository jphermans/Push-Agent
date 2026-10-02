# Changelog

All notable changes to the Pushover plugin are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

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
