"""Pushover notification tool (``pushover_notify``).

This is the Agent Zero tool surface for the Pushover integration. Agents
invoke it through the standard tool protocol:

.. code-block:: json

    {
        "action": "send",
        "message": "Deployment completed.",
        "title": "Deployment",
        "priority": "normal"
    }

Supported actions:

* ``send`` - send a Pushover notification (default action).
* ``test`` - send a default Test Notification using the configured defaults.
* ``receipt_status`` - check the status of an emergency notification by
  receipt id.
* ``cancel`` - cancel an emergency notification by receipt id.
* ``cancel_by_tag`` - cancel all emergency notifications that share a tag
  (Pushover doesn't expose a public tag-cancel API; we honour this by
  treating it as a no-op with a descriptive error explaining that Pushover
  only cancels by receipt).

The tool never echoes credentials or URLs in the tool response. Bad inputs
produce a structured error so the agent can correct itself.
"""

from __future__ import annotations

import json
from typing import Any

from helpers.tool import Response, Tool

from usr.plugins.pushover.helpers.config_helper import (
    get_credentials,
    get_raw_config,
    is_configured,
)
from usr.plugins.pushover.helpers.pushover_client import (
    PushoverClient,
    normalize_priority,
    priority_label,
    validate_emergency_retry,
)
from usr.plugins.pushover.helpers.validation import (
    build_message_payload,
    coalesce_defaults,
)


SUPPORTED_ACTIONS: tuple[str, ...] = (
    "send",
    "test",
    "receipt_status",
    "cancel",
    "cancel_by_tag",
)


