"""Sounds API handler (``POST /api/plugins/push_zero/sounds``).

Returns the list of available Pushover sounds so the Setup page can
populate the "Default Sound" dropdown. The default "User default" entry
is always prepended so the user can opt out of sending a sound override.
"""

from __future__ import annotations

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.push_zero.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    is_configured,
)
from usr.plugins.push_zero.helpers.push_zero_client import PushoverClient


class Sounds(ApiHandler):
    """Return available Pushover sounds with safe fallback."""

    async def process(self, input: dict, request: Request) -> dict:
        if not is_configured():
            return {
                "success": False,
                "sounds": [{"slug": "", "label": "User default"}],
                "configured": False,
                "error": "Configure Pushover first.",
            }

        token, user = get_credentials()
        cfg = get_raw_config() or {}
        advanced = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}
        try:
            timeout = int(advanced.get("timeout", 15)) if isinstance(advanced, dict) else 15
        except (TypeError, ValueError):
            timeout = 15

        client = PushoverClient(token=token, user=user, timeout=timeout)
        result = client.list_sounds()
        if not result.success:
            return {
                "success": False,
                "sounds": [{"slug": "", "label": "User default"}],
                "configured": True,
                "error": result.error or "; ".join(result.errors),
            }

        sounds_raw = (result.data or {}).get("sounds") or {}
        sounds: list[dict[str, str]] = [{"slug": "", "label": "User default"}]
        if isinstance(sounds_raw, dict):
            for slug in sorted(sounds_raw.keys()):
                label = sounds_raw.get(slug) or slug
                sounds.append({"slug": str(slug), "label": str(label)})
        return {
            "success": True,
            "sounds": sounds,
            "configured": True,
        }
