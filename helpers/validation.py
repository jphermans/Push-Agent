"""Centralised validation helpers for the Pushover plugin.

These helpers raise ``ValueError`` with human-friendly messages instead of
letting Pushover reject the request. They are intentionally idempotent so
they can be called from both the agent tool and the Setup page handlers.
"""

from __future__ import annotations

from typing import Any

from usr.plugins.push_zero.helpers.push_zero_client import (
    normalize_priority,
    priority_label,
    stringify_tags,
    validate_device,
    validate_emergency_expire,
    validate_emergency_retry,
    validate_message,
    validate_sound,
    validate_tags,
    validate_title,
    validate_ttl,
    validate_url,
    validate_url_title,
)


# Default emergency notification behaviour, applied when the user does not
# override them. Pushover itself requires both values when priority=2.
DEFAULT_EMERGENCY_RETRY_SECONDS: int = 60
DEFAULT_EMERGENCY_EXPIRE_SECONDS: int = 3600


def build_message_payload(
    *,
    message: Any,
    title: Any = "",
    priority: Any = "",
    sound: Any = "",
    device: Any = "",
    url: Any = "",
    url_title: Any = "",
    ttl: Any = "",
    html: Any = False,
    monospace: Any = False,
    retry: Any = "",
    expire: Any = "",
    callback: Any = "",
    tags: Any = "",
    timestamp: Any = "",
) -> dict[str, Any]:
    """Build a payload dict ready for POST to ``/1/messages.json``.

    The returned dict only contains keys Pushover accepts. Empty values are
    stripped before the request is sent so the API does not reject optional
    fields.

    ``html`` and ``monospace`` cannot both be true. Priority="emergency"
    (or numeric 2) requires ``retry`` and ``expire``; they default to
    60/3600 if absent so the agent does not have to repeat the well-known
    defaults.
    """
    text = validate_message(message)
    title_text = validate_title(title)
    device_text = validate_device(device)
    sound_text = validate_sound(sound)
    url_text = validate_url(url, field_name="url")
    url_title_text = validate_url_title(url_title)
    ttl_value = validate_ttl(ttl)
    # Validate tag length up front so users see friendly errors.
    validate_tags(tags)

    html_flag = _coerce_bool(html, field="html")
    mono_flag = _coerce_bool(monospace, field="monospace")

    if html_flag and mono_flag:
        raise ValueError("HTML and monospace formatting cannot both be enabled.")

    # Resolve priority: friendly or numeric.
    priority_value: int | None = None
    if priority not in ("", None):
        priority_value = normalize_priority(priority)

    payload: dict[str, Any] = {
        "message": text,
    }
    if title_text:
        payload["title"] = title_text
    if device_text:
        payload["device"] = device_text
    if sound_text:
        payload["sound"] = sound_text
    if priority_value is not None:
        payload["priority"] = priority_value
        if priority_value == 2:
            # Emergency notifications require retry/expire. Use defaults
            # if the caller did not provide them, otherwise run the
            # validators so an invalid value is rejected with a clear
            # error instead of silently falling through.
            if retry in ("", None):
                retry_value = DEFAULT_EMERGENCY_RETRY_SECONDS
            else:
                retry_value = validate_emergency_retry(retry)
            if expire in ("", None):
                expire_value = DEFAULT_EMERGENCY_EXPIRE_SECONDS
            else:
                expire_value = validate_emergency_expire(expire)
            payload["retry"] = retry_value
            payload["expire"] = expire_value
    if url_text:
        payload["url"] = url_text
    if url_title_text:
        payload["url_title"] = url_title_text
    if ttl_value:
        payload["ttl"] = ttl_value
    if html_flag:
        payload["html"] = 1
    if mono_flag:
        payload["monospace"] = 1
    if callback:
        payload["callback"] = str(callback).strip()
    if tags not in ("", None):
        payload["tags"] = stringify_tags(tags)
    if timestamp not in ("", None):
        try:
            payload["timestamp"] = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise ValueError("timestamp must be a unix epoch integer") from exc

    return payload


