"""Connection test API handler (``POST /api/plugins/push_zero/test``).

Probes the configured Pushover credentials by calling the lightweight
``/1/apps/limits.json`` endpoint, then optionally sends a dry-run
notification to confirm the user key is valid.

This handler never returns the configured token or user key - only the
``success`` flag and a list of readable test result entries.
"""

from __future__ import annotations

import time
from typing import Any

from flask import Request

from helpers.api import ApiHandler
from helpers.errors import format_error

from usr.plugins.push_zero.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    is_configured,
)
from usr.plugins.push_zero.helpers.push_zero_client import PushoverClient


class Test(ApiHandler):
    """Validate the configured Pushover credentials."""

    async def process(self, input: dict, request: Request) -> dict:
        results: list[dict[str, Any]] = []

        if not is_configured():
            results.append(
                {
                    "test": "Configuration",
                    "ok": False,
                    "message": (
                        "No Pushover credentials are stored yet. Add the "
                        "Application Token and User Key on the Setup page."
                    ),
                }
            )
            return {"success": False, "results": results, "configured": False}

        token, user = get_credentials()
        cfg = get_raw_config() or {}
        advanced = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}
        try:
            timeout = int(advanced.get("timeout", 15)) if isinstance(advanced, dict) else 15
        except (TypeError, ValueError):
            timeout = 15
        debug = bool(advanced.get("debug", False)) if isinstance(advanced, dict) else False

        client = PushoverClient(token=token, user=user, timeout=timeout, debug=debug)

        # 1. Validate the application token by hitting the cheap limits endpoint.
        try:
            limits = client.get_app_limits()
            if limits.success and limits.status == 200:
                results.append(
                    {
                        "test": "Application Token",
                        "ok": True,
                        "message": "Application token is valid.",
                    }
                )
            else:
                results.append(
                    {
                        "test": "Application Token",
                        "ok": False,
                        "message": limits.error
                        or "; ".join(limits.errors)
                        or "Invalid application token.",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "test": "Application Token",
                    "ok": False,
                    "message": f"Could not validate the application token: {format_error(exc)}",
                }
            )

        # 2. Validate the user key with a real send (lowest priority, dry message).
        try:
            send = client.send_message(
                {
                    "message": "Pushover connection test.",
                    "title": "Agent Zero",
                    "priority": -2,
                }
            )
            if send.success:
                results.append(
                    {
                        "test": "User Key",
                        "ok": True,
                        "message": "User key accepted. A lowest-priority test notification was sent.",
                    }
                )
            else:
                results.append(
                    {
                        "test": "User Key",
                        "ok": False,
                        "message": send.error
                        or "; ".join(send.errors)
                        or "Invalid user key.",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "test": "User Key",
                    "ok": False,
                    "message": f"Could not validate the user key: {format_error(exc)}",
                }
            )

        ok = all(r["ok"] for r in results)
        return {
            "success": ok,
            "results": results,
            "configured": True,
            "tested_at": int(time.time()),
        }
