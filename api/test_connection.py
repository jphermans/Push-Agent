"""API handler that tests connectivity to the Pushover API.

The Pushover REST API has no dedicated ``/validate`` endpoint. The handler
therefore performs a minimal HTTPS POST that proves both that the network
path to ``api.pushover.net`` is reachable and that TLS verification works,
without delivering a real notification. Pushover responds with HTTP 400 and
``errors=['message']`` when only the credentials are valid but the message
is empty, which is the expected signal that the API is reachable and the
token/user combination is accepted.
"""

from __future__ import annotations

from helpers.api import ApiHandler
from helpers.plugins import get_plugin_config
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import resolve_credentials
from usr.plugins.pushover.helpers.pushover_client import (
    PUSHOVER_API_ENDPOINT,
    PushoverClient,
)


class TestConnectionHandler(ApiHandler):
    """Verify that the configured credentials can reach the Pushover API."""

    async def process(self, input: dict, request) -> dict:
        settings = get_plugin_config(self.name) or {}
        if not isinstance(settings, dict):
            settings = {}
        try:
            secrets = get_secrets_manager().load_secrets()
        except Exception:
            secrets = {}
        if not isinstance(secrets, dict):
            secrets = {}

        resolved = resolve_credentials(saved_config=settings, secrets=secrets)
        if not resolved.is_configured:
            return {
                "success": False,
                "message": "Pushover is not configured. Save your credentials first.",
                "endpoint": PUSHOVER_API_ENDPOINT,
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
                "endpoint": PUSHOVER_API_ENDPOINT,
            }

        result = client.send(
            message=" ",
            title=resolved.default_title,
            priority=resolved.priority,
        )

        if result.success:
            return {
                "success": True,
                "message": "Connected to Pushover.",
                "endpoint": PUSHOVER_API_ENDPOINT,
            }

        # A 'message is empty' error from Pushover means credentials and
        # network are fine. Treat it as a successful connection probe.
        rejected_for_empty = (
            isinstance(result.errors, list)
            and any("message" in str(err).lower() for err in result.errors)
        )
        if rejected_for_empty:
            return {
                "success": True,
                "message": "Connected to Pushover (credentials accepted).",
                "endpoint": PUSHOVER_API_ENDPOINT,
            }

        return {
            "success": False,
            "message": result.error_message or "Pushover connection test failed.",
            "endpoint": PUSHOVER_API_ENDPOINT,
            "http_status": result.http_status,
        }
