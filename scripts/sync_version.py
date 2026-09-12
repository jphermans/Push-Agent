#!/usr/bin/env python3
"""Keep user-facing version labels in sync with plugin.yaml.

Run this script before every version bump (or as part of the version
bump itself). It reads the canonical ``version:`` field from
``plugin.yaml`` and rewrites any tracked file that contains a stale
literal version string. The script is idempotent — running it twice
with the same plugin.yaml version produces the same content.

Usage:
    python3 scripts/sync_version.py                # dry run; shows planned diffs
    python3 scripts/sync_version.py --apply        # write changes to disk
    python3 scripts/sync_version.py --check        # exit 0 if in sync, 1 if drift

Files updated (allowlist — add to FILES below if you introduce new
version-bearing strings):
- README.md (the shields.io version badge and the "Shipped at vX.Y.Z"
  subtitle that lives at the bottom of the file).

Files NOT updated (intentional):
- plugin.yaml (this is the source of truth).
- CHANGELOG.md (history of releases — version is meaningful here).
- any test file (tests reference the API surface, not the literal
  version string).
- any file under ``webui/`` (the Setup page reads the version from
  plugin.yaml via the API, not from a hard-coded string).
- any file under ``hooks.py``, ``helpers/``, ``api/``, ``tools/``
  (no literal version strings should live in runtime code).

The script intentionally avoids touching plugin.yaml, CHANGELOG.md,
or any test code so it cannot accidentally rewrite release history.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_YAML = PLUGIN_ROOT / "plugin.yaml"

# Files in which we will rewrite version literals, mapped to the
# (find_regex, replace_template) pair applied to each match.
# The replacement template uses {version} as a placeholder.
FILES: dict[Path, list[tuple[re.Pattern[str], str]]] = {
    PLUGIN_ROOT / "README.md": [
        # shields.io badge:  ...badge/version-1.1.4-E74C3C...
        (
            re.compile(r'(badge/version-)\d+\.\d+\.\d+(-E74C3C)'),
            r'\g<1>{version}\g<2>',
        ),
        # subtitle at the bottom:  "Shipped at v1.1.4."
        (
            re.compile(r'(Shipped at v)\d+\.\d+\.\d+(\.?)'),
            r'\g<1>{version}\g<2>',
        ),
    ],
}


def read_plugin_version() -> str:
    """Extract the canonical version string from plugin.yaml."""
    text = PLUGIN_YAML.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.MULTILINE)
    if not match:
        raise SystemExit(
            f"Could not find a 'version: X.Y.Z' line in {PLUGIN_YAML}"
        )
    return match.group(1)


def rewrite(path: Path, rules: list[tuple[re.Pattern[str], str]], version: str) -> tuple[str, str]:
    """Apply each (pattern, template) rule to the file. Return (original, rewritten)."""
    original = path.read_text(encoding="utf-8")
    rewritten = original
    for pattern, template in rules:
        rewritten = pattern.sub(template.format(version=version), rewritten)
    return original, rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write changes to disk")
    mode.add_argument("--check", action="store_true", help="exit 1 if any drift is detected")
    args = parser.parse_args()

    version = read_plugin_version()
    print(f"plugin.yaml version: {version}")

    drifts: list[tuple[Path, int, str]] = []  # (path, line, current_phrase)
    for path, rules in FILES.items():
        if not path.exists():
            print(f"skip: {path} (does not exist)")
            continue
        original, rewritten = rewrite(path, rules, version)
        if original == rewritten:
            print(f"ok  : {path} (already in sync)")
            continue
        diff_lines = [
            line for line in rewritten.splitlines()
            if line not in original and any(p.search(line) for p, _ in rules)
        ]
        for line in diff_lines:
            drifts.append((path, rewritten.splitlines().index(line) + 1, line.strip()))
        if args.apply:
            path.write_text(rewritten, encoding="utf-8")
            print(f"wrote: {path}")
        else:
            print(f"drift: {path}")
            for line in diff_lines:
                print(f"    would set line: {line.strip()}")

    if args.check:
        if drifts:
            print(f"\nFAIL: {len(drifts)} version drift(s) detected. Run "
                  f"'python3 scripts/sync_version.py --apply' to fix.")
            return 1
        print("\nOK: all version labels are in sync with plugin.yaml")
        return 0

    if drifts and not args.apply:
        print(f"\nFound {len(drifts)} drift(s). Re-run with --apply to write changes.")
        return 0

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
