#!/usr/bin/env python3

"""Refresh an untagged SREF release-candidate snapshot from the working tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_snapshots import (  # noqa: E402
    VERSION_RE,
    check_snapshots,
    load_json,
    snapshot_files,
)


def tag_exists(version: str) -> bool:
    if not (ROOT / ".git").exists():
        return False
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{version}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def refresh(version: str) -> None:
    """Rewrite snapshots/<version> from schema/ and registry/.

    A snapshot becomes immutable when its release tag exists; until then it
    tracks the tree it will be cut from.
    """
    if not VERSION_RE.fullmatch(version):
        raise ValueError("version must use MAJOR.MINOR.PATCH without a leading v")
    snapshot_root = ROOT / "snapshots" / version
    if not snapshot_root.is_dir():
        raise ValueError(f"snapshot {version} does not exist")
    if tag_exists(version):
        raise ValueError(
            f"snapshot {version} is published at tag v{version} and is immutable; "
            "a change to released schemas requires a new version"
        )

    for source in snapshot_files(ROOT):
        destination = snapshot_root / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    for stale in snapshot_files(snapshot_root):
        if not (ROOT / stale.relative_to(snapshot_root)).is_file():
            stale.unlink()

    manifest = {
        "format": "sref-release-snapshot",
        "version": 1,
        "sref_version": version,
        "unit_registry_version": load_json(snapshot_root / "registry" / "units.json")["version"],
        # Always a candidate: this refuses to run once the tag exists.
        "state": "candidate",
        "files": dict(
            sorted(
                (
                    path.relative_to(snapshot_root).as_posix(),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in snapshot_files(snapshot_root)
            )
        ),
    }
    (snapshot_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh an untagged release-candidate snapshot."
    )
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        refresh(args.version)
        check_snapshots()
    except (OSError, ValueError, KeyError) as error:
        print(f"snapshot refresh failed: {error}", file=sys.stderr)
        return 1
    print(f"refreshed release-candidate snapshot {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
