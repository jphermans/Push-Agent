"""Status API handler (``POST /api/plugins/pushover/status``).

Returns the current setup status snapshot: credentials presence (masked),
defaults, emergency settings, and a few advanced settings. Useful for
the Setup page initial render.
"""

from __future__ import annotations

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.pushover.helpers.config_helper import (
    get_masked_config,
    status_snapshot,
)


class Status(ApiHandler):
    """Return Pushover setup status, defaults, and emergency settings."""

    async def process(self, input: dict, request: Request) -> dict:
        snapshot = status_snapshot()
        config = get_masked_config()
        return {
            "success": True,
            "configured": snapshot["configured"],
            "masked_token": snapshot["masked_token"],
            "masked_user": snapshot["masked_user"],
            "config": config,
        }
