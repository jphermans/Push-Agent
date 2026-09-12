"""Pushover plugin configuration helpers.

These helpers read and write the plugin configuration using the Agent Zero
framework, including credential masking for UI consumption. They never print
or return the raw ``token`` / ``user`` values to anyone but the Pushover
HTTP client.
"""

from __future__ import annotations

import copy
from typing import Any

from helpers import plugins as core_plugins
from usr.plugins.push_zero.helpers.push_zero_client import mask_identifier


PLUGIN_NAME: str = "push_zero"


def get_raw_config(agent: Any | None = None) -> dict[str, Any]:
    """Return the plugin's runtime configuration as a dict.

    Falls back to ``default_config.yaml`` when nothing has been saved yet.
    """
    cfg = core_plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
    if not isinstance(cfg, dict):
        return {}
    return cfg


def get_masked_config(agent: Any | None = None) -> dict[str, Any]:
    """Return the plugin configuration with credentials safely masked.

    Use this when rendering the Setup page so that even a logged-in user
    never sees the full token or user key.
    """
    cfg = copy.deepcopy(get_raw_config(agent=agent))
    cfg["token"] = mask_identifier(cfg.get("token", "") or "")
    cfg["user"] = mask_identifier(cfg.get("user", "") or "")
    return cfg


def get_credentials(agent: Any | None = None) -> tuple[str, str]:
    """Return ``(token, user)`` for direct use by the HTTP client.

    No masking - this is intended for the client only.
    """
    cfg = get_raw_config(agent=agent)
    token = (cfg.get("token") or "").strip()
    user = (cfg.get("user") or "").strip()
    return token, user


def is_configured(agent: Any | None = None) -> bool:
    """Return ``True`` when both token and user key are stored."""
    token, user = get_credentials(agent=agent)
    return bool(token) and bool(user)


def status_snapshot(agent: Any | None = None) -> dict[str, Any]:
    """Return a setup-status snapshot for the Setup page.

    The Setup page reads ``data.config`` to populate ALL Notification
    Defaults / Emergency / Advanced / Tags / Device / Callback fields.
    The snapshot MUST include the full masked config so the page mirrors
    exactly what is on disk; otherwise non-credential fields revert to
    JS-side hardcoded defaults when the page is re-opened after a save.

    ``get_masked_config`` returns a deep-copy of the saved config with the
    ``token`` / ``user`` values replaced by masked displays, so the API
    response stays credential-safe.
    """
    cfg = get_masked_config(agent=agent)
    token, user = get_credentials(agent=agent)
    return {
        "configured": bool(token) and bool(user),
        "token_set": bool(token),
        "user_set": bool(user),
        "masked_token": mask_identifier(token),
        "masked_user": mask_identifier(user),
        # Full masked config - drives the JS-side hydration of every
        # Notification Defaults / Emergency / Advanced / Tags / Device /
        # Callback field on page open. Without this the JS falls back to
        # its hardcoded defaults and any non-credential edits appear
        # "lost" after a save+reopen cycle.
        "config": cfg,
    }


def ensure_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing keys with safe defaults; never overwrite user input."""
    out = copy.deepcopy(cfg) if isinstance(cfg, dict) else {}
    out.setdefault("token", "")
    out.setdefault("user", "")
    out.setdefault("device", "")
    out.setdefault("defaults", {})
    defaults = out["defaults"] or {}
    defaults.setdefault("title", "Agent Zero")
    defaults.setdefault("priority", "normal")
    defaults.setdefault("sound", "")
    defaults.setdefault("device", "")
    defaults.setdefault("ttl", "")
    defaults.setdefault("url", "")
    defaults.setdefault("url_title", "")
    defaults.setdefault("html", False)
    defaults.setdefault("monospace", False)
    out["defaults"] = defaults

    out.setdefault("emergency", {})
    emergency = out["emergency"] or {}
    emergency.setdefault("retry", 60)
    emergency.setdefault("expire", 3600)
    emergency.setdefault("callback", "")
    out["emergency"] = emergency

    out.setdefault("advanced", {})
    advanced = out["advanced"] or {}
    advanced.setdefault("timeout", 15)
    advanced.setdefault("debug", False)
    out["advanced"] = advanced

    out.setdefault("tags", [])
    out.setdefault("callback", "")
    return out


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    """Persist the supplied config in the global plugin scope.

    The agent scope is intentionally not used - per the project instructions,
    Pushover settings are global per Agent Zero install.
    """
    if not isinstance(config, dict):
        raise ValueError("config must be a dict")
    payload = ensure_defaults(config)
    core_plugins.save_plugin_config(
        PLUGIN_NAME,
        project_name="",
        agent_profile="",
        settings=payload,
    )
    return payload


def reset_config() -> None:
    """Erase all plugin-scope Pushover settings."""
    core_plugins.save_plugin_config(
        PLUGIN_NAME,
        project_name="",
        agent_profile="",
        settings={},
    )


__all__ = [
    "PLUGIN_NAME",
    "get_raw_config",
    "get_masked_config",
    "get_credentials",
    "is_configured",
    "status_snapshot",
    "ensure_defaults",
    "save_config",
    "reset_config",
]
