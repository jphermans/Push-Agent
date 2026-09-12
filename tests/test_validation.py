"""Tests for the Pushover validation helpers.

Tests for ``build_message_payload`` and ``coalesce_defaults``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path("/a0")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from usr.plugins.pushover.helpers.validation import (
    build_message_payload,
    coalesce_defaults,
)


class BuildMessagePayloadTests(unittest.TestCase):
    def test_simple(self):
        payload = build_message_payload(message="Hello")
        self.assertEqual(payload["message"], "Hello")
        self.assertNotIn("title", payload)
        self.assertNotIn("priority", payload)

    def test_full_payload(self):
        payload = build_message_payload(
            message="Hello",
            title="Agent Zero",
            priority="high",
            sound="magic",
            device="iphone",
            url="https://example.com",
            url_title="Open",
            ttl=3600,
            html=True,
        )
        self.assertEqual(payload["priority"], 1)
        self.assertEqual(payload["sound"], "magic")
        self.assertEqual(payload["device"], "iphone")
        self.assertEqual(payload["ttl"], 3600)
        self.assertEqual(payload["html"], 1)
        # retry/expire must not be set for non-emergency
        self.assertNotIn("retry", payload)
        self.assertNotIn("expire", payload)

    def test_emergency_requires_retry_expire(self):
        payload = build_message_payload(
            message="Critical alarm",
            priority="emergency",
            retry=60,
            expire=3600,
        )
        self.assertEqual(payload["priority"], 2)
        self.assertEqual(payload["retry"], 60)
        self.assertEqual(payload["expire"], 3600)

    def test_emergency_with_bad_retry(self):
        with self.assertRaises(ValueError):
            build_message_payload(
                message="Critical",
                priority="emergency",
                retry=10,
                expire=3600,
            )

    def test_html_and_monospace_rejected(self):
        with self.assertRaises(ValueError):
            build_message_payload(
                message="Hello",
                html=True,
                monospace=True,
            )

    def test_string_bool_coercion(self):
        payload = build_message_payload(
            message="Hello",
            html="yes",
            monospace="",
        )
        self.assertEqual(payload["html"], 1)
        self.assertNotIn("monospace", payload)

    def test_tags_merged(self):
        payload = build_message_payload(
            message="Hello",
            tags="agent-zero, alerts",
        )
        self.assertEqual(payload["tags"], "agent-zero, alerts")

    def test_priority_numeric_string(self):
        payload = build_message_payload(message="Hello", priority="2")
        self.assertEqual(payload["priority"], 2)
        self.assertEqual(payload["retry"], 60)  # default values applied
        self.assertEqual(payload["expire"], 3600)

    def test_invalid_priority(self):
        with self.assertRaises(ValueError):
            build_message_payload(message="Hello", priority=5)

    def test_unicode(self):
        payload = build_message_payload(message="Hello ☃")
        self.assertIn("Hello", payload["message"])


class CoalesceDefaultsTests(unittest.TestCase):
    def test_empty_config(self):
        merged = coalesce_defaults({"message": "hi"}, None)
        self.assertEqual(merged["message"], "hi")
        self.assertFalse(merged["html"])
        self.assertFalse(merged["monospace"])

    def test_config_defaults_applied(self):
        cfg = {
            "defaults": {
                "title": "T",
                "priority": "high",
                "sound": "magic",
                "device": "iphone",
                "ttl": "3600",
                "url": "https://example.com",
                "url_title": "Open",
                "html": True,
                "monospace": False,
            },
            "advanced": {"timeout": 30, "debug": True},
        }
        merged = coalesce_defaults({"message": "hi"}, cfg)
        self.assertEqual(merged["title"], "T")
        self.assertEqual(merged["priority"], "high")
        self.assertEqual(merged["sound"], "magic")
        self.assertTrue(merged["html"])
        self.assertFalse(merged["monospace"])
        self.assertEqual(merged["_timeout"], 30)
        self.assertTrue(merged["_debug"])

    def test_args_override_config(self):
        cfg = {"defaults": {"title": "Server", "priority": "low"}}
        merged = coalesce_defaults(
            {"message": "hi", "title": "Agent Zero"},
            cfg,
        )
        self.assertEqual(merged["title"], "Agent Zero")
        self.assertEqual(merged["priority"], "low")

    def test_emergency_picks_retry_from_config(self):
        cfg = {
            "defaults": {"priority": "emergency"},
            "emergency": {"retry": 90, "expire": 1800},
        }
        merged = coalesce_defaults({"message": "hi"}, cfg)
        self.assertEqual(merged["retry"], 90)
        self.assertEqual(merged["expire"], 1800)

    def test_emergency_explicit_overrides(self):
        cfg = {
            "emergency": {"retry": 90, "expire": 1800},
        }
        merged = coalesce_defaults(
            {"message": "hi", "priority": "emergency", "retry": 120},
            cfg,
        )
        self.assertEqual(merged["retry"], 120)
        # Expire stays at config value
        self.assertEqual(merged["expire"], 1800)

    def test_html_arg_false_overrides_config_true(self):
        cfg = {"defaults": {"html": True}}
        merged = coalesce_defaults({"message": "hi", "html": False}, cfg)
        self.assertFalse(merged["html"])


if __name__ == "__main__":
    unittest.main()
