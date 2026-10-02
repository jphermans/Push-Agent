"""API handler for saving Pushover credentials.

The handler stores the user-provided Application/API Token and User/Group
Key in Agent Zero's secret store under the plugin's stable keys. The
response payload never echoes the raw credentials back to the browser.
"""

from __future__ import annotations

from helpers.api import ApiHandler
from helpers.plugins import get_plugin_config, save_plugin_config
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import (
    SECRET_API_TOKEN_KEY,
    SECRET_USER_KEY,
    status_snapshot,
)


class SaveHandler(ApiHandler):
    """Save the Pushover credentials and non-secret settings."""

    async def process(self, input: dict, request) -> dict:
        api_token = (input.get("api_token") or "").strip()
        user_key = (input.get("user_key") or "").strip()
        request_timeout = input.get("request_timeout")
        default_title = (input.get("default_title") or "").strip() or "Agent Zero"

        if not api_token or not user_key:
            return {
                "success": False,
                "message": "Both Application/API Token and User/Group Key are required.",
            }

        secrets_mgr = get_secrets_manager()
        try:
            existing = secrets_mgr.load_secrets()
        except Exception:
            existing = {}

        if not isinstance(existing, dict):
            existing = {}

        merged = dict(existing)
        merged[SECRET_API_TOKEN_KEY] = api_token
        merged[SECRET_USER_KEY] = user_key

        try:
            secrets_mgr.save_secrets(secrets_mgr.parse_env_content(_serialize(merged)))
        except AttributeError:
            secrets_mgr.save_secrets(_serialize(merged))

        settings = get_plugin_config(self.name) or {}
        if not isinstance(settings, dict):
            settings = {}
        try:
            timeout_int = int(request_timeout)
        except (TypeError, ValueError):
            timeout_int = int(settings.get("request_timeout", 10) or 10)
        timeout_int = max(1, min(timeout_int, 60))

        settings["request_timeout"] = timeout_int
        settings["priority"] = 0
        settings["default_title"] = default_title

        save_plugin_config(
            self.name,
            project_name=getattr(self, "project_name", None),
            agent_profile=getattr(self, "agent_profile", None),
            settings=settings,
        )

        snapshot = status_snapshot(saved_config=settings, secrets=merged)
        return {
            "success": True,
            "message": "Pushover credentials saved.",
            "status": snapshot,
        }


def _serialize(secrets: dict) -> str:
    """Serialize a secrets dictionary back into the ``KEY=value`` format."""
    lines = []
    for key in sorted(secrets.keys()):
        value = secrets[key]
        if value is None:
            continue
        value_str = str(value).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{value_str}"')
    return "\n".join(lines) + "\n"
