"""Save-config API handler (``POST /api/plugins/push_zero/save``).

Persists the Setup page configuration in the global Pushover plugin scope.
The handler refuses to accept empty ``token`` or ``user`` fields once the
plugin has a saved configuration - empty fields are interpreted as "leave
the existing value untouched" so a user does not wipe their credentials
unintentionally. First-time saves require both fields.
"""

from __future__ import annotations

import re
from typing import Any

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.push_zero.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    save_config,
)


# Defensive: any input that consists mostly or entirely of asterisks is
# treated as a masked display, not as a real credential, and is ignored
# so the user cannot silently overwrite a real token with its own masked
# form. This belt-and-braces guard complements the frontend change that
# stops putting the masked display back into the input fields.
_MASKED_INPUT_RE = re.compile(r"^\*+[^*]*$")


def _looks_like_masked_value(value: str) -> bool:
    if not value:
        return False
    return bool(_MASKED_INPUT_RE.match(value))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Save(ApiHandler):
    """Persist Pushover configuration submitted by the Setup page."""

    async def process(self, input: dict, request: Request) -> dict:
        existing = get_raw_config() or {}
        cfg: dict[str, Any] = dict(existing)

        # First-time setup needs both fields; otherwise leave alone.
        # Defensive: treat asterisk-heavy inputs as masked-display artifacts
        # (a frontend regression could put the masked form back into the
        # input on Save). We silently drop them here.
        token_input = (input.get("token") or "").strip()
        user_input = (input.get("user") or "").strip()
        if _looks_like_masked_value(token_input):
            token_input = ""
        if _looks_like_masked_value(user_input):
            user_input = ""
        if token_input:
            cfg["token"] = token_input
        elif not cfg.get("token"):
            return {
                "success": False,
                "error": "Application/API Token is required.",
            }
        if user_input:
            cfg["user"] = user_input
        elif not cfg.get("user"):
            return {
                "success": False,
                "error": "User / Group Key is required.",
            }

        cfg["device"] = (input.get("device") or "").strip()

        # Notification defaults
        cfg.setdefault("defaults", {})
        defaults = cfg["defaults"] or {}
        defaults["title"] = (input.get("title") or "Agent Zero").strip() or "Agent Zero"
        defaults["priority"] = (input.get("priority") or "normal").strip().lower() or "normal"
        defaults["sound"] = (input.get("sound") or "").strip()
        defaults["device"] = (input.get("default_device") or "").strip()
        ttl_raw = input.get("ttl")
        defaults["ttl"] = str(ttl_raw) if str(ttl_raw or "").strip() else ""
        defaults["url"] = (input.get("url") or "").strip()
        defaults["url_title"] = (input.get("url_title") or "").strip()
        defaults["html"] = _coerce_bool(input.get("html"))
        defaults["monospace"] = _coerce_bool(input.get("monospace"))
        if defaults["html"] and defaults["monospace"]:
            # Enforce Pushover's exclusive rule - prefer HTML as the official mode.
            defaults["monospace"] = False
        cfg["defaults"] = defaults

        # Emergency settings
        cfg.setdefault("emergency", {})
        emergency = cfg["emergency"] or {}
        retry = _coerce_int(input.get("retry"), 60)
        expire = _coerce_int(input.get("expire"), 3600)
        if retry < 30:
            retry = 30
        if expire not in (0,) and expire < 30:
            expire = 30
        if expire > 10800:
            expire = 10800
        emergency["retry"] = retry
        emergency["expire"] = expire
        emergency["callback"] = (input.get("callback") or "").strip()
        cfg["emergency"] = emergency

        # Advanced settings
        cfg.setdefault("advanced", {})
        advanced = cfg["advanced"] or {}
        timeout = _coerce_int(input.get("timeout"), 15)
        if timeout < 1:
            timeout = 1
        if timeout > 60:
            timeout = 60
        advanced["timeout"] = timeout
        advanced["debug"] = _coerce_bool(input.get("debug"))
        cfg["advanced"] = advanced

        # Default tags list (comma-separated)
        tags_value = (input.get("tags") or "").strip()
        cfg["tags"] = [t.strip() for t in tags_value.split(",") if t.strip()] if tags_value else []

        # Top-level fallback callback
        cfg["callback"] = (input.get("default_callback") or "").strip()

        # Save
        try:
            saved = save_config(cfg)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {
            "success": True,
            "masked_token": "*" * max(0, len(saved.get("token", "")) - 4) + saved.get("token", "")[-4:],
            "masked_user": "*" * max(0, len(saved.get("user", "")) - 4) + saved.get("user", "")[-4:],
            "token_set": bool(saved.get("token")),
            "user_set": bool(saved.get("user")),
            "configured": bool(saved.get("token")) and bool(saved.get("user")),
        }
