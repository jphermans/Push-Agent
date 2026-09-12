"""Tests for the Pushover HTTP client.

These tests monkey-patch ``urllib.request.urlopen`` so no real Pushover
API calls are ever made.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

# Ensure the framework helpers are reachable as ``helpers`` (not the
# plugin-local ``usr.plugins.<name>.helpers``) and the plugin namespace
# ``usr.plugins.pushover.*`` is importable.
ROOT_DIR = Path("/a0")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from usr.plugins.pushover.helpers import pushover_client
from usr.plugins.pushover.helpers.pushover_client import (
    PRIORITY_FRIENDLY,
    PushoverClient,
    PushoverResult,
    mask_identifier,
    normalize_priority,
    safe_request_params,
    validate_device,
    validate_emergency_expire,
    validate_emergency_retry,
    validate_message,
    validate_sound,
    validate_tags,
    validate_title,
    validate_ttl,
    validate_url,
    validate_url_title,
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


class MaskIdentifierTests(unittest.TestCase):
    def test_mask_short(self):
        self.assertEqual(mask_identifier(""), "")
        self.assertEqual(mask_identifier("abcd", visible=4), "****")
        self.assertEqual(mask_identifier("abcdefgh", visible=4), "****efgh")

    def test_safe_request_params(self):
        masked = safe_request_params({"token": "deadbeef1234", "user": "u1234", "message": "hi"})
        self.assertIn("*", masked["token"])
        self.assertIn("*", masked["user"])
        self.assertEqual(masked["message"], "hi")


class PriorityTests(unittest.TestCase):
    def test_friendly_to_numeric(self):
        for name, num in PRIORITY_FRIENDLY.items():
            self.assertEqual(normalize_priority(name), num)
            self.assertEqual(normalize_priority(name.upper()), num)

    def test_numeric_passthrough(self):
        for num in PRIORITY_FRIENDLY.values():
            self.assertEqual(normalize_priority(num), num)

    def test_invalid_priority(self):
        for bad in [3, -3, "loud", True, [], None]:
            with self.assertRaises(ValueError):
                normalize_priority(bad)


class ValidationTests(unittest.TestCase):
    def test_message(self):
        self.assertEqual(validate_message("hi"), "hi")
        with self.assertRaises(ValueError):
            validate_message("")
        with self.assertRaises(ValueError):
            validate_message(None)
        with self.assertRaises(ValueError):
            validate_message(42)
        with self.assertRaises(ValueError):
            validate_message("a" * 5000)

    def test_title(self):
        self.assertEqual(validate_title(""), "")
        self.assertEqual(validate_title(None), "")
        self.assertEqual(validate_title("Agent"), "Agent")
        with self.assertRaises(ValueError):
            validate_title("a" * 1500)

    def test_device(self):
        self.assertEqual(validate_device("iphone"), "iphone")
        self.assertEqual(validate_device("iphone,ipad"), "iphone,ipad")
        self.assertEqual(validate_device(""), "")
        with self.assertRaises(ValueError):
            validate_device("iphone, ,ipad")

    def test_sound(self):
        self.assertEqual(validate_sound(""), "")
        self.assertEqual(validate_sound("magic"), "magic")
        self.assertEqual(validate_sound("bike_bell"), "bike_bell")
        with self.assertRaises(ValueError):
            validate_sound("drop-table")

    def test_url(self):
        self.assertEqual(validate_url(""), "")
        self.assertEqual(validate_url("https://example.com"), "https://example.com")
        with self.assertRaises(ValueError):
            validate_url("ftp://example.com")
        with self.assertRaises(ValueError):
            validate_url("not a url")
        with self.assertRaises(ValueError):
            validate_url("https://" + "a" * 2100)

    def test_url_title(self):
        self.assertEqual(validate_url_title(""), "")
        with self.assertRaises(ValueError):
            validate_url_title("x" * 200)

    def test_ttl(self):
        self.assertEqual(validate_ttl(""), 0)
        self.assertEqual(validate_ttl("3600"), 3600)
        self.assertEqual(validate_ttl(0), 0)
        with self.assertRaises(ValueError):
            validate_ttl(-1)
        with self.assertRaises(ValueError):
            validate_ttl(99999999999)

    def test_emergency_retry(self):
        self.assertEqual(validate_emergency_retry(60), 60)
        with self.assertRaises(ValueError):
            validate_emergency_retry(10)
        with self.assertRaises(ValueError):
            validate_emergency_retry("not-an-int")

    def test_emergency_expire(self):
        self.assertEqual(validate_emergency_expire(0), 0)
        self.assertEqual(validate_emergency_expire(3600), 3600)
        with self.assertRaises(ValueError):
            validate_emergency_expire(10)
        with self.assertRaises(ValueError):
            validate_emergency_expire(20000)

    def test_tags(self):
        self.assertEqual(validate_tags("a,b,c"), ["a", "b", "c"])
        self.assertEqual(validate_tags(["a", "b"]), ["a", "b"])
        self.assertEqual(validate_tags(""), [])
        self.assertEqual(validate_tags(None), [])
        with self.assertRaises(ValueError):
            validate_tags("a," + "x" * 50)


class ClientSendMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = PushoverClient(token="APP_TOKEN", user="USER_KEY")

    def test_send_message_success(self):
        captured: dict = {}

        def fake_urlopen(req, **kwargs):
            captured["url"] = req.full_url
            captured["data"] = req.data.decode("utf-8") if req.data else None
            return FakeResponse({"status": 1, "request": "abcd1234"})

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.send_message(
                {
                    "message": "Hello",
                    "title": "Agent Zero",
                    "priority": 0,
                    "_extra_empty": "",
                }
            )
        self.assertTrue(result.success)
        self.assertFalse(result.errors)
        self.assertEqual(result.request_id, "abcd1234")
        self.assertIn("app_token", captured["data"].lower())
        # Empty fields should be stripped before sending
        self.assertNotIn("_extra_empty", captured["data"] or "")
        # token / user must not appear in returned data
        self.assertNotIn("token", result.data)
        self.assertNotIn("user", result.data)

    def test_send_message_error(self):
        def fake_urlopen(req, **kwargs):
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(json.dumps({"status": 0, "errors": ["invalid user key"]}).encode("utf-8")),
            )

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.send_message({"message": "Hello"})
        self.assertFalse(result.success)
        self.assertEqual(result.status, 400)
        self.assertIn("user key", result.error.lower())

    def test_timeout(self):
        def fake_urlopen(req, **kwargs):
            raise TimeoutError("timed out")

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.send_message({"message": "Hello"})
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error.lower())

    def test_dns_error(self):
        def fake_urlopen(req, **kwargs):
            raise urllib.error.URLError("Name or service not known")

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.send_message({"message": "Hello"})
        self.assertFalse(result.success)
        self.assertIn("dns", result.error.lower())

    def test_malformed_payload(self):
        def fake_urlopen(req, **kwargs):
            return FakeResponse("this is not json", status=200)

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.send_message({"message": "Hello"})
        self.assertFalse(result.success)
        self.assertIn("malformed", result.error.lower())

    def test_list_sounds(self):
        def fake_urlopen(req, **kwargs):
            return FakeResponse({"status": 1, "sounds": {"magic": "Magic", "bike": "Bike"}})

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.list_sounds()
        self.assertTrue(result.success)
        self.assertIn("sounds", result.data)

    def test_get_receipt(self):
        def fake_urlopen(req, **kwargs):
            return FakeResponse({
                "status": 1,
                "acknowledged": True,
                "acknowledged_by": "device1",
                "acknowledged_at": 1234567890,
            })

        with mock.patch.object(pushover_client.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.client.get_receipt("deadbeef")
        self.assertTrue(result.success)
        self.assertTrue(result.data.get("acknowledged"))

    def test_cancel_receipt_missing(self):
        result = self.client.cancel_receipt("")
        self.assertFalse(result.success)
        self.assertIn("required", result.error)

    def test_constructor_requires_credentials(self):
        with self.assertRaises(ValueError):
            PushoverClient(token="", user="x")
        with self.assertRaises(ValueError):
            PushoverClient(token="x", user="")


class ResultTests(unittest.TestCase):
    def test_to_dict_includes_receipt(self):
        r = PushoverResult(success=True, status=200, receipt="abc")
        out = r.to_dict()
        self.assertTrue(out["success"])
        self.assertEqual(out["receipt"], "abc")

    def test_to_dict_includes_error(self):
        r = PushoverResult(success=False, status=400, error="Bad")
        out = r.to_dict()
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
