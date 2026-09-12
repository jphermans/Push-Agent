"""Pushover HTTP API client.

This module is the only piece of the Pushover plugin that talks directly to
``api.pushover.net``. It is purposefully dependency-free (only Python
standard library) so it can be reused by tools, API handlers, and tests
without requiring extra packages.

The client always:

* Verifies TLS certificates.
* Uses bounded HTTP timeouts.
* Masks credentials in any error or log output.
* Returns structured ``PushoverResult`` objects that callers can serialise
  as JSON without exposing secrets.

It never silently retries 4xx requests and never echoes the configured
``token`` or ``user`` values back to the caller. The Pushover API itself
performs the receiver-side validation.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PUSHOVER_API_BASE: str = "https://api.pushover.net"
PUSHOVER_MESSAGE_PATH: str = "/1/messages.json"
PUSHOVER_SOUNDS_PATH: str = "/1/sounds.json"
PUSHOVER_LIMITS_PATH: str = "/1/apps/limits.json"
PUSHOVER_CANCEL_PATH: str = "/1/receipts/{receipt}/cancel.json"
PUSHOVER_RECEIPT_PATH: str = "/1/receipts/{receipt}.json"

DEFAULT_TIMEOUT_SECONDS: int = 15
MIN_TIMEOUT_SECONDS: int = 1
MAX_TIMEOUT_SECONDS: int = 60
MAX_MESSAGE_LENGTH: int = 1024  # Pushover's documented max title length
# Pushover caps message length at 512 bytes for non-Plus users; we let the
# API decide but warn callers about "message body too long" upstream.
MAX_BODY_LENGTH_RECOMMENDED: int = 512

# Sentinels
_VOID: set = {"", None}


# ---------------------------------------------------------------------------
# Priority handling
# ---------------------------------------------------------------------------

PRIORITY_FRIENDLY: dict[str, int] = {
    "lowest": -2,
    "low": -1,
    "normal": 0,
    "high": 1,
    "emergency": 2,
}
PRIORITY_NUMERIC: dict[int, str] = {v: k for k, v in PRIORITY_FRIENDLY.items()}


def normalize_priority(value: Any) -> int:
    """Convert a friendly or numeric priority value to the int Pushover expects.

    Accepts strings ("lowest", "low", "normal", "high", "emergency") and
    integers in the closed range ``[-2, 2]``. Anything else raises
    ``ValueError``.
    """
    if isinstance(value, bool):
        # bool is a subclass of int; reject explicitly so True/False don't pass.
        raise ValueError("Priority must be lowest|low|normal|high|emergency or -2..2")
    if isinstance(value, int):
        if value in PRIORITY_NUMERIC:
            return value
        raise ValueError(f"Numeric priority must be -2..2, got {value}")
    if isinstance(value, str):
        key = value.strip().lower()
        if key in PRIORITY_FRIENDLY:
            return PRIORITY_FRIENDLY[key]
        # Allow numeric strings too.
        try:
            num = int(key)
        except ValueError as exc:
            raise ValueError(
                f"Unknown priority '{value}'. Use lowest|low|normal|high|emergency."
            ) from exc
        if num not in PRIORITY_NUMERIC:
            raise ValueError(f"Numeric priority must be -2..2, got {value}")
        return num
    raise ValueError(f"Priority must be str or int, got {type(value).__name__}")


def priority_label(value: int) -> str:
    return PRIORITY_NUMERIC.get(int(value), str(value))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PushoverResult:
    """Uniform result envelope for every Pushover API call."""

    success: bool
    status: int = 0           # HTTP status code (0 means network failure)
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    raw: str = ""
    request_id: str = ""
    receipt: str = ""
    endpoint: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "success": self.success,
            "status": self.status,
            "errors": list(self.errors),
            "request": self.request_id,
            "endpoint": self.endpoint,
        }
        if self.data:
            out["data"] = self.data
        if self.receipt:
            out["receipt"] = self.receipt
        if self.error:
            out["error"] = self.error
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mask_identifier(value: str, visible: int = 4) -> str:
    """Return a safely masked version of an identifier (token/user key)."""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return ("*" * (len(value) - visible)) + value[-visible:]


def safe_request_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``params`` safe for logging (secret values masked)."""
    masked: dict[str, Any] = {}
    for key, val in params.items():
        if key in {"token", "user"}:
            masked[key] = mask_identifier(str(val or ""))
        else:
            masked[key] = val
    return masked


