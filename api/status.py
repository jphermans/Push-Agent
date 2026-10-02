"""API handler returning a UI-safe status snapshot for the Pushover plugin."""

from __future__ import annotations

from helpers.api import ApiHandler
from helpers.plugins import get_plugin_config
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import status_snapshot


class StatusHandler(ApiHandler):
    """Return masked credentials, configuration summary and a configured flag."""

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

        snapshot = status_snapshot(saved_config=settings, secrets=secrets)
        snapshot["message"] = (
            "Pushover is configured." if snapshot["configured"] else "Pushover is not configured."
        )
        return {"success": True, "status": snapshot}
