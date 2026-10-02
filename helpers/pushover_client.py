"""Minimal HTTPS client for the Pushover REST API.

The Pushover API is a simple HTTPS POST endpoint. The plugin intentionally
avoids extra HTTP libraries (such as ``requests``) and uses ``urllib`` from
Python's standard library. Only the endpoints and parameters documented in
the v0.1.0 plugin spec are implemented.

Pushover API reference (v1, used by this plugin):
    https://api.pushover.net/1/messages.json

Required fields for ``messages.json``:
    token    Application/API Token
    user     User/Group Key
    message  Notification body

Optional field used by this plugin:
    title    Notification title

v0.1.0 always sends ``priority=0`` (normal priority). No additional
Pushover features (emergency, receipts, sounds, attachments, etc.) are
exposed.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

# Pushover official API endpoint.
PUSHOVER_API_ENDPOINT = "https://api.pushover.net/1/messages.json"

# Pushover returns ``status=1`` for success and ``status=0`` for any failure.
# ``errors`` is a list of human-readable error codes.
PUSHOVER_TEST_VALIDATE_SECRET = "PUSHOVER_API_TOKEN"  # noqa: F841 - kept for symmetry

# Reasonable upper bound for the HTTP body Pushover returns (~2 KB is typical).
PUSHOVER_MAX_RESPONSE_BYTES = 65536


@dataclass
class PushoverResult:
    """Result of a Pushover API call.

    Attributes
    ----------
    success:
        True only when Pushover responded with HTTP 200 and ``status=1``.
    status:
        Pushover's ``status`` value (``0`` or ``1``). ``None`` when the
        response could not be parsed.
    errors:
        List of Pushover error codes returned with ``status=0``.
    http_status:
        HTTP status code returned by the Pushover API. ``None`` for
        transport errors (timeout, DNS failure, TLS error).
    error_message:
        Safe-to-display summary of why the call failed.
    """

    success: bool
    status: Optional[int] = None
    errors: Optional[list] = None
    http_status: Optional[int] = None
    error_message: Optional[str] = None


class PushoverClient:
    """Thin client around the Pushover REST API.

    Parameters
    ----------
    api_token:
        Pushover Application/API Token.
    user_key:
        Pushover User/Group Key.
    timeout:
        Per-request timeout in seconds.
    endpoint:
        Override the API endpoint, mainly for tests.
    """

    def __init__(
        self,
        api_token: str,
        user_key: str,
        timeout: int = 10,
        endpoint: str = PUSHOVER_API_ENDPOINT,
    ) -> None:
        if not api_token or not user_key:
            raise ValueError("PushoverClient requires both api_token and user_key.")
        self.api_token = api_token
        self.user_key = user_key
        self.timeout = max(1, int(timeout or 10))
        self.endpoint = endpoint

    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: int = 0,
    ) -> PushoverResult:
        """Send a single Pushover notification.

        The Pushover API enforces a 512-character limit on the message body.
        This method lets the caller decide how to truncate long messages;
        for v0.1.0 the caller is responsible for any length handling.
        """
        if not message or not message.strip():
            raise ValueError("PushoverClient.send requires a non-empty message.")

        form = {
            "token": self.api_token,
            "user": self.user_key,
            "message": message,
            "priority": str(int(priority or 0)),
        }
        if title:
            form["title"] = title

        encoded = urllib.parse.urlencode(form).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=encoded,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "AgentZeroPushoverPlugin/0.1.0",
            },
        )

        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            response = urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=context,
            )
        except urllib.error.HTTPError as exc:
            body = _safe_read(exc)
            parsed = _safe_parse_json(body)
            return PushoverResult(
                success=False,
                status=parsed.get("status"),
                errors=parsed.get("errors"),
                http_status=exc.code,
                error_message=_human_error(parsed.get("errors"), exc.code),
            )
        except urllib.error.URLError as exc:
            return PushoverResult(
                success=False,
                error_message=_transport_error_message(exc),
            )
        except (socket.timeout, TimeoutError) as exc:
            return PushoverResult(
                success=False,
                error_message=f"Pushover request timed out after {self.timeout}s.",
            )
        except (ssl.SSLError, ssl.CertificateError) as exc:
            return PushoverResult(
                success=False,
                error_message="Pushover TLS verification failed.",
            )
        except OSError as exc:
            return PushoverResult(
                success=False,
                error_message=_transport_error_message(exc),
            )

        body = _safe_read(response)
        parsed = _safe_parse_json(body)
        status_value = parsed.get("status")
        return PushoverResult(
            success=(status_value == 1),
            status=status_value,
            errors=parsed.get("errors"),
            http_status=getattr(response, "status", None),
            error_message=None if status_value == 1 else _human_error(parsed.get("errors")),
        )


def _safe_read(response) -> bytes:
    """Read up to PUSHOVER_MAX_RESPONSE_BYTES from a urllib response."""
    try:
        return response.read(PUSHOVER_MAX_RESPONSE_BYTES)
    except Exception:
        return b""


def _safe_parse_json(body: bytes) -> dict:
    """Parse a Pushover JSON body safely."""
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _human_error(errors, http_status: Optional[int] = None) -> str:
    """Translate Pushover error codes into a safe, generic message."""
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, str) and first:
            return f"Pushover rejected the request ({first})."
    if http_status:
        return f"Pushover returned HTTP {http_status}."
    return "Pushover notification could not be delivered."


def _transport_error_message(exc: Exception) -> str:
    """Convert low-level transport exceptions to a generic safe message."""
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return "Pushover request timed out."
        if isinstance(reason, ssl.SSLError):
            return "Pushover TLS verification failed."
        if isinstance(reason, OSError):
            return "Pushover request could not reach the API."
        if reason is not None:
            return "Pushover request could not reach the API."
    if isinstance(exc, socket.timeout):
        return "Pushover request timed out."
    if isinstance(exc, (ssl.SSLError, ssl.CertificateError)):
        return "Pushover TLS verification failed."
    if isinstance(exc, OSError):
        return "Pushover request could not reach the API."
    return "Pushover notification could not be delivered."
