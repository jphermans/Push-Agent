"""Reset configuration API handler.

The Setup page "Reset Pushover Configuration" action should require explicit
confirmation; this endpoint is intentionally destructive and should only be
called as a result of that confirmation dialog.
"""

from __future__ import annotations

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.pushover.helpers.config_helper import reset_config


class Reset(ApiHandler):
    """Erase all stored Pushover plugin configuration."""

    async def process(self, input: dict, request: Request) -> dict:
        confirm = input.get("confirm")
        if confirm not in (True, "true", "yes", "1"):
            return {
                "success": False,
                "error": (
                    "Confirmation is required to reset the Pushover "
                    "configuration."
                ),
            }
        reset_config()
        return {"success": True, "configured": False}
