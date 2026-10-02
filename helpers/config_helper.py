"""Credential and configuration helpers for the Pushover plugin.

Pushover credentials (Application/API Token and User/Group Key) are stored
only in Agent Zero's secret store under stable keys ``PUSHOVER_API_TOKEN``
and ``PUSHOVER_USER_KEY``. Non-secret defaults (timeout, default message
title) live in the plugin's regular configuration via Agent Zero's
``get_plugin_config`` / ``save_plugin_config`` helpers.

The helpers in this file never log or return the raw credential values and
provide masked representations for safe display in the UI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import yaml

# Stable secret-store keys. Keep these stable across versions so that
# configuration entered once persists across reinstalls and updates.
SECRET_API_TOKEN_KEY = "PUSHOVER_API_TOKEN"
SECRET_USER_KEY = "PUSHOVER_USER_KEY"

# Plugin configuration key (under the plugin's own config namespace).
CONFIG_KEY = "pushover"

# Path to the bundled default_config.yaml used as a fallback when no
# plugin configuration has been saved yet.
DEFAULT_CONFIG_PATH = "/a0/usr/plugins/pushover/default_config.yaml"

# Local plugin-owned config file. This is the canonical source of truth
# for non-secret settings (timeout, default title, priority). Using a
# local file avoids triggering Agent Zero's plugin module reload, which
# previously caused HTTP 500 errors on save.
LOCAL_CONFIG_PATH = "/a0/usr/plugins/pushover/pushover_config.json"

# Pushover enforces a 512-character message body limit. The agent tool
# truncates longer messages to keep the API call valid.
PUSHOVER_MAX_MESSAGE_LEN = 512

# Mask length for credential display (chars shown as "•").
MASK_CHAR = "•"
MASK_VISIBLE_TAIL = 4


@dataclass
class ResolvedCredentials:
    """Resolved credentials and full configuration for the Pushover plugin.

    Attributes
    ----------
    api_token:
        Pushover Application/API token. ``None`` when not configured.
    user_key:
        Pushover User/Group key. ``None`` when not configured.
    request_timeout:
        Seconds to wait for the Pushover API to respond.
    priority:
        Pushover priority. v0.1.0 always sends ``0`` (normal priority).
    default_title:
        Default notification title; defaults to ``"Agent Zero"``.
    """

    api_token: Optional[str]
    user_key: Optional[str]
    request_timeout: int
    priority: int
    default_title: str

    @property
    def is_configured(self) -> bool:
        """Return True if both required credentials are present and non-empty."""
        return bool(self.api_token and self.user_key)


def mask_credential(value: Optional[str]) -> str:
    """Return a masked display representation of a credential.

    Returns an empty string for empty/None input and a placeholder mask of
    the original length with the trailing ``MASK_VISIBLE_TAIL`` characters
    visible when possible. The raw value is never returned.
    """
    if not value:
        return ""
    if len(value) <= MASK_VISIBLE_TAIL:
        return MASK_CHAR * max(len(value), 4)
    masked_len = max(len(value), 8)
    head = MASK_CHAR * (masked_len - MASK_VISIBLE_TAIL)
    tail = value[-MASK_VISIBLE_TAIL:]
    return head + tail


def _load_default_config() -> dict:
    """Load the bundled default configuration YAML."""
    try:
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data


def load_default_config() -> dict:
    """Public wrapper for loading the bundled default configuration."""
    return _load_default_config()


def load_local_config() -> dict:
    """Load the plugin-owned local configuration file.

    This file is the canonical source of truth for non-secret settings
    (timeout, default title, priority). Reading from a local file avoids
    triggering Agent Zero's plugin module reload that the framework
    ``get_plugin_config`` path can produce.
    """
    try:
        with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_local_config(settings: dict) -> dict:
    """Persist non-secret settings to the plugin-owned local config file.

    The write is atomic: settings are written to a sibling ``.tmp`` file
    and then ``os.replace`` is used so partial writes never overwrite the
    previous configuration.
    """
    safe: dict = {}
    if isinstance(settings, dict):
        for key, value in settings.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
    tmp_path = LOCAL_CONFIG_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(safe, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, LOCAL_CONFIG_PATH)
    except OSError:
        # As a last resort, try a non-atomic write.
        try:
            with open(LOCAL_CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(safe, fh, indent=2, sort_keys=True)
                fh.write("\n")
        except OSError:
            pass
    return safe


def resolve_credentials(
    saved_config: Optional[dict] = None,
    secrets: Optional[dict] = None,
) -> ResolvedCredentials:
    """Combine saved plugin configuration with secret-store credentials.

    Parameters
    ----------
    saved_config:
        The dictionary returned by ``get_plugin_config`` for the plugin.
        ``None`` falls back to the default configuration.
    secrets:
        The dictionary returned by ``get_secrets_manager().load_secrets()``.
        ``None`` means no secrets are configured.
    """
    base = _load_default_config()
    if isinstance(saved_config, dict):
        for key, value in saved_config.items():
            if isinstance(value, (str, int, float, bool)):
                base[key] = value

    secrets = secrets or {}
    api_token = secrets.get(SECRET_API_TOKEN_KEY) or None
    user_key = secrets.get(SECRET_USER_KEY) or None

    request_timeout = int(base.get("request_timeout", 10) or 10)
    priority = int(base.get("priority", 0) or 0)
    default_title = str(base.get("default_title", "Agent Zero") or "Agent Zero")

    return ResolvedCredentials(
        api_token=api_token,
        user_key=user_key,
        request_timeout=request_timeout,
        priority=priority,
        default_title=default_title,
    )


def status_snapshot(
    saved_config: Optional[dict] = None,
    secrets: Optional[dict] = None,
) -> dict:
    """Return a UI-safe status snapshot.

    The snapshot never contains raw secret values. Use ``mask_credential``
    for any display rendering.
    """
    resolved = resolve_credentials(saved_config=saved_config, secrets=secrets)
    return {
        "configured": resolved.is_configured,
        "request_timeout": resolved.request_timeout,
        "priority": resolved.priority,
        "default_title": resolved.default_title,
        "has_token": bool(resolved.api_token),
        "has_user_key": bool(resolved.user_key),
        "masked_token": mask_credential(resolved.api_token) if resolved.api_token else "",
        "masked_user_key": mask_credential(resolved.user_key) if resolved.user_key else "",
    }