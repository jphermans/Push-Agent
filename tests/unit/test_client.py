"""Tests for the Pushover HTTP client.

External Pushover HTTPS calls are intercepted by the ``urlopen_recorder``
fixture from ``conftest.py``. These tests therefore never reach the real
Pushover API and never expose any real credentials.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error

import pytest

from usr.plugins.pushover.helpers.pushover_client import (
    PUSHOVER_API_ENDPOINT,
    PushoverClient,
)


def _make_client(timeout=2):
    return PushoverClient(
        api_token="a" * 30,
        user_key="u" * 30,
        timeout=timeout,
    )


def test_endpoint_is_official_https_pushover_url():
    assert PUSHOVER_API_ENDPOINT == "https://api.pushover.net/1/messages.json"


def test_client_rejects_missing_credentials():
    with pytest.raises(ValueError):
        PushoverClient(api_token="", user_key="u" * 30)
    with pytest.raises(ValueError):
        PushoverClient(api_token="a" * 30, user_key="")


def test_client_rejects_empty_message(urlopen_recorder):
    client = _make_client()
    with pytest.raises(ValueError):
        client.send(message="")
    with pytest.raises(ValueError):
        client.send(message="   ")


def test_successful_send(urlopen_recorder):
    urlopen_recorder.queue_success()
    client = _make_client()
    result = client.send(message="hello", title="Greeting")
    assert result.success is True
    assert result.status == 1
    assert result.error_message is None


def test_pushover_rejection_returns_error(urlopen_recorder):
    urlopen_recorder.queue_pushover_error(["invalid"])
    client = _make_client()
    result = client.send(message="hello")
    assert result.success is False
    assert "invalid" in (result.error_message or "")


def test_http_error_returns_failure(urlopen_recorder):
    urlopen_recorder.next_http_error = urllib.error.HTTPError(
        url=PUSHOVER_API_ENDPOINT,
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )
    client = _make_client()
    result = client.send(message="hi")
    assert result.success is False
    assert result.http_status == 500


def test_timeout_returns_generic_message(urlopen_recorder):
    urlopen_recorder.next_error = socket.timeout("timed out")
    client = _make_client(timeout=1)
    result = client.send(message="hi")
    assert result.success is False
    assert result.http_status is None
    assert "timed out" in (result.error_message or "").lower()


def test_urlerror_returns_generic_message(urlopen_recorder):
    urlopen_recorder.next_error = urllib.error.URLError(
        socket.gaierror(-2, "Name or service not known")
    )
    client = _make_client()
    result = client.send(message="hi")
    assert result.success is False
    assert result.http_status is None


def test_tls_error_returns_generic_message(urlopen_recorder):
    urlopen_recorder.next_error = ssl.SSLError("certificate verify failed")
    client = _make_client()
    result = client.send(message="hi")
    assert result.success is False
    assert "tls" in (result.error_message or "").lower() or "verif" in (result.error_message or "").lower()


def test_malformed_response_returns_failure(urlopen_recorder):
    urlopen_recorder.next_body = b"<html>not-json</html>"
    client = _make_client()
    result = client.send(message="hi")
    assert result.success is False
    assert result.http_status is not None or result.error_message is not None


def test_form_payload_includes_required_fields(urlopen_recorder):
    urlopen_recorder.queue_success()
    client = _make_client()
    client.send(message="hello", title="Greeting")
    call = urlopen_recorder.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == PUSHOVER_API_ENDPOINT
    body = call["data"].decode("utf-8")
    assert "token=" in body
    assert "user=" in body
    assert "message=hello" in body
    assert "title=Greeting" in body
    assert "priority=0" in body


def test_title_is_optional(urlopen_recorder):
    urlopen_recorder.queue_success()
    client = _make_client()
    client.send(message="hello")
    body = urlopen_recorder.calls[0]["data"].decode("utf-8")
    assert "title=" not in body


def test_request_uses_https_and_form_content_type(urlopen_recorder):
    urlopen_recorder.queue_success()
    client = _make_client()
    client.send(message="hi")
    headers = urlopen_recorder.calls[0]["headers"]
    assert headers.get("Content-type") == "application/x-www-form-urlencoded"
    assert urlopen_recorder.calls[0]["url"].startswith("https://")