def _coerce_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, int):
        return value != 0
    if value in (None, ""):
        return False
    raise ValueError(f"{field} must be a boolean value")


def _is_emergency(value: Any) -> bool:
    if value in ("", None):
        return False
    try:
        return normalize_priority(value) == 2
    except (ValueError, TypeError):
        return False


def _resolve_emergency_value(value: Any, fallback: int) -> int:
    """Return ``value`` if it is a usable integer, else ``fallback``."""
    if value in ("", None):
        return fallback
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        if value <= 0:
            return fallback
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            parsed = int(text)
        except ValueError:
            return fallback
        if parsed <= 0:
            return fallback
        return parsed
    return fallback


def coalesce_defaults(
    agent_args: dict[str, Any],
    plugin_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply plugin defaults onto the tool-call arguments.

    Agent-provided values win over plugin defaults. Booleans are kept
    intentionally separate from plain defaults so a user explicit
    ``False`` override is not swallowed by a missing config value.
    """
    args = dict(agent_args or {})
    cfg = plugin_config or {}
    defaults = cfg.get("defaults", {}) if isinstance(cfg, dict) else {}
    emergency = cfg.get("emergency", {}) if isinstance(cfg, dict) else {}
    advanced = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}

    def pick(key: str, plugin_key: str | None = None):
        if key in args and args[key] not in (None, ""):
            return args[key]
        plugin_value = (defaults.get(plugin_key or key) if isinstance(defaults, dict) else None)
        if plugin_value not in (None, ""):
            return plugin_value
        # Fallback to top-level token / user keys for ergonomic defaults.
        if plugin_key is None and key in cfg and cfg[key] not in (None, ""):
            return cfg[key]
        return None

    def pick_bool(key: str, plugin_key: str | None = None) -> bool:
        if key in args:
            return _coerce_bool(args[key], field=key)
        plugin_value = (defaults.get(plugin_key or key) if isinstance(defaults, dict) else None)
        if plugin_value in (None, "") and isinstance(cfg, dict):
            if plugin_key is None and key in cfg:
                plugin_value = cfg[key]
        return _coerce_bool(plugin_value, field=key)

    merged: dict[str, Any] = {}
    for key in ("message", "title", "priority", "sound", "device", "url", "url_title", "ttl", "callback", "tags"):
        v = pick(key)
        if v is not None:
            merged[key] = v

    merged["html"] = pick_bool("html")
    merged["monospace"] = pick_bool("monospace")

    # Plugin-wide timeout helper
    merged["_timeout"] = advanced.get("timeout", 15) if isinstance(advanced, dict) else 15
    merged["_debug"] = _coerce_bool(advanced.get("debug", False), field="debug") if isinstance(advanced, dict) else False

    # Emergency retry/expire resolution: explicit args first, then config.
    # Use the *resolved* priority (after defaults applied), so a default
    # priority of "emergency" still populates retry/expire from the
    # emergency block.
    final_priority = args.get("priority", defaults.get("priority"))
    if _is_emergency(final_priority):
        retry_val = args.get("retry", "")
        if retry_val in (None, ""):
            retry_val = emergency.get("retry") if isinstance(emergency, dict) else None
        if retry_val in (None, "") or _resolve_emergency_value(retry_val, 0) <= 0:
            retry_val = DEFAULT_EMERGENCY_RETRY_SECONDS
        merged["retry"] = retry_val

        expire_val = args.get("expire", "")
        if expire_val in (None, ""):
            expire_val = emergency.get("expire") if isinstance(emergency, dict) else None
        if expire_val in (None, "") or _resolve_emergency_value(expire_val, 0) <= 0:
            expire_val = DEFAULT_EMERGENCY_EXPIRE_SECONDS
        merged["expire"] = expire_val

    return merged


__all__ = [
    "build_message_payload",
    "coalesce_defaults",
    "DEFAULT_EMERGENCY_RETRY_SECONDS",
    "DEFAULT_EMERGENCY_EXPIRE_SECONDS",
    "priority_label",
    "normalize_priority",
    "stringify_tags",
    "validate_tags",
]