class PushoverNotify(Tool):
    """Agent-callable Pushover notification tool."""

    async def execute(self, **kwargs) -> Response:  # type: ignore[override]
        action = (self.args.get("action") or "send").strip().lower()
        if action not in SUPPORTED_ACTIONS:
            return Response(
                message=(
                    f"Unknown action '{self.args.get('action')}'. "
                    f"Use one of: {', '.join(SUPPORTED_ACTIONS)}."
                ),
                break_loop=False,
            )

        if not is_configured(agent=self.agent):
            return Response(
                message=(
                    "Pushover is not configured yet. Add your Application Token "
                    "and User Key on the Pushover Setup page, then try again."
                ),
                break_loop=False,
            )

        # Tool-level handlers.
        if action == "test":
            return await self._send_test_notification()
        if action == "receipt_status":
            return await self._receipt_status()
        if action == "cancel":
            return await self._cancel_receipt()
        if action == "cancel_by_tag":
            return self._cancel_by_tag()
        return await self._send()

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _send(self) -> Response:
        cfg = get_raw_config(agent=self.agent)
        merged = coalesce_defaults(self.args, cfg)
        message = merged.get("message")
        if not message:
            return Response(
                message="Error: 'message' is required when action='send'.",
                break_loop=False,
            )

        try:
            payload = build_message_payload(
                message=message,
                title=merged.get("title", ""),
                priority=merged.get("priority", ""),
                sound=merged.get("sound", ""),
                device=merged.get("device", ""),
                url=merged.get("url", ""),
                url_title=merged.get("url_title", ""),
                ttl=merged.get("ttl", ""),
                html=merged.get("html", False),
                monospace=merged.get("monospace", False),
                retry=merged.get("retry", ""),
                expire=merged.get("expire", ""),
                callback=merged.get("callback", ""),
                tags=merged.get("tags", ""),
            )
        except ValueError as exc:
            return Response(
                message=f"Pushover notification rejected: {exc}",
                break_loop=False,
            )

        return await self._deliver(payload)

    async def _send_test_notification(self) -> Response:
        cfg = get_raw_config(agent=self.agent)
        defaults = (cfg or {}).get("defaults", {}) if isinstance(cfg, dict) else {}
        title = (defaults.get("title") if defaults else None) or "Agent Zero"
        try:
            payload = build_message_payload(
                message="Pushover integration is working.",
                title=title,
                priority=defaults.get("priority", "normal") if defaults else "normal",
                sound=defaults.get("sound", "") if defaults else "",
                device=defaults.get("device", "") if defaults else "",
                ttl=defaults.get("ttl", "") if defaults else "",
                url=defaults.get("url", "") if defaults else "",
                url_title=defaults.get("url_title", "") if defaults else "",
                html=bool(defaults.get("html", False)),
                monospace=bool(defaults.get("monospace", False)),
            )
        except ValueError as exc:
            return Response(
                message=f"Pushover test notification rejected: {exc}",
                break_loop=False,
            )
        return await self._deliver(payload)

    async def _receipt_status(self) -> Response:
        receipt = self.args.get("receipt", "")
        if not receipt:
            return Response(
                message="Error: 'receipt' is required when action='receipt_status'.",
                break_loop=False,
            )
        client = self._build_client()
        if isinstance(client, Response):
            return client
        result = client.get_receipt(receipt)
        return self._render_result("receipt_status", result, priority="emergency")

    async def _cancel_receipt(self) -> Response:
        receipt = self.args.get("receipt", "")
        if not receipt:
            return Response(
                message="Error: 'receipt' is required when action='cancel'.",
                break_loop=False,
            )
        client = self._build_client()
        if isinstance(client, Response):
            return client
        result = client.cancel_receipt(receipt)
        return self._render_result("cancel", result)

    def _cancel_by_tag(self) -> Response:
        # Pushover does not currently expose a tag-based emergency cancel
        # endpoint. We refuse clearly so the agent can report it instead of
        # silently doing nothing.
        return Response(
            message=(
                "Pushover does not support cancelling an emergency notification by "
                "tag. Use action='cancel' with the receipt id returned by the "
                "original emergency send."
            ),
            break_loop=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_client(self) -> PushoverClient | Response:
        token, user = get_credentials(agent=self.agent)
        cfg = get_raw_config(agent=self.agent) or {}
        advanced = cfg.get("advanced", {}) if isinstance(cfg, dict) else {}
        try:
            timeout = int(advanced.get("timeout", 15)) if advanced else 15
        except (TypeError, ValueError):
            timeout = 15
        try:
            return PushoverClient(
                token=token,
                user=user,
                timeout=timeout,
                debug=bool(advanced.get("debug", False) if advanced else False),
            )
        except ValueError as exc:
            return Response(
                message=f"Pushover configuration error: {exc}",
                break_loop=False,
            )

    async def _deliver(self, payload: dict[str, Any]) -> Response:
        client = self._build_client()
        if isinstance(client, Response):
            return client
        try:
            result = client.send_message(payload)
        except Exception as exc:  # noqa: BLE001
            return Response(
                message=f"Pushover notification failed: {type(exc).__name__}",
                break_loop=False,
            )
        # Detect emergency priority to surface the receipt separately.
        priority_int = 0
        try:
            priority_int = normalize_priority(payload.get("priority", 0))
        except ValueError:
            priority_int = 0
        return self._render_result(
            "send",
            result,
            priority=priority_label(priority_int),
        )

    def _render_result(
        self,
        action: str,
        result,
        *,
        priority: str = "normal",
    ) -> Response:
        data = result.to_dict()
        if action == "receipt_status":
            message = self._format_receipt_status(result, data)
        else:
            message = self._format_default(action, result, data, priority)
        return Response(
            message=message,
            break_loop=False,
            additional=data,
        )

    @staticmethod
    def _format_default(action: str, result, data: dict[str, Any], priority: str) -> str:
        if result.success:
            if priority == "emergency" and result.receipt:
                return (
                    f"Pushover emergency notification accepted. "
                    f"Receipt id: {result.receipt}. Use action='receipt_status' "
                    "to check whether the user acknowledged it, and "
                    "action='cancel' with the same receipt id to stop retries."
                )
            return (
                "Pushover notification sent successfully."
            )
        detail = result.error or "; ".join(result.errors) or "Unknown Pushover error."
        return f"Pushover notification failed: {detail}"

    @staticmethod
    def _format_receipt_status(result, data: dict[str, Any]) -> str:
        if not result.success:
            detail = result.error or "; ".join(result.errors) or "Unknown Pushover error."
            return f"Could not look up Pushover receipt: {detail}"
        info = result.data or {}
        acknowledged = bool(info.get("acknowledged"))
        expired = bool(info.get("expired"))
        acked_by = info.get("acknowledged_by") or ""
        acked_at = info.get("acknowledged_at") or ""
        called_back = info.get("called_back")
        last_delivered = info.get("last_delivered_at") or ""
        expires_at = info.get("expires_at") or ""
        parts = []
        if acknowledged:
            who = f" by {acked_by}" if acked_by else ""
            when = f" at {acked_at}" if acked_at else ""
            parts.append(f"acknowledged{who}{when}")
        else:
            parts.append("not acknowledged")
        if expired:
            parts.append("expired")
        elif expires_at:
            parts.append(f"expires at {expires_at}")
        if last_delivered:
            parts.append(f"last delivered at {last_delivered}")
        if called_back is not None:
            parts.append(f"called_back={called_back}")
        return "Receipt status: " + "; ".join(parts) + "."


__all__ = ["PushoverNotify"]
