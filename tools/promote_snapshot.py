#!/usr/bin/env python3
"""Promote a release-candidate snapshot and tag it, in one step.

`check_snapshots.py` requires the manifest state and the `vVERSION` tag to
agree, so this writes the state, commits it, and tags that commit.

    python3 tools/promote_snapshot.py --version 0.1.0

It refuses a dirty checkout, a version with no snapshot, a snapshot already
released, and a tag that already exists.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_snapshots import check_snapshots, snapshot_tagged  # noqa: E402


def promote(version: str, *, sign: bool) -> None:
    snapshot_root = ROOT / "snapshots" / version
    manifest_path = snapshot_root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"no snapshot for {version}")

    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
    ).strip()
    if status:
        raise SystemExit("promotion requires a clean checkout")
    if snapshot_tagged(version):
        raise SystemExit(f"v{version} already exists, so {version} is already published")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("state") == "released":
        raise SystemExit(f"snapshot {version} already says released, with no tag to match it")

    manifest["state"] = "released"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Verify everything before committing; a promotion cannot be amended.
    check_snapshots(promoting=version)

    subprocess.run(["git", "add", str(manifest_path.relative_to(ROOT))], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Publish SREF {version}"],
        cwd=ROOT, check=True,
    )
    tag = ["git", "tag", "-a" if not sign else "-s", f"v{version}", "-m", f"SREF {version}"]
    subprocess.run(tag, cwd=ROOT, check=True)
    print(f"committed and tagged v{version}; push the commit and the tag together")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sign", action="store_true", help="create a signed tag")
    arguments = parser.parse_args()
    promote(arguments.version, sign=arguments.sign)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
