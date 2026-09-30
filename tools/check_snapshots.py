#!/usr/bin/env python3

"""Verify SREF schema and registry snapshots, released and candidate alike.

A snapshot is immutable once its `vVERSION` tag exists, and until then it is a
release candidate that tracks the tree it will be cut from (docs/versioning.md).
Each manifest states which it is, and this checks that claim against whether
the tag exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "snapshots"
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SEMANTIC_UNIT_FIELDS = (
    "id",
    "kind",
    "dimension",
    "definition",
    "ucum",
    "regions",
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_key(value: str) -> tuple[int, int, int]:
    if not VERSION_RE.fullmatch(value):
        raise ValueError(f"invalid snapshot version directory {value!r}")
    return tuple(int(component) for component in value.split("."))  # type: ignore[return-value]


def schema_files(root: Path) -> list[Path]:
    return sorted((root / "schema").glob("*.json"))


def snapshot_files(root: Path) -> list[Path]:
    return schema_files(root) + [root / "registry" / "units.json"]


def snapshot_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    manifest = load_json(manifest_path)
    expected = {
        path.relative_to(root).as_posix(): digest(path) for path in snapshot_files(root)
    }
    if manifest.get("format") != "sref-release-snapshot" or manifest.get("version") != 1:
        raise ValueError(f"{manifest_path}: unsupported snapshot manifest")
    if manifest.get("sref_version") != root.name:
        raise ValueError(f"{manifest_path}: snapshot version does not match directory")
    registry_version = load_json(root / "registry" / "units.json").get("version")
    if manifest.get("unit_registry_version") != registry_version:
        raise ValueError(f"{manifest_path}: registry version does not match snapshot")
    if manifest.get("files") != expected:
        raise ValueError(f"{manifest_path}: file inventory or digests do not match")
    state = manifest.get("state")
    if state not in ("candidate", "released"):
        raise ValueError(f"{manifest_path}: state is 'candidate' or 'released', not {state!r}")
    return manifest


def schema_id_map(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in schema_files(root):
        schema_id = load_json(path).get("$id")
        if not isinstance(schema_id, str):
            raise ValueError(f"{path}: missing schema $id")
        if schema_id in result:
            raise ValueError(f"{path}: duplicate schema $id {schema_id}")
        result[schema_id] = path
    return result


def unit_map(root: Path) -> dict[str, dict[str, Any]]:
    registry = load_json(root / "registry" / "units.json")
    return {unit["id"]: unit for unit in registry["units"]}


def unit_semantics(unit: dict[str, Any]) -> dict[str, Any]:
    return {field: unit[field] for field in SEMANTIC_UNIT_FIELDS if field in unit}


def alias_map(units: dict[str, dict[str, Any]]) -> dict[tuple[str, bool, str], set[str]]:
    result: dict[tuple[str, bool, str], set[str]] = {}
    for unit_id, unit in units.items():
        for alias_set in unit.get("aliases", []):
            language = alias_set["language"].casefold()
            case_sensitive = alias_set["case_sensitive"]
            for form in alias_set["forms"]:
                normalized = form if case_sensitive else form.casefold()
                result.setdefault((language, case_sensitive, normalized), set()).add(
                    unit_id
                )
    return result


def snapshot_tagged(version: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{version}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def tagged_snapshot_changed(version: str) -> bool:
    if not (ROOT / ".git").exists():
        return False
    tag = f"v{version}"
    if not snapshot_tagged(version):
        return False
    return subprocess.run(
        ["git", "diff", "--quiet", tag, "--", f"snapshots/{version}"],
        cwd=ROOT,
        check=False,
    ).returncode != 0


def check_snapshots(root: Path = ROOT, promoting: str | None = None) -> dict[str, str]:
    """Verify every snapshot. `promoting` names one being published right now.

    Between promotion writing `released` and tagging the commit, the state and
    tag disagree; naming the version excuses only that rule for that snapshot.
    """
    snapshots_root = root / "snapshots"
    roots = sorted(
        (path for path in snapshots_root.iterdir() if path.is_dir()),
        key=lambda path: version_key(path.name),
    )
    if not roots:
        raise ValueError("no release snapshots are present")

    current_registry = load_json(root / "registry" / "units.json")
    current_version = load_json(root / "conformance" / "manifest.json")["sref_version"]
    current_root = snapshots_root / current_version
    if current_root not in roots:
        raise ValueError(f"missing snapshot for current registry {current_version}")

    current_schemas = schema_id_map(root)
    current_units = {unit["id"]: unit for unit in current_registry["units"]}
    current_aliases = alias_map(current_units)
    released_schema_ids: dict[str, Path] = {}
    prior_units: dict[str, dict[str, Any]] = {}
    prior_aliases: dict[tuple[str, bool, str], set[str]] = {}

    states: dict[str, str] = {}
    for snapshot_root in roots:
        manifest = snapshot_manifest(snapshot_root)
        states[snapshot_root.name] = manifest["state"]
        if root == ROOT and (ROOT / ".git").exists() and snapshot_root.name != promoting:
            # The tag is the publication event.
            tagged = snapshot_tagged(snapshot_root.name)
            if tagged and manifest["state"] != "released":
                raise ValueError(
                    f"snapshot {snapshot_root.name} is tagged and its manifest still says candidate"
                )
            if not tagged and manifest["state"] == "released":
                raise ValueError(
                    f"snapshot {snapshot_root.name} calls itself released and v{snapshot_root.name} does not exist"
                )
        if root == ROOT and tagged_snapshot_changed(snapshot_root.name):
            raise ValueError(
                f"snapshot {snapshot_root.name} differs from immutable tag v{snapshot_root.name}"
            )

        for schema_id, path in schema_id_map(snapshot_root).items():
            prior = released_schema_ids.get(schema_id)
            if prior is not None and prior.read_bytes() != path.read_bytes():
                raise ValueError(f"released schema $id {schema_id} has different bytes")
            released_schema_ids[schema_id] = path
            current = current_schemas.get(schema_id)
            if current is not None and current.read_bytes() != path.read_bytes():
                raise ValueError(f"current schema reuses released $id {schema_id}")

        released_units = unit_map(snapshot_root)
        released_aliases = alias_map(released_units)
        for unit_id, prior in prior_units.items():
            released = released_units.get(unit_id)
            if released is None:
                raise ValueError(
                    f"snapshot {snapshot_root.name} removed released unit ID {unit_id}"
                )
            if unit_semantics(released) != unit_semantics(prior):
                raise ValueError(
                    f"snapshot {snapshot_root.name} changed released unit ID {unit_id}"
                )
        for alias, prior_ids in prior_aliases.items():
            released_ids = released_aliases.get(alias)
            if released_ids is not None and not prior_ids.issubset(released_ids):
                raise ValueError(
                    f"snapshot {snapshot_root.name} reassigned released alias {alias!r}"
                )
        for unit_id, released in released_units.items():
            current = current_units.get(unit_id)
            if current is None:
                raise ValueError(f"released unit ID {unit_id} was removed")
            if unit_semantics(current) != unit_semantics(released):
                raise ValueError(f"released unit ID {unit_id} changed semantics")
        for alias, released_ids in released_aliases.items():
            current_ids = current_aliases.get(alias)
            if current_ids is not None and not released_ids.issubset(current_ids):
                raise ValueError(f"released alias {alias!r} was reassigned")
        prior_units.update(released_units)
        for alias, unit_ids in released_aliases.items():
            prior_aliases.setdefault(alias, set()).update(unit_ids)

    current_relative_files = {
        path.relative_to(root).as_posix()
        for path in schema_files(root) + [root / "registry" / "units.json"]
    }
    snapshot_relative_files = {
        path.relative_to(current_root).as_posix()
        for path in snapshot_files(current_root)
    }
    if current_relative_files != snapshot_relative_files:
        raise ValueError(
            f"current release surface inventory differs from snapshot {current_version}"
        )
    for relative in snapshot_files(current_root):
        current_path = root / relative.relative_to(current_root)
        if current_path.read_bytes() != relative.read_bytes():
            raise ValueError(
                f"current release surface differs from snapshot {current_version}: "
                f"{relative.relative_to(current_root)}"
            )
    return states


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    try:
        states = check_snapshots()
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"snapshot check failed: {exc}", file=sys.stderr)
        return 1
    versions = sorted(path.name for path in SNAPSHOTS.iterdir() if path.is_dir())
    described = ", ".join(f"{version} ({states.get(version, 'unknown')})" for version in versions)
    print(f"validated snapshots: {described}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
