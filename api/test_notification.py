"""API handler that delivers a manual test Pushover notification.

This handler is only meant for the "Send Test Notification" button in the
plugin settings UI. The notification it delivers always uses the fixed
title and message documented in the v0.0.1 spec, so the user can
recognise it on the receiving end.
"""

from __future__ import annotations

from helpers.api import ApiHandler
from helpers.plugins import get_plugin_config
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import (
    load_local_config,
    resolve_credentials,
)
from usr.plugins.pushover.helpers.pushover_client import PushoverClient


class TestNotificationHandler(ApiHandler):
    """Deliver a fixed test message so the user can verify the integration."""

    TEST_TITLE = "Agent Zero"
    TEST_MESSAGE = "Pushover integration is working."

    async def process(self, input: dict, request) -> dict:
        local_config = load_local_config()
        if not local_config:
            try:
                local_config = get_plugin_config(self.name) or {}
            except Exception:
                local_config = {}
        if not isinstance(local_config, dict):
            local_config = {}

        try:
            secrets = get_secrets_manager().load_secrets()
        except Exception:
            secrets = {}
        if not isinstance(secrets, dict):
            secrets = {}

        resolved = resolve_credentials(saved_config=local_config, secrets=secrets)
        if not resolved.is_configured:
            return {
                "success": False,
                "message": "Pushover is not configured. Save your credentials first.",
            }

        try:
            client = PushoverClient(
                api_token=resolved.api_token,
                user_key=resolved.user_key,
                timeout=resolved.request_timeout,
            )
        except ValueError as exc:
            return {
                "success": False,
                "message": str(exc) or "Pushover credentials are missing.",
            }

        result = client.send(
            message=self.TEST_MESSAGE,
            title=self.TEST_TITLE,
            priority=resolved.priority,
        )
        if result.success:
            return {
                "success": True,
                "message": "Test notification sent. Check your device.",
            }

        return {
            "success": False,
            "message": result.error_message or "Pushover notification could not be delivered.",
        }


__all__ = ["TestNotificationHandler"]
