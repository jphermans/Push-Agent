"""Settings validation API handler (``POST /api/plugins/pushover/validate``).

Validates a candidate Pushover configuration without persisting it. Useful
for the Setup page when the user wants to test field values before
"Save Configuration".
"""

from __future__ import annotations

from typing import Any

from flask import Request

from helpers.api import ApiHandler

from usr.plugins.pushover.helpers.pushover_client import validate_url
from usr.plugins.pushover.helpers.validation import build_message_payload


class Validate(ApiHandler):
    """Validate inputs without sending a notification."""

    async def process(self, input: dict, request: Request) -> dict:
        errors: dict[str, str] = {}
        warnings: list[str] = []

        token = (input.get("token") or "").strip()
        user = (input.get("user") or "").strip()
        if not token:
            errors["token"] = "Application/API Token is required."
        if not user:
            errors["user"] = "User / Group Key is required."

        try:
            url_value = validate_url(input.get("url"), field_name="url")
        except ValueError as exc:
            errors["url"] = str(exc)
            url_value = ""

        try:
            build_message_payload(
                message=(input.get("test_message") or "Validate me"),
                title=input.get("title", ""),
                priority=input.get("priority", "normal"),
                sound=input.get("sound", ""),
                device=input.get("device", ""),
                url=url_value,
                url_title=input.get("url_title", ""),
                ttl=input.get("ttl", ""),
                html=bool(input.get("html", False)),
                monospace=bool(input.get("monospace", False)),
                retry=input.get("retry", ""),
                expire=input.get("expire", ""),
            )
        except ValueError as exc:
            errors["message"] = str(exc)

        if bool(input.get("html")) and bool(input.get("monospace")):
            warnings.append("HTML and monospace cannot both be enabled; one will be ignored.")

        priority = (input.get("priority") or "").strip().lower()
        if priority == "emergency":
            try:
                from usr.plugins.pushover.helpers.pushover_client import (
                    validate_emergency_retry,
                    validate_emergency_expire,
                )
                retry_val = input.get("retry", 60)
                expire_val = input.get("expire", 3600)
                validate_emergency_retry(retry_val)
                validate_emergency_expire(expire_val)
            except ValueError as exc:
                errors["emergency"] = str(exc)

        return {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        }
