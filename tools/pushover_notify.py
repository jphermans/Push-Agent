"""Agent-callable tool for sending a Pushover notification.

The tool deliberately exposes a tiny argument surface (message plus an
optional title). It reads the Pushover Application/API Token and User/Group
Key from Agent Zero's secret store and the non-secret settings from the
plugin configuration, so credentials never appear as agent-visible
parameters.

Call this tool only when the user has explicitly asked to be notified via
Pushover. Do not call it as part of an unrelated task.
"""

from __future__ import annotations

import json
from typing import Optional

from helpers.tool import Response, Tool

from usr.plugins.pushover.helpers.config_helper import (
    PUSHOVER_MAX_MESSAGE_LEN,
    resolve_credentials,
)
from usr.plugins.pushover.helpers.pushover_client import PushoverClient


class PushoverNotify(Tool):
    """Send a Pushover notification when the user has explicitly requested one."""

    async def execute(
        self,
        message: str = "",
        title: Optional[str] = None,
        **kwargs,
    ) -> Response:
        if not self.agent:
            return Response(
                message=json.dumps({
                    "success": False,
                    "error": "Pushover: no agent context available; the push tool cannot run.",
                }),
                break_loop=False,
            )

        if not message or not str(message).strip():
            return Response(
                message=json.dumps({
                    "success": False,
                    "error": "Pushover message is required.",
                }),
                break_loop=False,
            )

        clean_message = str(message).strip()
        if len(clean_message) > PUSHOVER_MAX_MESSAGE_LEN:
            clean_message = clean_message[: PUSHOVER_MAX_MESSAGE_LEN]

        try:
            secrets = _load_secrets()
        except Exception:
            secrets = {}

        try:
            from helpers.plugins import get_plugin_config

            settings = get_plugin_config(self.name, agent=self.agent) or {}
        except Exception:
            settings = {}
        if not isinstance(settings, dict):
            settings = {}

        resolved = resolve_credentials(saved_config=settings, secrets=secrets)
        if not resolved.is_configured:
            return Response(
                message=json.dumps({
                    "success": False,
                    "error": "Pushover is not configured. Save your credentials in the plugin settings first.",
                }),
                break_loop=False,
            )

        try:
            client = PushoverClient(
                api_token=resolved.api_token,
                user_key=resolved.user_key,
                timeout=resolved.request_timeout,
            )
        except ValueError as exc:
            return Response(
                message=json.dumps({
                    "success": False,
                    "error": str(exc) or "Pushover credentials are missing.",
                }),
                break_loop=False,
            )

        title_value = (str(title).strip() if title else "") or resolved.default_title

        result = client.send(
            message=clean_message,
            title=title_value,
            priority=resolved.priority,
        )
        if result.success:
            return Response(
                message=json.dumps({
                    "success": True,
                    "message": "Pushover notification sent.",
                }),
                break_loop=False,
            )

        return Response(
            message=json.dumps({
                "success": False,
                "error": result.error_message or "Pushover notification could not be delivered.",
            }),
            break_loop=False,
        )


def _load_secrets() -> dict:
    """Load secrets from the Agent Zero secret manager."""
    try:
        from helpers.secrets import get_secrets_manager

        secrets = get_secrets_manager().load_secrets()
    except Exception:
        return {}
    if not isinstance(secrets, dict):
        return {}
    return secrets
