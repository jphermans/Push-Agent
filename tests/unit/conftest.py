"""Pytest fixtures and helpers for the Pushover plugin unit tests.

The tests are designed to run without any real Pushover network calls.
External HTTPS traffic is intercepted by monkeypatching
``urllib.request.urlopen`` so tests can simulate Pushover responses,
timeouts, TLS failures and HTTP errors deterministically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

PLUGIN_ROOT = Path("/a0/usr/plugins/pushover")


def pytest_configure(config):
    """Make ``usr.plugins.pushover.*`` importable without Agent Zero boot."""
    # Agent Zero root contains the ``usr``, ``helpers``, ``agent`` and other
    # top-level packages. The plugin lives at ``usr/plugins/pushover``, so we
    # add the Agent Zero root to ``sys.path`` so that imports of
    # ``usr.plugins.pushover.*`` resolve correctly.
    a0_root = PLUGIN_ROOT.parent.parent.parent
    for entry in ("", str(a0_root)):
        if entry and entry not in sys.path:
            sys.path.insert(0, entry)


@pytest.fixture
def plugin_root():
    """Return the absolute path of the plugin root directory."""
    return PLUGIN_ROOT


class FakeResponse:
    """Minimal stand-in for ``urllib.request.urlopen`` results."""

    def __init__(self, body=None, status=200):
        self._body = body
        self.status = status

    def read_all(self):
        if isinstance(self._body, bytes):
            return self._body
        if isinstance(self._body, str):
            return self._body.encode("utf-8")
        return json.dumps(self._body).encode("utf-8")

    def read(self, *args, **kwargs):
        return self.read_all()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class UrlopenRecorder:
    """Captures every URL that the Pushover client contacts."""

    def __init__(self):
        self.calls = []
        self.next_status = 200
        self.next_body = {"status": 1}
        self.next_error = None
        self.next_http_error = None

    def queue_success(self, body=None):
        self.next_status = 200
        self.next_body = body or {"status": 1}
        self.next_error = None
        self.next_http_error = None

    def queue_pushover_error(self, errors, status=0, http_status=400):
        self.next_status = http_status
        self.next_body = {"status": status, "errors": errors}
        self.next_error = None
        self.next_http_error = None

    def __call__(self, request, context=None, **kwargs):
        self.calls.append(
            {
                "url": request.full_url,
                "data": request.data,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "kwargs": dict(kwargs),
            }
        )
        if self.next_error is not None:
            raise self.next_error
        if self.next_http_error is not None:
            raise self.next_http_error
        return FakeResponse(self.next_body, status=self.next_status)


@pytest.fixture
def urlopen_recorder(monkeypatch):
    """Patch ``urllib.request.urlopen`` and return a recording helper."""
    recorder = UrlopenRecorder()
    import urllib.request as urllib_request

    monkeypatch.setattr(urllib_request, "urlopen", recorder)
    sys.modules.pop("usr.plugins.pushover.helpers.pushover_client", None)
    return recorder


@pytest.fixture
def configured_secrets():
    """Sample secrets and configuration values for tests."""
    return {
        "secrets": {
            "PUSHOVER_API_TOKEN": "a" * 30,
            "PUSHOVER_USER_KEY": "u" * 30,
        },
        "config": {
            "request_timeout": 5,
            "priority": 0,
            "default_title": "Agent Zero",
        },
    }