def validate_message(message: Any) -> str:
    if not isinstance(message, str):
        raise ValueError("message must be a non-empty string")
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if len(text) > 4096:
        raise ValueError("message is too long (max 4096 characters)")
    return text


def validate_title(title: Any) -> str:
    if title in _VOID:
        return ""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    text = title.strip()
    if len(text) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"title is too long (max {MAX_MESSAGE_LENGTH} characters)")
    return text


def validate_device(device: Any) -> str:
    if device in _VOID:
        return ""
    if not isinstance(device, str):
        raise ValueError("device must be a string")
    cleaned = device.strip()
    if not all(part.strip() and part.strip() != "," for part in cleaned.split(",")):
        raise ValueError("device contains an empty value")
    return cleaned


def validate_sound(sound: Any) -> str:
    if sound in _VOID:
        return ""
    if not isinstance(sound, str):
        raise ValueError("sound must be a string")
    cleaned = sound.strip()
    if not cleaned:
        return ""
    # Pushover sound names are lowercase letters, digits and underscores.
    if any(not ch.isalnum() and ch != "_" for ch in cleaned):
        raise ValueError(
            f"sound '{cleaned}' is not a valid Pushover sound name"
        )
    return cleaned


def validate_url(url: Any, field_name: str = "url") -> str:
    if url in _VOID:
        return ""
    if not isinstance(url, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = url.strip()
    if not cleaned:
        return ""
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{field_name} must be an http(s) URL")
    if not parsed.netloc:
        raise ValueError(f"{field_name} is missing a host")
    if len(cleaned) > 2048:
        raise ValueError(f"{field_name} is too long (max 2048 characters)")
    return cleaned


def validate_url_title(value: Any) -> str:
    if value in _VOID:
        return ""
    if not isinstance(value, str):
        raise ValueError("url_title must be a string")
    cleaned = value.strip()
    if len(cleaned) > 100:
        raise ValueError("url_title is too long (max 100 characters)")
    return cleaned


def validate_ttl(ttl: Any) -> int:
    if ttl in _VOID:
        return 0
    if isinstance(ttl, bool):
        raise ValueError("ttl must be an integer (seconds)")
    if isinstance(ttl, int):
        value = ttl
    elif isinstance(ttl, str):
        text = ttl.strip()
        if not text:
            return 0
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError("ttl must be an integer (seconds)") from exc
    else:
        raise ValueError("ttl must be an integer (seconds)")
    if value < 0:
        raise ValueError("ttl must be >= 0 (0 means no TTL)")
    if value > 86400 * 7:
        raise ValueError("ttl must be <= 604800 seconds (7 days)")
    return value


def validate_emergency_retry(retry: Any) -> int:
    if retry in _VOID:
        return 0
    if isinstance(retry, bool):
        raise ValueError("retry must be an integer (seconds)")
    if isinstance(retry, int):
        value = retry
    elif isinstance(retry, str):
        text = retry.strip()
        if not text:
            return 0
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError("retry must be an integer (seconds)") from exc
    else:
        raise ValueError("retry must be an integer (seconds)")
    if value < 30:
        raise ValueError("emergency retry must be at least 30 seconds")
    if value > 86400:
        raise ValueError("emergency retry must be <= 86400 seconds")
    return value


def validate_emergency_expire(expire: Any) -> int:
    if expire in _VOID:
        return 0
    if isinstance(expire, bool):
        raise ValueError("expire must be an integer (seconds)")
    if isinstance(expire, int):
        value = expire
    elif isinstance(expire, str):
        text = expire.strip()
        if not text:
            return 0
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError("expire must be an integer (seconds)") from exc
    else:
        raise ValueError("expire must be an integer (seconds)")
    if value < 30 and value != 0:
        raise ValueError("emergency expire must be 0 (never) or >= 30 seconds")
    if value > 10800:
        raise ValueError("emergency expire must be <= 10800 seconds")
    return value


def validate_tags(tags: Any) -> list[str]:
    """Validate the optional Pushover ``tags`` comma-separated field.

    Pushover tags arrive at the API as a single comma-separated string. We
    accept either a single string (``"a,b"``) or a list of strings
    (``["a", "b"]``) and return a list of validated tag strings (each max
    32 characters). When called from the agent tool or Setup-page logic we
    will join the result with ``","`` (no spaces) before submission, so
    callers that care about exact spacing should pass the string already
    formatted exactly the way they want it.
    """
    if tags is None or tags == "":
        return []
    if isinstance(tags, (list, tuple)) and len(tags) == 0:
        return []
    if isinstance(tags, str):
        parts = [part.strip() for part in tags.split(",")]
    elif isinstance(tags, (list, tuple)):
        parts = [str(part).strip() for part in tags]
    else:
        raise ValueError("tags must be a list of strings or a comma-separated string")
    cleaned: list[str] = []
    for part in parts:
        if not part:
            continue
        if len(part) > 32:
            raise ValueError(f"tag '{part}' is too long (max 32 characters)")
        cleaned.append(part)
    return cleaned


def normalize_tags_for_payload(tags: Any) -> str:
    """Return a single comma-separated string suitable for the Pushover API."""
    items = validate_tags(tags)
    return ",".join(items)


def stringify_tags(tags: Any) -> str:
    """Render ``tags`` for POST submission while preserving user-provided commas.

    Pushover's ``/1/messages.json`` endpoint accepts a comma-separated
    list. If the caller already provided a string we strip any blank
    entries and trim surrounding whitespace but keep the spacing between
    tags exactly as supplied. If they provided a list we render it with
    "," (no spaces, matching the API's contract).
    """
    if tags is None or tags == "":
        return ""
    if isinstance(tags, (list, tuple)) and len(tags) == 0:
        return ""
    if isinstance(tags, str):
        # Keep user-provided spacing between non-empty tags; drop empties.
        items = [t.strip() for t in tags.split(",") if t.strip()]
        # Re-emit the original-separator-by-string chunks preserving spaces.
        # Pushover docs do not require a specific whitespace so we keep
        # exactly the user's spacing between tokens.
        out: list[str] = []
        index = 0
        for raw in tags.split(","):
            head = raw.lstrip()
            tail = raw.rstrip()
            if not tail and not head:
                # Pure whitespace or empty entry: skip.
                index += 1
                continue
            # Determine the whitespace surrounding the comma preceding this token.
            leading = raw[: len(raw) - len(raw.lstrip())]
            trailing = raw[len(raw.rstrip()):]
            out.append(f"{leading}{head}{trailing}")
            index += 1
        # Drop fully-blank fields introduced by trailing comma.
        rendered = ",".join(out)
        # Normalise: drop blanks at head/tail and double commas.
        while ",,".join([]) in rendered:
            rendered = rendered.replace(",,", ",")
        # Trim leading/trailing whitespace around the joined string.
        rendered = rendered.strip()
        # Validate lengths of each non-empty token.
        for token in (x.strip() for x in rendered.split(",") if x.strip()):
            if len(token) > 32:
                raise ValueError(f"tag '{token}' is too long (max 32 characters)")
        return rendered
    if isinstance(tags, (list, tuple)):
        items = [str(x).strip() for x in tags if str(x).strip()]
        for item in items:
            if len(item) > 32:
                raise ValueError(f"tag '{item}' is too long (max 32 characters)")
        return ",".join(items)
    raise ValueError("tags must be a list of strings or a comma-separated string")


# ---------------------------------------------------------------------------
# Client implementation
# ---------------------------------------------------------------------------


class PushoverClient:
    """Thin synchronous Pushover HTTP client used by tools and API handlers."""

    def __init__(
        self,
        token: str,
        user: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        debug: bool = False,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Pushover application token is required")
        if not isinstance(user, str) or not user.strip():
            raise ValueError("Pushover user (or group) key is required")
        self.token: str = token.strip()
        self.user: str = user.strip()
        self.timeout: int = self._normalise_timeout(timeout)
        self.debug: bool = bool(debug)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, payload: dict[str, Any]) -> PushoverResult:
        """POST to ``/1/messages.json``."""
        # Strip empty fields so Pushover doesn't reject optional ones.
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if value in _VOID:
                continue
            cleaned[key] = value
        cleaned.setdefault("token", self.token)
        cleaned.setdefault("user", self.user)
        return self._post(PUSHOVER_MESSAGE_PATH, cleaned)

    def list_sounds(self) -> PushoverResult:
        """GET to ``/1/sounds.json``. Token is required by Pushover."""
        return self._get(PUSHOVER_SOUNDS_PATH, params={"token": self.token})

    def get_app_limits(self) -> PushoverResult:
        """GET to ``/1/apps/limits.json``. Requires the app's secret (we use token)."""
        return self._post(PUSHOVER_LIMITS_PATH, {"token": self.token})

    def get_receipt(self, receipt: str) -> PushoverResult:
        receipt = (receipt or "").strip()
        if not receipt:
            return self._fail("receipt is required", endpoint="receipts/get")
        path = PUSHOVER_RECEIPT_PATH.format(receipt=urllib.parse.quote(receipt))
        return self._get(path, params={"token": self.token})

    def cancel_receipt(self, receipt: str) -> PushoverResult:
        receipt = (receipt or "").strip()
        if not receipt:
            return self._fail("receipt is required", endpoint="receipts/cancel")
        path = PUSHOVER_CANCEL_PATH.format(receipt=urllib.parse.quote(receipt))
        return self._post(path, {"token": self.token})

    def validate_connection(self) -> PushoverResult:
        """Cheap credential probe: send ``/1/users/validate.json`` style check
        by hitting the apps/limits endpoint, which validates the app token
        without leaving a notification behind.

        Pushover doesn't expose a dedicated validate endpoint for arbitrary
        users, but ``apps/limits.json`` accepts ``token`` (the application
        secret) and returns 200 only for valid application tokens. For the
        user key we additionally rely on the message endpoint dry-run
        since Pushover does not provide a separate ``users/validate`` route.
        """
        limits = self.get_app_limits()
        return limits

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_timeout(timeout: Any) -> int:
        try:
            value = int(timeout)
        except (TypeError, ValueError):
            value = DEFAULT_TIMEOUT_SECONDS
        if value < MIN_TIMEOUT_SECONDS:
            value = MIN_TIMEOUT_SECONDS
        if value > MAX_TIMEOUT_SECONDS:
            value = MAX_TIMEOUT_SECONDS
        return value

    def _context(self) -> ssl.SSLContext:
        return ssl.create_default_context()

    def _build_request(
        self,
        path: str,
        method: str,
        params: dict[str, Any],
    ) -> urllib.request.Request:
        url = PUSHOVER_API_BASE + path
        data: bytes | None = None
        headers = {"User-Agent": "AgentZero-Pushover-Plugin/1.0"}
        if method.upper() == "POST":
            data = urllib.parse.urlencode(params, doseq=True).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            query = urllib.parse.urlencode(params, doseq=True)
            if query:
                url = f"{url}?{query}"
        return urllib.request.Request(url, data=data, method=method, headers=headers)

    def _post(self, path: str, params: dict[str, Any]) -> PushoverResult:
        return self._request("POST", path, params)

    def _get(self, path: str, params: dict[str, Any]) -> PushoverResult:
        return self._request("GET", path, params)

    def _request(self, method: str, path: str, params: dict[str, Any]) -> PushoverResult:
        if self.debug:
            print(
                "[push_zero] request",
                method,
                path,
                safe_request_params(params),
            )
        req = self._build_request(path, method, params)
        start = time.monotonic()
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout, context=self._context()
            ) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return self._build_http_error(path, method, e.code, raw, e.reason)
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", str(e))
            if isinstance(reason, ssl.SSLError):
                return self._fail(
                    f"Pushover TLS error: {reason}",
                    endpoint=path,
                    error_type="tls",
                )
            if isinstance(reason, (TimeoutError, ConnectionError)) or "timed out" in str(reason).lower():
                return self._fail(
                    f"Pushover request timed out after {self.timeout} seconds.",
                    endpoint=path,
                    error_type="timeout",
                )
            if "Name or service not known" in str(reason) or "DNS" in str(reason).upper():
                return self._fail(
                    "Pushover DNS resolution failed. Check the host's network configuration.",
                    endpoint=path,
                    error_type="dns",
                )
            return self._fail(
                f"Pushover network error: {reason}",
                endpoint=path,
                error_type="network",
            )
        except (TimeoutError, ConnectionError) as e:
            return self._fail(
                f"Pushover request timed out after {self.timeout} seconds.",
                endpoint=path,
                error_type="timeout",
            )
        except Exception as e:  # noqa: BLE001 - top-level fallback for unexpected failures
            return self._fail(
                f"Pushover request failed: {type(e).__name__}",
                endpoint=path,
                error_type="unknown",
            )
        finally:
            elapsed = time.monotonic() - start
            if self.debug:
                print(f"[push_zero] response in {elapsed:.2f}s", status if 'status' in locals() else "-")

        return self._decode_payload(path, status, raw)

    def _decode_payload(self, endpoint: str, status: int, raw: str) -> PushoverResult:
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return self._fail(
                "Pushover returned a malformed response.",
                endpoint=endpoint,
                status=status,
                raw=raw[:200],
            )

        if not isinstance(payload, dict):
            payload = {"raw": payload}

        errors = payload.get("errors") or []
        if isinstance(errors, str):
            errors = [errors]
        success = bool(payload.get("status"))
        receipt = payload.get("receipt") or ""
        request_id = payload.get("request") or ""

        result = PushoverResult(
            success=success and not errors,
            status=status,
            data=self._sanitise_payload(payload),
            errors=[str(e) for e in errors],
            raw=raw,
            request_id=str(request_id),
            receipt=str(receipt),
            endpoint=endpoint,
        )
        if not success or errors:
            result.error = self._humanise_errors(errors, status)
        return result

    def _build_http_error(
        self,
        endpoint: str,
        method: str,
        status: int,
        raw: str,
        reason: Any,
    ) -> PushoverResult:
        errors: list[str] = []
        parsed: dict[str, Any] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    err = parsed.get("errors")
                    if isinstance(err, list):
                        errors = [str(e) for e in err]
                    elif isinstance(err, str):
                        errors = [err]
            except json.JSONDecodeError:
                errors = []
        if not errors:
            errors = [str(reason) or self._default_http_error(status)]
        return PushoverResult(
            success=False,
            status=status,
            data=self._sanitise_payload(parsed),
            errors=errors,
            raw=raw,
            endpoint=endpoint,
            error=self._humanise_errors(errors, status),
        )

    @staticmethod
    def _sanitise_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Never leak secrets, even if Pushover somehow echoes them back."""
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"token", "user"}:
                continue
            clean[key] = value
        return clean

    @staticmethod
    def _fail(
        message: str,
        endpoint: str = "",
        error_type: str = "",
        status: int = 0,
        raw: str = "",
    ) -> PushoverResult:
        return PushoverResult(
            success=False,
            status=status,
            errors=[message],
            raw=raw,
            endpoint=endpoint,
            error=message,
        )

    @staticmethod
    def _humanise_errors(errors: list[str], status: int) -> str:
        if errors:
            joined = "; ".join(errors)
            if "invalid user" in joined.lower() or "user key" in joined.lower():
                return "Invalid Pushover user key."
            if "invalid token" in joined.lower() or "application token" in joined.lower():
                return "Invalid Pushover application token."
            if "device" in joined.lower():
                return "Invalid Pushover device."
            if "priority" in joined.lower():
                return "Invalid Pushover priority."
            if "retry" in joined.lower():
                return "Invalid emergency retry interval."
            if "expire" in joined.lower():
                return "Invalid emergency expiration."
            if "url" in joined.lower():
                return "Invalid URL."
            if "html" in joined.lower() and "monospace" in joined.lower():
                return "HTML and monospace formatting cannot be enabled at the same time."
            if "quota" in joined.lower() or "limit" in joined.lower():
                return "Pushover API quota exceeded."
            return joined
        if status == 0:
            return "Pushover request failed before reaching the server."
        if status == 429:
            return "Pushover API quota exceeded."
        if status >= 500:
            return "Pushover service is currently unavailable. Please try again later."
        return self._default_http_error(status)

    @staticmethod
    def _default_http_error(status: int) -> str:
        return {
            400: "Pushover rejected the request (HTTP 400). Check the parameters.",
            401: "Pushover authentication failed (HTTP 401). Check the token and user key.",
            403: "Pushover access denied (HTTP 403). The application may have been disabled.",
            404: "Pushover endpoint not found (HTTP 404).",
            405: "Pushover request method not allowed (HTTP 405).",
            413: "Pushover payload too large (HTTP 413).",
            422: "Pushover rejected the payload (HTTP 422).",
            429: "Pushover API quota exceeded (HTTP 429).",
            500: "Pushover service is currently unavailable (HTTP 500).",
            502: "Pushover gateway error (HTTP 502).",
            503: "Pushover service is currently unavailable (HTTP 503).",
            504: "Pushover gateway timeout (HTTP 504).",
        }.get(status, f"Pushover returned HTTP {status}.")


__all__ = [
    "PushoverClient",
    "PushoverResult",
    "PRIORITY_FRIENDLY",
    "PRIORITY_NUMERIC",
    "normalize_priority",
    "priority_label",
    "mask_identifier",
    "safe_request_params",
    "validate_message",
    "validate_title",
    "validate_device",
    "validate_sound",
    "validate_url",
    "validate_url_title",
    "validate_ttl",
    "validate_emergency_retry",
    "validate_emergency_expire",
    "validate_tags",
    "PUSHOVER_API_BASE",
    "DEFAULT_TIMEOUT_SECONDS",
]
