"""Pushover plugin lifecycle hooks.

This file owns the install / pre_update / uninstall lifecycle so the
framework can route lifecycle events here. Per Agent Zero's contract these
functions MUST live in ``hooks.py`` and NEVER in ``execute.py``.

The Pushover plugin uses only the Python standard library, so install and
uninstall do not need to manage external dependencies or processes. The
hooks below focus on one critical property: **user-saved Pushover
configuration must survive plugin updates**.

Background. ``save_plugin_config`` writes the saved config to a path
inside the plugin directory tree (see ``helpers/plugins.py``). On update
the framework may invoke ``uninstall()`` followed by ``install()`` (or it
may replace directory contents outright), so a hook that actively wipes
the config will cause users to re-enter their Pushover token and user
key every single update. We avoid that by:

* never erasing the config in ``uninstall()`` — explicit wipe lives on
  the Setup page ("Reset Pushover Configuration"),
* backing up the config in ``pre_update()`` and ``install()`` before any
  destructive step and restoring it once the install completes.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("plugin.push_zero")

PLUGIN_DIR: Path = Path(__file__).resolve().parent
CONFIG_PATH: Path = PLUGIN_DIR / "config.json"

# Where we stash a backup of the saved config outside the plugin tree so
# it survives even a full directory replacement. /tmp is the simplest,
# platform-neutral location; the file is owner-read/write only.
_BACKUP_PATH: Optional[Path] = None


def _backup_config() -> bool:
    """Copy ``config.json`` to a safe location outside the plugin tree.

    Returns True when a backup was written, False when there was nothing
    to back up or the copy failed. We never raise — backup failures must
    not block the framework from completing an update.
    """
    global _BACKUP_PATH
    if not CONFIG_PATH.exists():
        return False
    try:
        # mkstemp gives us an atomic, owner-only file in /tmp.
        fd, tmp = tempfile.mkstemp(prefix="push_zero_config_backup_", suffix=".json")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(CONFIG_PATH.read_bytes())
            os.chmod(tmp, 0o600)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        _BACKUP_PATH = Path(tmp)
        log.info(
            "Pushover plugin: backed up config.json to %s for update safety.",
            _BACKUP_PATH,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - backup must never crash install
        log.warning(
            "Pushover plugin: could not back up config.json before update: %s",
            exc,
        )
        return False


def _restore_config() -> bool:
    """Restore the config.json backup created by ``_backup_config``."""
    global _BACKUP_PATH
    if _BACKUP_PATH is None or not _BACKUP_PATH.exists():
        return False
    try:
        # Only restore if the current config.json is missing or empty.
        # We never overwrite a freshly-saved config with stale data.
        if CONFIG_PATH.exists() and CONFIG_PATH.stat().st_size > 0:
            log.info(
                "Pushover plugin: config.json already present (%d B); "
                "skipping backup restore.",
                CONFIG_PATH.stat().st_size,
            )
        else:
            shutil.copy2(str(_BACKUP_PATH), str(CONFIG_PATH))
            try:
                CONFIG_PATH.chmod(0o600)
            except OSError:
                pass
            log.info(
                "Pushover plugin: restored config.json (%d B) after update.",
                CONFIG_PATH.stat().st_size,
            )
        # Clean up the backup regardless.
        try:
            _BACKUP_PATH.unlink()
        except OSError:
            pass
        _BACKUP_PATH = None
        return True
    except Exception as exc:  # noqa: BLE001 - restore must never crash install
        log.warning(
            "Pushover plugin: could not restore config.json after update: %s",
            exc,
        )
        return False


def install() -> None:
    """Prepare the plugin for first use; idempotent across updates.

    The framework may invoke ``install()`` on every plugin update. To
    guarantee that the user's saved Pushover configuration (token, user
    key, defaults, emergency settings, advanced settings) survives the
    update, we back up any existing config.json before doing any work
    and restore it after the install completes.
    """
    backed_up = _backup_config()
    log.info("Pushover plugin: install() called; plugin is ready to use.")
    if backed_up:
        _restore_config()


def pre_update() -> None:
    """Prepare for a code update.

    Backs up ``config.json`` (if present) so that ``install()`` can
    restore it once the framework has finished swapping the plugin
    files. ``uninstall()`` is intentionally a no-op for config because
    Agent Zero may invoke it during a code update, not just a full
    removal.
    """
    _backup_config()
    log.info(
        "Pushover plugin: pre_update() called; config backed up if present."
    )


def uninstall() -> None:
    """Clean up plugin-owned state on full uninstall.

    We intentionally do NOT erase the saved Pushover configuration here.
    Agent Zero may invoke ``uninstall()`` as part of a code update, in
    which case wiping the config would force the user to re-enter their
    Pushover token and user key on every plugin update. To explicitly
    reset the configuration, use the Setup page's Reset button (the
    ``/api/plugins/push_zero/reset`` endpoint), which always wipes.
    """
    log.info(
        "Pushover plugin: uninstall() called; saved configuration preserved "
        "(use Setup > Reset to wipe)."
    )


__all__ = ["install", "pre_update", "uninstall"]