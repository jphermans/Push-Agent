"""Lifecycle hooks for the Pushover plugin.

The Pushover plugin has no required setup, dependencies, or background
services. Credentials live in Agent Zero's secret store and are loaded on
demand. The hooks here exist so that the plugin can be installed and removed
through Agent Zero's normal plugin-management APIs without manual cleanup
or a separate execute.py step.
"""

from __future__ import annotations


def install() -> None:
    """Prepare the plugin for use.

    The Pushover plugin has no external dependencies and no startup work.
    The hook is kept so that Agent Zero records a successful install and
    so that re-running install after an update remains a safe no-op.
    """
    return None


def pre_update() -> None:
    """Stop plugin-owned processes before an update.

    The plugin runs no background processes, so this is intentionally a
    no-op. Keeping it defined makes future stateful updates easy to add
    without changing Agent Zero's lifecycle contract.
    """
    return None


def uninstall() -> None:
    """Clean up plugin-owned state before removal.

    The plugin owns no background processes and no local files outside its
    own directory. Agent Zero's secret store entries added through this
    plugin's configuration UI are left in place so that a later reinstall
    does not silently lose credentials.
    """
    return None
