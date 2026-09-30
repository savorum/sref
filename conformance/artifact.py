#!/usr/bin/env python3
"""Central validation of what a writer actually emitted.

An adapter may return the artifact it produced, and this module checks it
against the schemas and rules this repository publishes, since a writer and
its paired reader can share a mistake. An adapter that returns no artifact is
not failed, but its writer results are marked as resting on its own word.

`divergence` also compares the artifact with the fixture it was asked to
produce, by the specification's equivalence rules rather than bytes: SREF
defines neither canonical JSON nor canonical ZIP.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import pathlib
import sys
import zipfile
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import semantics  # noqa: E402
import validate  # noqa: E402


class Malformed(ValueError):
    """The adapter's answer did not carry an artifact this can check."""


def decode(answer: dict[str, Any]) -> bytes | None:
    """The bytes an adapter returned, or `None` when it returned none."""
    artifact = answer.get("artifact")
    if artifact is None:
        return None
    encoding = answer.get("artifact_encoding", "utf-8")
    if encoding == "utf-8":
        if not isinstance(artifact, str):
            raise Malformed("a utf-8 artifact is a string")
        return artifact.encode("utf-8")
    if encoding == "base64":
        if not isinstance(artifact, str):
            raise Malformed("a base64 artifact is a string")
        try:
            return base64.b64decode(artifact, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise Malformed(f"the base64 artifact did not decode: {exc}") from exc
    raise Malformed(f"unknown artifact encoding {encoding!r}")


def problems(data: bytes, capability: str) -> list[str]:
    """What this repository's own validator says about the emitted artifact."""
    recipe_validator = validate.validator("recipe.schema.json")
    manifest_validator = validate.validator("manifest.schema.json")
    bundle_validator = validate.validator("bundle-manifest.schema.json")
    units = _units()

    if capability == "package-writer":
        return validate.validate_package_bytes(data, recipe_validator, manifest_validator, units)
    if capability == "bundle-writer":
        return _bundle(data, recipe_validator, manifest_validator, bundle_validator, units)
    return _recipe(data, recipe_validator, units)


def _recipe(data: bytes, recipe_validator, units) -> list[str]:
    try:
        document = validate.load_json_bytes(data)
    except ValueError as exc:
        return [f"the emitted document is not valid SREF JSON: {exc}"]
    found = [error.message for error in recipe_validator.iter_errors(document)]
    if found:
        return found
    return validate.recipe_semantic_errors(document, units)


def _bundle(data: bytes, recipe_validator, manifest_validator, bundle_validator, units) -> list[str]:
    """Bundles are validated from a file, so the bytes are written to one."""
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "emitted.srefbundle"
        path.write_bytes(data)
        return validate.validate_bundle(path, recipe_validator, manifest_validator, bundle_validator, units)


def _units() -> dict[str, dict[str, Any]]:
    registry = validate.load_json(validate.ROOT / "registry" / "units.json")
    return {unit["id"]: unit for unit in registry["units"]}


def divergence(data: bytes, capability: str, request: pathlib.Path) -> str:
    """What the emitted artifact changed against the request it answered.

    Empty when the artifact still says what the fixture said. Comparison is by
    the specification's equivalence rules for the recipe, and by identity and
    bytes for the things a schema cannot compare: an asset's content, and the
    order and identity of a bundle's members.
    """
    try:
        source = request.read_bytes()
        if capability == "package-writer":
            return _package_divergence(source, data)
        if capability == "bundle-writer":
            return _bundle_divergence(source, data)
        return _recipe_divergence(source, data)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        return f"the emitted artifact could not be compared with the request: {exc}"


def _recipe_divergence(source: bytes, emitted: bytes) -> str:
    return semantics.difference(
        validate.load_json_bytes(source), validate.load_json_bytes(emitted)
    )


def _package_divergence(source: bytes, emitted: bytes) -> str:
    """Assets first, then the recipe, so an altered asset is named as such
    rather than reported as a differing digest in the recipe.
    """
    source_recipe, source_assets = _package_content(source)
    emitted_recipe, emitted_assets = _package_content(emitted)
    changed = _asset_divergence(source_assets, emitted_assets)
    if changed:
        return changed
    changed = semantics.difference(source_recipe, emitted_recipe)
    return f"the packaged recipe changed: {changed}" if changed else ""


def _package_content(data: bytes) -> tuple[Any, dict[str, bytes]]:
    """A package's meaning: its recipe, and its assets by the ID that names them.

    Read through the manifest, because an asset's path is a packaging decision
    and its ID is what the recipe refers to.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        recipe = validate.load_json_bytes(archive.read("recipe.json"))
        manifest = validate.load_json_bytes(archive.read("manifest.json"))
        assets = {
            asset["id"]: archive.read(asset["path"]) for asset in manifest["assets"]
        }
    return recipe, assets


def _asset_divergence(source: dict[str, bytes], emitted: dict[str, bytes]) -> str:
    missing = sorted(set(source) - set(emitted))
    if missing:
        return f"asset {missing[0]} is missing from the emitted package"
    invented = sorted(set(emitted) - set(source))
    if invented:
        return f"asset {invented[0]} is not in the request"
    for asset_id in sorted(source):
        if source[asset_id] != emitted[asset_id]:
            return (
                f"asset {asset_id}: the emitted bytes are not the requested ones "
                f"({_digest(source[asset_id])} became {_digest(emitted[asset_id])})"
            )
    return ""


def _bundle_divergence(source: bytes, emitted: bytes) -> str:
    source_members = _bundle_content(source)
    emitted_members = _bundle_content(emitted)
    source_ids = [recipe_id for recipe_id, _ in source_members]
    emitted_ids = [recipe_id for recipe_id, _ in emitted_members]
    if source_ids != emitted_ids:
        # Member order is meaning.
        return (
            f"bundle members changed: {_render(source_ids)} became {_render(emitted_ids)}"
        )
    for (recipe_id, source_member), (_, emitted_member) in zip(
        source_members, emitted_members
    ):
        changed = _package_divergence(source_member, emitted_member)
        if changed:
            return f"bundle member {recipe_id}: {changed}"
    return ""


def _bundle_content(data: bytes) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = validate.load_json_bytes(archive.read("manifest.json"))
        return [
            (item["recipe_id"], archive.read(item["path"]))
            for item in manifest["recipes"]
        ]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _render(ids: list[str]) -> str:
    rendered = ", ".join(ids)
    return rendered if len(rendered) <= 120 else rendered[:117] + "..."
