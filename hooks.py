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
HELPERS_DIR: Path = PLUGIN_DIR / "helpers"
HELPERS_PYCACHE: Path = HELPERS_DIR / "__pycache__"

# A source file the runtime imports for every PushoverClient call. We
# keep this list here so the chmod/pyc-clear self-heal in
# ``_ensure_helpers_readable`` always touches the modules that can
# otherwise break the Setup page.
_HELPER_MODULES: tuple[str, ...] = ("push_zero_client", "validation", "config_helper")

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


def _ensure_helpers_readable() -> bool:
    """Make sure every helper module is readable by the Agent Zero runtime.

    When the plugin source tree is edited as root (or via a tool that
    preserves the editor's uid/gid), ``helpers/*.py`` can end up with
    mode 0600 root-owned while the surrounding files remain 0644
    user-owned. Python then cannot ``stat()`` the source file to check
    the bytecode cache's mtime, so it keeps loading a stale ``.pyc``
    that lacks methods the new source defines. The visible symptom
    is an ``AttributeError`` on a method the source clearly has —
    exactly the failure mode that prompted this hook.

    This helper is intentionally idempotent and defensive:

    * chmod ``helpers/*.py`` to 0o644 (read for owner, group, world).
    * delete stale ``__pycache__/<module>.cpython-{312,313}.pyc``
      entries for the modules the runtime imports at request time,
      so the next import re-compiles from readable source.
    * never raise — chmod / unlink failures must not block lifecycle.
    """
    if not HELPERS_DIR.is_dir():
        return False
    fixed = 0
    try:
        for module_name in _HELPER_MODULES:
            src = HELPERS_DIR / f"{module_name}.py"
            if src.is_file():
                try:
                    src.chmod(0o644)
                    fixed += 1
                except OSError as exc:
                    log.warning(
                        "Pushover plugin: could not chmod %s: %s", src, exc
                    )
            if HELPERS_PYCACHE.is_dir():
                for pyc in HELPERS_PYCACHE.glob(f"{module_name}.cpython-*.pyc"):
                    try:
                        pyc.unlink()
                        log.info(
                            "Pushover plugin: removed stale bytecode %s",
                            pyc,
                        )
                    except OSError as exc:
                        log.warning(
                            "Pushover plugin: could not remove %s: %s",
                            pyc,
                            exc,
                        )
        if fixed:
            log.info(
                "Pushover plugin: normalised mode on %d helper module(s).",
                fixed,
            )
        return True
    except Exception as exc:  # noqa: BLE001 - never crash install
        log.warning(
            "Pushover plugin: helper self-heal encountered an error: %s",
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

    We also run ``_ensure_helpers_readable()`` so that any helper
    modules the runtime imports (notably ``push_zero_client``) end up
    with mode 0o644 and a fresh bytecode cache after install. Without
    this, the runtime can keep loading a stale ``.pyc`` that lacks
    methods the new source defines — surfacing as ``AttributeError`` on
    every request until someone manually clears the cache.
    """
    backed_up = _backup_config()
    log.info("Pushover plugin: install() called; plugin is ready to use.")
    if backed_up:
        _restore_config()
    _ensure_helpers_readable()


def pre_update() -> None:
    """Prepare for a code update.

    Backs up ``config.json`` (if present) so that ``install()`` can
    restore it once the framework has finished swapping the plugin
    files. ``uninstall()`` is intentionally a no-op for config because
    Agent Zero may invoke it during a code update, not just a full
    removal.

    We also normalise helper file modes here so that any helpers the
    update touches remain readable by the runtime after the framework
    finishes swapping files in.
    """
    _backup_config()
    log.info(
        "Pushover plugin: pre_update() called; config backed up if present."
    )
    _ensure_helpers_readable()


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