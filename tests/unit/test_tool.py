"""Tests for the Pushover agent tool.

These tests stub out the Agent Zero helpers (``helpers.tool``,
``helpers.plugins``, ``helpers.secrets``) so the tool can be exercised
without a running Agent Zero instance. Network access is still blocked
by the ``urlopen_recorder`` fixture from ``conftest.py``.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any, Optional

import pytest


class _FakeResponse:
    """Minimal ``helpers.tool.Response`` double used by the tests."""

    def __init__(self, message: str, break_loop: bool = False):
        self.message = message
        self.break_loop = break_loop


def _install_helpers_stubs(monkeypatch, secrets=None, plugin_config=None):
    """Stub the Agent Zero helper modules the tool imports at runtime."""
    helpers_pkg = types.ModuleType("helpers")
    tool_mod = types.ModuleType("helpers.tool")
    tool_mod.Response = _FakeResponse

    class _BaseTool:
        def __init__(self, agent=None):
            self.agent = agent

        async def execute(self):
            raise NotImplementedError

    tool_mod.Tool = _BaseTool

    plugins_mod = types.ModuleType("helpers.plugins")
    plugins_mod.get_plugin_config = lambda *a, **k: plugin_config or {}

    secrets_mod = types.ModuleType("helpers.secrets")

    class _SecretsManager:
        def load_secrets(self_inner):
            return secrets or {}

    secrets_mod.get_secrets_manager = lambda: _SecretsManager()

    monkeypatch.setitem(sys.modules, "helpers", helpers_pkg)
    monkeypatch.setitem(sys.modules, "helpers.tool", tool_mod)
    monkeypatch.setitem(sys.modules, "helpers.plugins", plugins_mod)
    monkeypatch.setitem(sys.modules, "helpers.secrets", secrets_mod)

    sys.modules.pop("usr.plugins.pushover.tools.pushover_notify", None)
    return tool_mod, plugins_mod, secrets_mod


@pytest.fixture
def tool_under_test(monkeypatch, configured_secrets):
    """Return a freshly imported PushoverNotify class with helpers stubbed."""
    _install_helpers_stubs(
        monkeypatch,
        secrets=configured_secrets["secrets"],
        plugin_config=configured_secrets["config"],
    )
    from usr.plugins.pushover.tools.pushover_notify import PushoverNotify

    return PushoverNotify


@pytest.mark.asyncio
async def test_tool_sends_notification_when_configured(urlopen_recorder, tool_under_test):
    urlopen_recorder.queue_success()
    tool = tool_under_test(agent=object())
    response = await tool.execute(message="Hello", title="Greeting")
    assert isinstance(response, _FakeResponse)
    assert response.break_loop is False
    payload = json.loads(response.message)
    assert payload == {"success": True, "message": "Pushover notification sent."}
    assert urlopen_recorder.calls, "tool did not contact the Pushover API"


@pytest.mark.asyncio
async def test_tool_uses_default_title_when_title_missing(urlopen_recorder, tool_under_test):
    urlopen_recorder.queue_success()
    tool = tool_under_test(agent=object())
    await tool.execute(message="hi")
    body = urlopen_recorder.calls[0]["data"].decode("utf-8")
    assert "title=Agent+Zero" in body


@pytest.mark.asyncio
async def test_tool_returns_failure_for_empty_message(urlopen_recorder, tool_under_test):
    tool = tool_under_test(agent=object())
    response = await tool.execute(message="")
    payload = json.loads(response.message)
    assert payload["success"] is False
    assert "message" in payload["error"].lower()
    assert not urlopen_recorder.calls


@pytest.mark.asyncio
async def test_tool_returns_failure_when_not_configured(monkeypatch, urlopen_recorder):
    _install_helpers_stubs(monkeypatch, secrets={}, plugin_config={})
    from usr.plugins.pushover.tools.pushover_notify import PushoverNotify

    tool = PushoverNotify(agent=object())
    response = await tool.execute(message="hi")
    payload = json.loads(response.message)
    assert payload["success"] is False
    assert "not configured" in payload["error"].lower()
    assert not urlopen_recorder.calls


@pytest.mark.asyncio
async def test_tool_returns_failure_when_no_agent(monkeypatch, urlopen_recorder, configured_secrets):
    _install_helpers_stubs(
        monkeypatch,
        secrets=configured_secrets["secrets"],
        plugin_config=configured_secrets["config"],
    )
    from usr.plugins.pushover.tools.pushover_notify import PushoverNotify

    tool = PushoverNotify(agent=None)
    response = await tool.execute(message="hi")
    payload = json.loads(response.message)
    assert payload["success"] is False
    assert not urlopen_recorder.calls


@pytest.mark.asyncio
async def test_tool_truncates_long_messages(urlopen_recorder, tool_under_test):
    urlopen_recorder.queue_success()
    tool = tool_under_test(agent=object())
    long_message = "x" * 1024
    await tool.execute(message=long_message)
    body = urlopen_recorder.calls[0]["data"].decode("utf-8")
    assert "message=" in body
    # Body length for "message=<512 x's>" must be at most 1 + 512
    assert len(body.split("message=", 1)[1].split("&", 1)[0]) <= 512


@pytest.mark.asyncio
async def test_tool_returns_failure_on_api_error(urlopen_recorder, tool_under_test):
    urlopen_recorder.queue_pushover_error(["invalid"])
    tool = tool_under_test(agent=object())
    response = await tool.execute(message="hi")
    payload = json.loads(response.message)
    assert payload["success"] is False
    assert "invalid" in payload["error"]


@pytest.mark.asyncio
async def test_tool_never_returns_raw_credentials(monkeypatch, urlopen_recorder, configured_secrets):
    _install_helpers_stubs(
        monkeypatch,
        secrets=configured_secrets["secrets"],
        plugin_config=configured_secrets["config"],
    )
    urlopen_recorder.queue_success()
    from usr.plugins.pushover.tools.pushover_notify import PushoverNotify

    tool = PushoverNotify(agent=object())
    response = await tool.execute(message="hi")
    assert "a" * 30 not in response.message
    assert "u" * 30 not in response.message


@pytest.mark.asyncio
async def test_tool_uses_provided_title(urlopen_recorder, tool_under_test):
    urlopen_recorder.queue_success()
    tool = tool_under_test(agent=object())
    await tool.execute(message="hi", title="My Title")
    body = urlopen_recorder.calls[0]["data"].decode("utf-8")
    assert "title=My+Title" in body or "title=My%20Title" in body
