"""API handler for saving Pushover credentials.

The handler stores the user-provided Application/API Token and User/Group
Key in Agent Zero's secret store under the plugin's stable keys, and
persists the non-secret settings (timeout, default title) to a local
plugin-owned JSON file. The response payload never echoes the raw
credentials back to the browser.

Notes on the secret store: in some Agent Zero deployments the secret
manager tracks multiple files (a global ``/a0/usr/.env`` plus one or more
project-scoped files like
``/a0/usr/projects/<project>/.a0proj/secrets.env``). When that is the
case, ``SecretsManager.save_secrets`` refuses to write - it raises
``RuntimeError('Saving secrets is disabled when multiple files are
configured')`` so it doesn't have to pick which file to mutate. The
Pushover plugin tolerates that case by falling back to writing the two
plugin keys directly into the project's ``.a0proj/secrets.env`` file
using the same ``KEY="value"`` format the secrets manager uses.

Using a local config file for the non-secret settings (instead of
``save_plugin_config``) avoids triggering Agent Zero's plugin module
reload, which previously caused HTTP 500 errors on save.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from helpers.api import ApiHandler
from helpers.secrets import get_secrets_manager

from usr.plugins.pushover.helpers.config_helper import (
    LOCAL_CONFIG_PATH,
    SECRET_API_TOKEN_KEY,
    SECRET_USER_KEY,
    load_local_config,
    save_local_config,
    status_snapshot,
)


class SaveHandler(ApiHandler):
    """Save the Pushover credentials and non-secret settings."""

    async def process(self, input: dict, request) -> dict:
        api_token = (input.get("api_token") or "").strip()
        user_key = (input.get("user_key") or "").strip()
        request_timeout = input.get("request_timeout")
        default_title = (input.get("default_title") or "").strip() or "Agent Zero"

        if not api_token or not user_key:
            return {
                "success": False,
                "message": "Both Application/API Token and User/Group Key are required.",
            }

        merged: dict = {}
        try:
            secrets_mgr = get_secrets_manager()
            existing = secrets_mgr.load_secrets()
            if isinstance(existing, dict):
                merged.update(existing)
        except Exception:
            merged = {}

        merged[SECRET_API_TOKEN_KEY] = api_token
        merged[SECRET_USER_KEY] = user_key

        secrets_ok, secrets_msg = _persist_credentials(merged)
        if not secrets_ok:
            return {
                "success": False,
                "message": secrets_msg,
            }

        existing_config = load_local_config()
        try:
            timeout_int = int(request_timeout)
        except (TypeError, ValueError):
            timeout_int = int(existing_config.get("request_timeout", 10) or 10)
        timeout_int = max(1, min(timeout_int, 60))

        settings = {
            "request_timeout": timeout_int,
            "priority": 0,
            "default_title": default_title,
        }
        try:
            settings = save_local_config(settings)
        except Exception as exc:
            return {
                "success": False,
                "message": f"Failed to save plugin settings: {exc}",
            }

        snapshot = status_snapshot(saved_config=settings, secrets=merged)
        return {
            "success": True,
            "message": "Pushover credentials saved.",
            "status": snapshot,
        }


def _persist_credentials(merged: dict) -> Tuple[bool, str]:
    """Save credentials via the secret manager; fall back to the project file."""
    serialized = _serialize(merged)

    try:
        secrets_mgr = get_secrets_manager()
        secrets_mgr.save_secrets(serialized)
        return True, "saved via secrets manager"
    except RuntimeError as exc:
        msg = str(exc) or "RuntimeError"
    except Exception as exc:
        return False, f"Failed to save credentials: {exc}"

    project_path = _project_secrets_path()
    if not project_path:
        return (
            False,
            f"Pushover credentials could not be saved: {msg}. "
            "No project secrets.env file is available as a fallback.",
        )

    try:
        _write_env_file(project_path, serialized)
        return True, "saved via project secrets.env fallback"
    except Exception as exc:
        return False, f"Pushover credentials could not be saved: {exc}"


def _project_secrets_path() -> Optional[str]:
    """Return the project's secrets.env path, if one is available."""
    try:
        from helpers import projects as projects_helper

        ctx = projects_helper.get_context_project_name()
    except Exception:
        ctx = None

    candidates = []
    if ctx:
        candidates.append(f"/a0/usr/projects/{ctx}/.a0proj/secrets.env")
    candidates.append("/a0/usr/projects/pushnote_plugin/.a0proj/secrets.env")
    for path in candidates:
        parent = os.path.dirname(path)
        if parent and os.path.isdir(parent):
            return path
    return None


def _write_env_file(path: str, serialized: str) -> None:
    """Write KEY="value" lines to ``path`` preserving other lines."""
    new_keys = set()
    for line in serialized.splitlines():
        if not line or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            new_keys.add(key)

    existing_lines: list = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                existing_lines = fh.read().splitlines()
        except OSError:
            existing_lines = []

    kept: list = []
    for line in existing_lines:
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in new_keys:
                continue
        kept.append(line)

    new_payload_lines = [
        line for line in serialized.splitlines() if line and not line.startswith("#")
    ]
    final = kept + new_payload_lines

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(final))
        fh.write("\n")
    os.replace(tmp, path)


def _serialize(secrets: dict) -> str:
    """Serialize a secrets dictionary back into the ``KEY="value"`` format."""
    lines = []
    for key in sorted(secrets.keys()):
        value = secrets[key]
        if value is None:
            continue
        value_str = str(value).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{value_str}"')
    return "\n".join(lines) + "\n"


__all__ = ["SaveHandler", "LOCAL_CONFIG_PATH"]
