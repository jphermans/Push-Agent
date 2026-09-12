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

        # 1. Validate the application token AND the user (or group) key in
        # a single non-destructive call via Pushover's dedicated
        # /1/users/validate.json endpoint. This is the right endpoint for
        # the Setup page's "Test Connection" button; previous versions
        # called /1/apps/limits.json here, which only validates the token
        # and could surface a misleading 404 "resource not found" when
        # the application had been disabled or the limits endpoint
        # returned a non-200 response for any other reason.
        try:
            validate = client.validate_credentials()
            if validate.success and validate.status == 200:
                results.append(
                    {
                        "test": "Credentials",
                        "ok": True,
                        "message": (
                            "Application token and user (or group) key are valid."
                        ),
                    }
                )
            else:
                joined_errors = "; ".join(validate.errors)
                if "application token" in joined_errors.lower() or "invalid token" in joined_errors.lower():
                    token_message = validate.error or joined_errors or "Invalid application token."
                    user_message = "Could not be validated because the application token is invalid."
                elif "user" in joined_errors.lower() or "user key" in joined_errors.lower():
                    token_message = "Application token is valid."
                    user_message = validate.error or joined_errors or "Invalid user key."
                else:
                    detail = validate.error or joined_errors or "Pushover rejected the credentials."
                    token_message = detail
                    user_message = detail
                results.append(
                    {
                        "test": "Application Token",
                        "ok": validate.success,
                        "message": token_message,
                    }
                )
                results.append(
                    {
                        "test": "User Key",
                        "ok": validate.success,
                        "message": user_message,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "test": "Credentials",
                    "ok": False,
                    "message": f"Could not validate the Pushover credentials: {format_error(exc)}",
                }
            )

        ok = all(r["ok"] for r in results)
        return {
            "success": ok,
            "results": results,
            "configured": True,
            "tested_at": int(time.time()),
        }
