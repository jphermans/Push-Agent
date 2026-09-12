"""Pushover plugin configuration helpers.

These helpers read and write the plugin configuration using BOTH:

  1. An explicit plugin-local JSON file at
     ``<plugin_dir>/push_zero_config.json`` (PRIMARY; the source of truth
     the user can verify on disk and inspect with any tool).
  2. The Agent Zero framework's ``core_plugins.save_plugin_config`` storage
     (SECONDARY; kept in sync so the framework's plugin-management UI also
     reflects the same values).

The local JSON file is read first; the framework storage acts as a
fallback when the local file is missing or empty. The local file is
always written on save so the user sees their changes durably
persisted on disk and can verify by reading the file.

Credentials are masked in any value returned to the UI; the HTTP client
is the only consumer of the raw ``token`` / ``user`` values.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

from helpers import plugins as core_plugins
from usr.plugins.push_zero.helpers.push_zero_client import mask_identifier


PLUGIN_NAME: str = "push_zero"

# Plugin-local JSON persistence. This is the PRIMARY store - the user
# can verify the file on disk and read it with any tool. The framework
# storage is a secondary mirror.
_LOCAL_CONFIG_NAME = "push_zero_config.json"
_LOCAL_CONFIG_PATH: Path = Path(__file__).resolve().parent.parent / _LOCAL_CONFIG_NAME

logger = logging.getLogger(__name__)


def _read_local_config() -> dict[str, Any]:
    """Read the plugin-local JSON config. Returns empty dict on any failure."""
    try:
        if not _LOCAL_CONFIG_PATH.exists():
            return {}
        text = _LOCAL_CONFIG_PATH.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("push_zero: could not read local config at %s: %s", _LOCAL_CONFIG_PATH, exc)
        return {}


def _write_local_config(cfg: dict[str, Any]) -> None:
    """Write the plugin-local JSON config atomically. Never raises."""
    try:
        _LOCAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = _LOCAL_CONFIG_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(_LOCAL_CONFIG_PATH)
        try:
            _LOCAL_CONFIG_PATH.chmod(0o644)
        except OSError:
            pass
    except OSError as exc:
        logger.warning("push_zero: could not write local config at %s: %s", _LOCAL_CONFIG_PATH, exc)


def get_raw_config(agent: Any | None = None) -> dict[str, Any]:
    """Return the plugin's runtime configuration as a dict.

    The local JSON file at ``push_zero_config.json`` is the PRIMARY source
    of truth. The framework's plugin storage is read as a SECONDARY
    fallback when the local file is missing or empty. This way the user
    always sees their last-saved values, and a missing local file just
    falls back to whatever the framework already has.

    Falls back to ``default_config.yaml`` when neither source has anything.
    """
    local = _read_local_config()
    if local:
        return ensure_defaults(local)
    framework = core_plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
    if not isinstance(framework, dict):
        return {}
    cfg = ensure_defaults(framework)
    # Mirror framework storage into the local file so subsequent reads are fast.
    _write_local_config(cfg)
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

    Writes go to BOTH the plugin-local JSON file (PRIMARY) and the framework
    storage (SECONDARY mirror). If the framework write fails for any reason,
    the local JSON file still has the user's values, so a page reload will
    still hydrate them correctly. If the local write fails, the framework
    write still goes through so the framework-level plugin UI reflects the
    same state.
    """
    if not isinstance(config, dict):
        raise ValueError("config must be a dict")
    payload = ensure_defaults(config)
    # PRIMARY: write to the local JSON file first.
    _write_local_config(payload)
    # SECONDARY: mirror into framework storage so the framework plugin UI
    # also reflects the saved values.
    try:
        core_plugins.save_plugin_config(
            PLUGIN_NAME,
            project_name="",
            agent_profile="",
            settings=payload,
        )
    except Exception as exc:
        logger.warning("push_zero: framework save_plugin_config failed: %s", exc)
    return payload


def reset_config() -> None:
    """Erase all plugin-scope Pushover settings."""
    # Remove the local JSON file so the next read starts from defaults.
    try:
        if _LOCAL_CONFIG_PATH.exists():
            _LOCAL_CONFIG_PATH.unlink()
    except OSError as exc:
        logger.warning("push_zero: could not delete local config at %s: %s", _LOCAL_CONFIG_PATH, exc)
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
