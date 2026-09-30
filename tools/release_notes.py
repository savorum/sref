#!/usr/bin/env python3

"""Print the GitHub release text for one version."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def version_key(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag.removeprefix("v").split("."))


def notes(version: str) -> str:
    manifest = json.loads((ROOT / "snapshots" / version / "manifest.json").read_text(encoding="utf-8"))
    tags = subprocess.check_output(["git", "tag", "--list", "v*"], cwd=ROOT, text=True).split()
    earlier = sorted((tag for tag in tags if version_key(tag) < version_key(version)), key=version_key)
    versions = f"Format version {version}, unit registry version {manifest['unit_registry_version']}."
    if not earlier:
        return f"First release of the Structured Recipe Exchange Format. {versions}"
    return f"{versions} Changes since {earlier[-1]} are in CHANGELOG.md."


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: release_notes.py VERSION")
    print(notes(sys.argv[1]))


if __name__ == "__main__":
    main()
