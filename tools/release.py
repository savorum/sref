#!/usr/bin/env python3

"""Build and independently verify a deterministic SREF source release."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from check_snapshots import check_snapshots


ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def run(command: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def output(command: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def require_clean_checkout() -> None:
    status = output(["git", "status", "--porcelain", "--untracked-files=all"])
    if status:
        raise ValueError("release requires a clean checkout")


def require_tag_match(version: str) -> None:
    ci_tag = os.environ.get("SREF_RELEASE_TAG")
    if not ci_tag:
        return
    expected = f"v{version}"
    if ci_tag != expected:
        raise ValueError(f"tag {ci_tag!r} does not match release version {expected!r}")
    tags = output(["git", "tag", "--points-at", "HEAD"]).splitlines()
    if expected not in tags:
        raise ValueError(f"release tag {expected} does not point at HEAD")


def build_archive(version: str, output_dir: Path) -> tuple[Path, Path]:
    prefix = f"sref-v{version}"
    archive_path = output_dir / f"{prefix}.tar.gz"
    checksum_path = output_dir / f"{prefix}.tar.gz.sha256"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    tar_bytes = subprocess.check_output(
        ["git", "archive", "--format=tar", f"--prefix={prefix}/", "HEAD"],
        cwd=ROOT,
    )
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(tar_bytes)

    archive_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(
        f"{archive_digest}  {archive_path.name}\n", encoding="ascii"
    )
    return archive_path, checksum_path


def verify_archive(archive_path: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="sref-release-") as temporary:
        temporary_root = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(temporary_root, filter="data")
        extracted = temporary_root / f"sref-v{version}"
        if not extracted.is_dir():
            raise ValueError("release archive has an unexpected root directory")
        run([sys.executable, "conformance/validate.py"], extracted)
        run([sys.executable, "conformance/build_archive_fixtures.py", "--check"], extracted)
        run([sys.executable, "tools/check_snapshots.py"], extracted)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version must use MAJOR.MINOR.PATCH without a leading v")

    output_dir = args.output_dir.resolve()
    try:
        require_clean_checkout()
        require_tag_match(args.version)
        check_snapshots()
        sref_version = json.loads(
            (ROOT / "conformance" / "manifest.json").read_text(encoding="utf-8")
        )["sref_version"]
        if sref_version != args.version:
            raise ValueError(
                f"release version {args.version} does not match SREF {sref_version}"
            )
        run([sys.executable, "conformance/validate.py"])
        run([sys.executable, "conformance/build_archive_fixtures.py", "--check"])
        archive_path, checksum_path = build_archive(args.version, output_dir)
        verify_archive(archive_path, args.version)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"release failed: {exc}", file=sys.stderr)
        return 1

    print(f"built and verified {archive_path}")
    print(f"wrote {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
