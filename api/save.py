"""API handler for saving Pushover credentials.

The handler stores the user-provided Application/API Token and User/Group
Key in Agent Zero's secret store under the plugin's stable keys, and
persists the non-secret settings (timeout, default title) to a local
plugin-owned JSON file. The response payload never echoes the raw
credentials back to the browser.

Using a local config file (instead of the framework
``save_plugin_config``) avoids triggering Agent Zero's plugin module
reload, which previously caused HTTP 500 errors on save.
"""

from __future__ import annotations

from helpers.api import ApiHandler
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import (
    LOCAL_CONFIG_PATH,
    SECRET_API_TOKEN_KEY,
    SECRET_USER_KEY,
    load_local_config,
    save_local_config,
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

        secrets_mgr.save_secrets(_serialize(merged))

        existing_config = load_local_config()
        try:
            timeout_int = int(request_timeout)
        except (TypeError, ValueError):
            timeout_int = int(existing_config.get("request_timeout", 10) or 10)
        timeout_int = max(1, min(timeout_int, 60))

        settings = {
            "request_timeout": timeout_int,
            "priority": 0,
            "default_title": default_title,
        }
        settings = save_local_config(settings)

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


# Re-export for tests / introspection.
__all__ = ["SaveHandler", "LOCAL_CONFIG_PATH"]
