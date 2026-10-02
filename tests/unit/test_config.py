"""Tests for the credential/configuration helpers."""

from __future__ import annotations

from usr.plugins.pushover.helpers.config_helper import (
    DEFAULT_CONFIG_PATH,
    PLUGIN_VERSION,
    PUSHOVER_MAX_MESSAGE_LEN,
    SECRET_API_TOKEN_KEY,
    SECRET_USER_KEY,
    mask_credential,
    resolve_credentials,
    status_snapshot,
)


def test_default_constants_have_expected_values():
    assert SECRET_API_TOKEN_KEY == "PUSHOVER_API_TOKEN"
    assert SECRET_USER_KEY == "PUSHOVER_USER_KEY"
    assert PUSHOVER_MAX_MESSAGE_LEN == 512
    assert DEFAULT_CONFIG_PATH == "/a0/usr/plugins/pushover/default_config.yaml"


def test_mask_credential_returns_empty_for_empty_input():
    assert mask_credential(None) == ""
    assert mask_credential("") == ""


def test_mask_credential_keeps_tail_for_long_values():
    value = "ABCDEFGHIJKLMNOP"
    masked = mask_credential(value)
    assert masked.endswith("MNOP")
    assert "ABCDEFGHIJKL" not in masked
    assert "•" in masked


def test_mask_credential_handles_short_values():
    masked = mask_credential("ab")
    assert "ab" not in masked
    assert "•" in masked


def test_resolve_credentials_missing_secrets():
    resolved = resolve_credentials(saved_config=None, secrets=None)
    assert resolved.api_token is None
    assert resolved.user_key is None
    assert resolved.is_configured is False
    assert resolved.request_timeout == 10
    assert resolved.priority == 0
    assert resolved.default_title == "Agent Zero"


def test_resolve_credentials_with_secrets():
    resolved = resolve_credentials(
        saved_config={"request_timeout": 7, "default_title": "Custom"},
        secrets={SECRET_API_TOKEN_KEY: "t" * 30, SECRET_USER_KEY: "u" * 30},
    )
    assert resolved.api_token == "t" * 30
    assert resolved.user_key == "u" * 30
    assert resolved.is_configured is True
    assert resolved.request_timeout == 7
    assert resolved.default_title == "Custom"
    assert resolved.priority == 0


def test_resolve_credentials_partially_configured():
    resolved = resolve_credentials(
        saved_config={},
        secrets={SECRET_API_TOKEN_KEY: "only-token"},
    )
    assert resolved.is_configured is False


def test_status_snapshot_never_includes_raw_secrets():
    snapshot = status_snapshot(
        saved_config={"default_title": "X"},
        secrets={SECRET_API_TOKEN_KEY: "abcdEFGH", SECRET_USER_KEY: "wxyzABCD"},
    )
    assert snapshot["configured"] is True
    assert snapshot["has_token"] is True
    assert snapshot["has_user_key"] is True
    assert snapshot["default_title"] == "X"
    assert "abcdEFGH" not in snapshot["masked_token"]
    assert "wxyzABCD" not in snapshot["masked_user_key"]
    assert "raw" not in snapshot
    assert "api_token" not in snapshot
    assert "user_key" not in snapshot


def test_status_snapshot_exposes_plugin_version():
    snapshot = status_snapshot()
    assert snapshot["version"] == PLUGIN_VERSION
    # Version is a non-empty semver-ish string the UI can show directly.
    assert snapshot["version"]
    assert "." in snapshot["version"]
