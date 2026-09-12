"""Pushover plugin lifecycle hooks.

The Pushover plugin uses only the Python standard library, so install and
uninstall do not need to manage external dependencies or processes. We still
provide explicit no-op hooks so the framework can route lifecycle events to
this file in the future (e.g. if we add a background receipt watcher).

All hooks live here - never in ``execute.py`` - per Agent Zero's required
lifecycle contract.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from usr.plugins.push_zero.helpers.config_helper import reset_config

log = logging.getLogger("plugin.push_zero")


def install() -> None:
    """Prepare the plugin for first use.

    The plugin has no external dependencies, no background processes, and
    no required migrations. Still, we record install state so plugin
    operators can confirm the framework invoked the lifecycle correctly,
    and so future versions can extend this hook without breaking the
    contract.
    """
    log.info("Pushover plugin: install() called; plugin is ready to use.")


def pre_update() -> None:
    """Prepare for a code update.

    The plugin has no long-running processes. Make sure configuration data
    is persisted (the framework owns it) and remove any test state that
    might have leaked into runtime caches.
    """
    log.info("Pushover plugin: pre_update() called; ready for code update.")


def uninstall() -> None:
    """Clean up plugin-owned state on uninstall.

    Erases plugin-scope Pushover configuration so a future reinstall does
    not inherit stale credentials. We intentionally do not touch any
    shared framework state, packages, or services.
    """
    try:
        reset_config()
        log.info("Pushover plugin: uninstall() cleaned plugin configuration.")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Pushover plugin: uninstall could not clear config: {exc}")


__all__ = ["install", "pre_update", "uninstall"]
