"""API usage handler (``POST /api/plugins/pushover/limits``).

Probes Pushover's ``/1/apps/limits.json`` endpoint to show monthly
message counts and quota. The Pushover docs do not document this as a
stable public API, so failures must NEVER block notification sending -
they are always returned as a non-success payload.
"""

from __future__ import annotations

import time
from typing import Any

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.pushover.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    is_configured,
)
from usr.plugins.pushover.helpers.pushover_client import PushoverClient


class Limits(ApiHandler):
    """Return Pushover application usage / quota information."""

    async def process(self, input: dict, request: Request) -> dict:
        if not is_configured():
            return {
                "success": False,
                "configured": False,
                "error": "Pushover is not configured yet.",
            }

        token, user = get_credentials()
        cfg = get_raw_config() or {}
        advanced = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}
        try:
            timeout = int(advanced.get("timeout", 15)) if isinstance(advanced, dict) else 15
        except (TypeError, ValueError):
            timeout = 15

        client = PushoverClient(token=token, user=user, timeout=timeout)
        result = client.get_app_limits()

        payload: dict[str, Any] = {
            "success": result.success,
            "configured": True,
            "fetched_at": int(time.time()),
        }
        if not result.success:
            payload["error"] = result.error or "; ".join(result.errors) or "Could not load Pushover limits."
            return payload

        info = result.data or {}
        limit = info.get("limit")
        remaining = info.get("remaining")
        used = info.get("used")
        reset = info.get("reset")
        payload.update(
            {
                "limit": int(limit) if isinstance(limit, (int, float)) else None,
                "remaining": int(remaining) if isinstance(remaining, (int, float)) else None,
                "used": int(used) if isinstance(used, (int, float)) else None,
                "reset": reset,
                "raw": info,
            }
        )
        return payload
