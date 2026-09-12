"""Send test notification API handler (``POST /api/plugins/pushover/test_notify``).

Sends a default "Test Notification" using the configured Pushover
defaults. Failures return a structured response with a human-readable
reason and never include credentials.
"""

from __future__ import annotations

from typing import Any

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.pushover.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    is_configured,
)
from usr.plugins.pushover.helpers.pushover_client import PushoverClient
from usr.plugins.pushover.helpers.validation import build_message_payload


class TestNotify(ApiHandler):
    """Send a default test Pushover notification."""

    async def process(self, input: dict, request: Request) -> dict:
        if not is_configured():
            return {
                "success": False,
                "error": (
                    "Pushover is not configured yet. Add the Application "
                    "Token and User Key first."
                ),
            }

        cfg = get_raw_config() or {}
        defaults = (cfg.get("defaults") or {}) if isinstance(cfg, dict) else {}
        advanced = (cfg.get("advanced") or {}) if isinstance(cfg, dict) else {}

        message = (input.get("message") or "Pushover integration is working.").strip()
        title = (defaults.get("title") or "Agent Zero") if isinstance(defaults, dict) else "Agent Zero"
        priority = (defaults.get("priority") or "normal") if isinstance(defaults, dict) else "normal"
        sound = (defaults.get("sound") or "") if isinstance(defaults, dict) else ""
        device = (defaults.get("device") or cfg.get("device") or "") if isinstance(cfg, dict) else ""
        ttl = defaults.get("ttl") if isinstance(defaults, dict) else ""

        try:
            payload = build_message_payload(
                message=message,
                title=title,
                priority=priority,
                sound=sound,
                device=device,
                ttl=ttl,
                html=bool(defaults.get("html", False)),
                monospace=bool(defaults.get("monospace", False)),
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        token, user = get_credentials()
        try:
            timeout = int(advanced.get("timeout", 15)) if isinstance(advanced, dict) else 15
        except (TypeError, ValueError):
            timeout = 15
        debug = bool(advanced.get("debug", False)) if isinstance(advanced, dict) else False

        client = PushoverClient(token=token, user=user, timeout=timeout, debug=debug)
        result = client.send_message(payload)
        if result.success:
            return {
                "success": True,
                "message": "Test notification sent successfully.",
                "request": result.request_id,
            }
        return {
            "success": False,
            "error": result.error or "; ".join(result.errors) or "Could not send the test notification.",
            "request": result.request_id,
        }
