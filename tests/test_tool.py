"""End-to-end tests for the Pushover tool pipeline.

The Pushover tool is a thin wrapper around the helper functions
(``coalesce_defaults``, ``build_message_payload``) and the
``PushoverClient`` HTTP layer. We exercise that pipeline directly
instead of instantiating ``helpers.tool.Tool`` because the framework's
base ``Tool`` class requires a live ``Agent`` and ``LoopData`` to
construct properly.

All tests patch the underlying ``urllib.request.urlopen`` so no
real Pushover API call ever occurs. The plugin-local
``PushoverClient`` keeps its own ``urllib.request`` reference, so
tests patch the client module's namespace rather than the global
``urllib`` module.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT_DIR = Path("/a0")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from usr.plugins.pushover.helpers import pushover_client as client_module
from usr.plugins.pushover.helpers.pushover_client import (
    PUSHOVER_MESSAGE_PATH,
    PRIORITY_FRIENDLY,
    PRIORITY_NUMERIC,
    PushoverClient,
    PushoverResult,
    mask_identifier,
    normalize_priority,
    stringify_tags,
    validate_tags,
)
from usr.plugins.pushover.helpers.validation import (
    build_message_payload,
    coalesce_defaults,
)


class FakeResponse:
    def __init__(self, body: dict | str, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        if isinstance(self._body, dict):
            return json.dumps(self._body).encode("utf-8")
        return str(self._body).encode("utf-8")

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def patch_urlopen(target):
    """Patch ``urlopen`` inside the PushoverClient module."""
    return mock.patch.object(client_module.urllib.request, "urlopen", target)


def make_loaded_config():
    """Return a configuration dict that mirrors what config_helper writes."""
    return {
        "token": "APP_TOKEN",
        "user": "USER_KEY",
        "defaults": {
            "title": "Agent Zero",
            "priority": "normal",
            "sound": "magic",
            "device": "iphone",
            "ttl": 3600,
        },
        "emergency": {"retry": 60, "expire": 3600, "callback": ""},
        "advanced": {"timeout": 15, "debug": False},
        "tags": ["agent-zero"],
    }


def capture_urlopen(bodies):
    """Return ``(fake_callable, captured_dict)`` so tests can inspect requests."""
    captured = {"requests": []}
    responses = list(bodies)

    def fake(req, **kwargs):
        captured["requests"].append({
            "url": req.full_url,
            "method": req.method,
            "data": req.data.decode("utf-8") if req.data else None,
        })
        body = responses.pop(0) if responses else {"status": 1, "request": "ok"}
        return FakeResponse(body)

    return fake, captured


def run_tool_pipeline(args, config):
    """Replicate what the agent tool does without instantiating the Tool."""
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            parsed = {}
    else:
        parsed = args
    parsed = parsed or {}
    action = str(parsed.get("action") or "send").strip().lower()

    cfg = config
    if cfg is None:
        return PushoverResult(success=False, status=0, error="Pushover is not configured.")
    if not cfg:
        return PushoverResult(success=False, status=0, error="Pushover is not configured.")

    token = cfg.get("token") or ""
    user = cfg.get("user") or ""
    if not token or not user:
        return PushoverResult(
            success=False,
            status=0,
            error="Pushover application token and user key are required.",
        )

    timeout = (cfg.get("advanced") or {}).get("timeout") or 15
    debug = bool((cfg.get("advanced") or {}).get("debug"))
    client = PushoverClient(token=token, user=user, timeout=timeout, debug=debug)

    if action == "send":
        merged = coalesce_defaults(parsed, cfg)
        # The framework-specific helpers (``_timeout``, ``_debug``) live on
        # the merged dictionary; strip them before submitting to the
        # pure-Python build_message_payload helper.
        stripped = {k: v for k, v in merged.items() if not k.startswith("_")}
        if not (stripped.get("message") or "").strip():
            return PushoverResult(
                success=False,
                status=0,
                error="Pushover message is required.",
            )
        try:
            payload = build_message_payload(**stripped)
        except (ValueError, TypeError) as exc:
            return PushoverResult(success=False, status=0, error=str(exc))
        return client.send_message(payload)
    if action == "test":
        test_payload = build_message_payload(
            message="Pushover integration is working.",
            priority="lowest",
            title=(cfg.get("defaults") or {}).get("title") or "Agent Zero",
        )
        return client.send_message(test_payload)
    if action == "cancel":
        receipt = (parsed.get("receipt") or "").strip()
        if not receipt:
            return PushoverResult(success=False, status=0, error="receipt is required.")
        return client.cancel_receipt(receipt)
    if action == "cancel_by_tag":
        return PushoverResult(
            success=False,
            status=0,
            error="Pushover does not support cancellation by tag. Provide a receipt instead.",
        )
    if action == "receipt_status":
        receipt = (parsed.get("receipt") or "").strip()
        if not receipt:
            return PushoverResult(success=False, status=0, error="receipt is required.")
        return client.get_receipt(receipt)
    return PushoverResult(success=False, status=0, error=f"Unknown action '{action}'.")


class PipelineSendTests(unittest.TestCase):
    def test_send_success(self):
        fake, captured = capture_urlopen([{"status": 1, "request": "req123"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertTrue(result.success)
        self.assertEqual(len(captured["requests"]), 1)

    def test_no_config(self):
        result = run_tool_pipeline({"message": "hi"}, None)
        self.assertFalse(result.success)
        self.assertIn("not configured", result.error.lower())

    def test_message_required(self):
        result = run_tool_pipeline({"title": "no message"}, make_loaded_config())
        self.assertFalse(result.success)
        self.assertIn("message", result.error.lower())

    def test_priority_high_sends_priority_1(self):
        fake, captured = capture_urlopen([{"status": 1, "request": "x"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline(
                {"message": "hi", "priority": "high"}, make_loaded_config()
            )
        self.assertTrue(result.success)
        body = captured["requests"][0]["data"] or ""
        self.assertIn("priority=1", body)
        self.assertNotIn("retry=", body)
        self.assertNotIn("expire=", body)

    def test_priority_emergency_includes_retry_expire(self):
        fake, captured = capture_urlopen(
            [{"status": 1, "request": "x", "receipt": "deadbeef"}]
        )
        with patch_urlopen(fake):
            result = run_tool_pipeline(
                {"message": "alert", "priority": "emergency"},
                make_loaded_config(),
            )
        self.assertTrue(result.success)
        self.assertEqual(result.receipt, "deadbeef")
        body = captured["requests"][0]["data"] or ""
        self.assertIn("priority=2", body)
        self.assertIn("retry=60", body)
        self.assertIn("expire=3600", body)

    def test_credentials_not_returned(self):
        fake, _captured = capture_urlopen([{"status": 1, "request": "x"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertNotIn("APP_TOKEN", str(result.data))
        self.assertNotIn("USER_KEY", str(result.data))

    def test_defaults_applied(self):
        fake, captured = capture_urlopen([{"status": 1, "request": "x"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertTrue(result.success)
        body = captured["requests"][0]["data"] or ""
        self.assertIn("title=Agent+Zero", body)
        self.assertIn("sound=magic", body)
        self.assertIn("device=iphone", body)

    def test_transport_error(self):
        def fake(req, **kwargs):
            raise urllib.error.URLError("Network down")
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertFalse(result.success)
        self.assertIn("network", result.error.lower())

    def test_timeout(self):
        def fake(req, **kwargs):
            raise TimeoutError("timed out")
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error.lower())

    def test_http_400_error(self):
        def fake(req, **kwargs):
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(
                    json.dumps({"status": 0, "errors": ["invalid user key"]}).encode("utf-8")
                ),
            )
        with patch_urlopen(fake):
            result = run_tool_pipeline({"message": "hi"}, make_loaded_config())
        self.assertFalse(result.success)
        self.assertEqual(result.status, 400)
        self.assertIn("user key", result.error.lower())


class PipelineActionTests(unittest.TestCase):
    def test_action_test(self):
        fake, _captured = capture_urlopen([{"status": 1, "request": "x"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline({"action": "test"}, make_loaded_config())
        self.assertTrue(result.success)

    def test_action_cancel(self):
        fake, _captured = capture_urlopen([{"status": 1, "request": "x"}])
        with patch_urlopen(fake):
            result = run_tool_pipeline(
                {"action": "cancel", "receipt": "abc"}, make_loaded_config()
            )
        self.assertTrue(result.success)

    def test_action_cancel_by_tag_refuses(self):
        result = run_tool_pipeline(
            {"action": "cancel_by_tag"}, make_loaded_config()
        )
        self.assertFalse(result.success)
        self.assertIn("does not support", result.error.lower())

    def test_action_receipt_status(self):
        fake, _captured = capture_urlopen([{
            "status": 1, "acknowledged": True, "acknowledged_by": "iphone"
        }])
        with patch_urlopen(fake):
            result = run_tool_pipeline(
                {"action": "receipt_status", "receipt": "abc"}, make_loaded_config()
            )
        self.assertTrue(result.success)
        self.assertTrue(result.data.get("acknowledged"))


class ToolModuleTests(unittest.TestCase):
    """Sanity-check the public surface of the tool module."""

    def test_class_and_prompt(self):
        from usr.plugins.pushover.tools import pushover_notify as tn
        from helpers.tool import Tool as BaseTool
        self.assertTrue(hasattr(tn, "PushoverNotify"))
        self.assertTrue(issubclass(tn.PushoverNotify, BaseTool))
        # The tool ships with a system-prompt fragment that the framework
        # can include for the agent context.
        from pathlib import Path as _P
        prompt_path = (
            _P("/a0/usr/plugins/pushover/prompts")
            / "fw.pushover.tool.md"
        )
        self.assertTrue(prompt_path.exists())
        text = prompt_path.read_text(encoding="utf-8")
        self.assertIn("pushover_notify", text.lower())


if __name__ == "__main__":
    unittest.main()
