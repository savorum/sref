#!/usr/bin/env python3

"""Rebuild deterministic SREF package and bundle conformance fixtures."""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import stat
import tempfile
import warnings
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tests" / "packages" / "valid-with-asset"
DESTINATION = ROOT / "tests" / "packages"
BUNDLE_DESTINATION = ROOT / "tests" / "bundles"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def entry(
    name: str, data: bytes, mode: int = stat.S_IFREG | 0o644
) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = mode << 16
    return info, data


def write_package(name: str, entries: list[tuple[zipfile.ZipInfo, bytes]]) -> None:
    write_archive(DESTINATION / name, entries)


def write_archive(path: Path, entries: list[tuple[zipfile.ZipInfo, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for info, data in entries:
                archive.writestr(info, data)


def package_bytes(entries: list[tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    """Builds a package in memory so a bundle can carry it as a member."""
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buffer, "w") as archive:
            for info, data in entries:
                archive.writestr(info, data)
    return buffer.getvalue()


def member(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    """A bundle member is already compressed, so it is stored rather than deflated."""
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info, data


def bundle_manifest(members: list[tuple[str, str, bytes]]) -> bytes:
    return compact_json(
        {
            "format": "sref-bundle",
            "version": 1,
            "recipes": [
                {
                    "member_id": member_id,
                    "recipe_id": recipe_id,
                    "path": f"recipes/{member_id}.sref",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
                for member_id, recipe_id, data in members
            ],
        }
    )


def compact_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def duplicate_json_member(document: bytes, member: bytes) -> bytes:
    """Repeat one exact serialized member without parsing away the duplicate."""
    if document.count(member) != 1:
        raise ValueError(f"expected one JSON member {member!r}")
    return document.replace(member, member + b"," + member, 1)


def build_fixtures() -> None:
    recipe = (SOURCE / "recipe.json").read_bytes()
    manifest = (SOURCE / "manifest.json").read_bytes()
    source_note = (SOURCE / "assets" / "source.txt").read_bytes()
    hero = (SOURCE / "assets" / "hero.svg").read_bytes()
    extra = (SOURCE / "extra.txt").read_bytes()

    base = [
        entry("recipe.json", recipe),
        entry("manifest.json", manifest),
        entry("assets/source.txt", source_note),
        entry("assets/hero.svg", hero),
    ]
    write_package("valid-with-asset.sref", base)
    write_package("missing-asset.sref", base[:-1])
    write_package("undeclared-file.sref", base + [entry("assets/extra.txt", extra)])

    changed_same_size = bytes([source_note[0] ^ 1]) + source_note[1:]
    write_package(
        "asset-digest-mismatch.sref",
        base[:2] + [entry("assets/source.txt", changed_same_size), base[3]],
    )
    write_package(
        "asset-size-mismatch.sref",
        base[:2] + [entry("assets/source.txt", source_note + b"\n"), base[3]],
    )
    write_package(
        "recipe-digest-mismatch.sref",
        [entry("recipe.json", recipe + b"\n"), *base[1:]],
    )

    changed_manifest = copy.deepcopy(json.loads(manifest))
    changed_manifest["assets"][1]["media_type"] = "image/png"
    write_package(
        "manifest-disagreement.sref",
        [base[0], entry("manifest.json", compact_json(changed_manifest)), *base[2:]],
    )

    duplicate_asset_manifest = copy.deepcopy(json.loads(manifest))
    duplicate_asset_manifest["assets"].append(
        copy.deepcopy(duplicate_asset_manifest["assets"][0])
    )
    write_package(
        "duplicate-manifest-asset.sref",
        [
            base[0],
            entry("manifest.json", compact_json(duplicate_asset_manifest)),
            *base[2:],
        ],
    )

    compact_manifest = compact_json(json.loads(manifest))
    package_version = b'"version":"0.1.0"'
    write_package(
        "manifest-duplicate-version.sref",
        [
            base[0],
            entry(
                "manifest.json",
                duplicate_json_member(compact_manifest, package_version),
            ),
            *base[2:],
        ],
    )
    recipe_digest = json.loads(manifest)["recipe"]["sha256"].encode("ascii")
    digest_member = b'"sha256":"' + recipe_digest + b'"'
    write_package(
        "manifest-duplicate-recipe-digest.sref",
        [
            base[0],
            entry(
                "manifest.json",
                duplicate_json_member(compact_manifest, digest_member),
            ),
            *base[2:],
        ],
    )
    write_package(
        "manifest-trailing-value.sref",
        [base[0], entry("manifest.json", compact_manifest + b"{}\n"), *base[2:]],
    )

    write_package("unsafe-traversal.sref", base + [entry("../escape.txt", extra)])
    write_package("backslash-path.sref", base + [entry("assets\\escape.txt", extra)])
    write_package("absolute-path.sref", base + [entry("/escape.txt", extra)])
    write_package("drive-letter-path.sref", base + [entry("C:/escape.txt", extra)])
    write_package("control-character-path.sref", base + [entry("assets/\x01escape.txt", extra)])
    write_package("empty-path-segment.sref", base + [entry("assets//escape.txt", extra)])
    write_package("duplicate-entry.sref", base + [entry("recipe.json", recipe)])
    write_package(
        "symlink-entry.sref",
        base + [entry("assets/link.txt", b"source.txt", stat.S_IFLNK | 0o777)],
    )
    write_package("missing-manifest.sref", [base[0], *base[2:]])
    write_package("missing-recipe.sref", base[1:])
    # The manifest is rebuilt around the truncated bytes so malformed JSON is
    # the only defect; readers verify digests first.
    truncated_recipe = b'{"sref":'
    truncated_manifest = copy.deepcopy(json.loads(manifest))
    truncated_manifest["recipe"]["sha256"] = hashlib.sha256(truncated_recipe).hexdigest()
    truncated_manifest["recipe"]["size"] = len(truncated_recipe)
    write_package(
        "malformed-recipe-json.sref",
        [
            entry("recipe.json", truncated_recipe),
            entry("manifest.json", compact_json(truncated_manifest)),
            *base[2:],
        ],
    )
    build_compression_ratio_fixture(recipe, manifest, base)
    (DESTINATION / "not-a-zip.sref").write_bytes(b"This is not a ZIP archive.\n")
    build_valid_archive_fixtures(recipe, manifest, base)
    partials = []
    for kind in ("ingredients-only", "instructions-only"):
        name = f"minimum-{kind}"
        data, entries = package_around(ROOT / "tests" / "valid" / f"{name}.recipe.json")
        write_package(f"{name}.sref", entries)
        partials.append((name, "minimum", data))
    write_archive(
        BUNDLE_DESTINATION / "minimum-collections.srefbundle",
        [member("manifest.json", bundle_manifest(partials))]
        + [member(f"recipes/{mid}.sref", data) for mid, _rid, data in partials],
    )


def build_compression_ratio_fixture(recipe: bytes, manifest: bytes, base: list) -> None:
    """A package whose only defect is the compression ratio of one entry.

    The filler is declared in the recipe and the manifest, so the ratio is the
    only rule broken.

    The ratio deliberately sits near the ceiling DEFLATE can physically reach.
    A single DEFLATE stream cannot exceed roughly 1032:1 — 258 bytes of match
    per couple of bits — and measurement puts the practical asymptote around
    1029:1 whatever the entry's size. That has a consequence worth stating,
    because it is not obvious and an implementation can look compliant without
    being so: a per-entry ratio ceiling set above about 1032 can never be
    reached, so it is not a limit at all, and an implementation carrying one
    has not satisfied section 15's requirement to impose one. The value is
    implementation policy; that there is an operative value is not.

    Four mebibytes rather than one, because the asymptote is approached from
    below and a fixture nearer to it leaves less room for an inoperative
    ceiling to pass. It costs about four kilobytes in the repository.
    """
    filler = b"0" * (4 * 1024 * 1024)
    declaration = {
        "id": "7compressible",
        "path": "assets/highly-compressible.bin",
        "media_type": "application/octet-stream",
        "sha256": hashlib.sha256(filler).hexdigest(),
        "size": len(filler),
    }
    declared_recipe = copy.deepcopy(json.loads(recipe))
    declared_recipe["assets"].append(copy.deepcopy(declaration))
    recipe_bytes = compact_json(declared_recipe)

    declared_manifest = copy.deepcopy(json.loads(manifest))
    declared_manifest["assets"].append(copy.deepcopy(declaration))
    declared_manifest["recipe"]["sha256"] = hashlib.sha256(recipe_bytes).hexdigest()
    declared_manifest["recipe"]["size"] = len(recipe_bytes)

    write_package(
        "excessive-compression-ratio.sref",
        [
            entry("recipe.json", recipe_bytes),
            entry("manifest.json", compact_json(declared_manifest)),
            *base[2:],
            entry("assets/highly-compressible.bin", filler),
        ],
    )


def minimal_package(title: str | None = None) -> bytes:
    """A second, asset-free member, so a bundle is not one package repeated."""
    recipe = (ROOT / "tests" / "valid" / "minimal.recipe.json").read_bytes()
    if title is not None:
        document = json.loads(recipe)
        document["title"] = title
        recipe = compact_json(document)
    manifest = compact_json(
        {
            "sref_package": {"version": "0.1.0"},
            "recipe": {
                "path": "recipe.json",
                "media_type": "application/json",
                "sha256": hashlib.sha256(recipe).hexdigest(),
                "size": len(recipe),
            },
            "assets": [],
        }
    )
    return package_bytes([entry("recipe.json", recipe), entry("manifest.json", manifest)])


def build_manifest_schema_fixtures() -> None:
    """Packages whose manifest does not satisfy the schema section 14 makes
    normative for it.

    These are all the manifest's fixed and required members, including an
    asset-free package's `assets: []`.

    A malformed asset entry is deliberately absent. Removing a member from one
    breaks the schema and puts the manifest at odds with the recipe at the same
    time, and a case that breaks two rules cannot declare which category an
    implementation must report: both answers are correct and the corpus would
    be picking one arbitrarily. The same is true of a bundle member entry with
    no `recipe_id`.
    """
    recipe = (ROOT / "tests" / "valid" / "minimal.recipe.json").read_bytes()
    manifest = {
        "sref_package": {"version": "0.1.0"},
        "recipe": {
            "path": "recipe.json",
            "media_type": "application/json",
            "sha256": hashlib.sha256(recipe).hexdigest(),
            "size": len(recipe),
        },
        "assets": [],
    }

    def package(name: str, change=None) -> None:
        altered = copy.deepcopy(manifest)
        if change is not None:
            change(altered)
        write_package(
            name,
            [entry("recipe.json", recipe), entry("manifest.json", compact_json(altered))],
        )

    # The valid case first, because a corpus of only invalid manifests would
    # be satisfied by an implementation that rejected every package.
    package("valid-no-assets.sref")

    package("manifest-missing-assets.sref", lambda m: m.pop("assets"))
    package("manifest-missing-package-header.sref", lambda m: m.pop("sref_package"))
    package("manifest-unsupported-package-version.sref", lambda m: m["sref_package"].update(version="9.9.9"))
    package("manifest-wrong-recipe-path.sref", lambda m: m["recipe"].update(path="not-recipe.json"))
    package("manifest-wrong-recipe-media-type.sref", lambda m: m["recipe"].update(media_type="text/plain"))
    package("manifest-extra-member.sref", lambda m: m.update(generated_by="a writer that added a member"))


def build_bundle_manifest_schema_fixtures(manifest: bytes, base: list) -> None:
    """Bundle manifests whose fixed members are wrong.

    The same class as the package cases above, and the same reasoning: `format`
    and `version` are constants, and an implementation that never checks them
    will read a future bundle format as though it were this one.
    """

    def bundle(name: str, change) -> None:
        altered = copy.deepcopy(json.loads(manifest))
        change(altered)
        write_archive(
            BUNDLE_DESTINATION / name,
            [member("manifest.json", compact_json(altered)), *base[1:]],
        )

    bundle("manifest-wrong-format.srefbundle", lambda m: m.update(format="sref-collection"))
    bundle("manifest-missing-format.srefbundle", lambda m: m.pop("format"))
    bundle("manifest-wrong-version.srefbundle", lambda m: m.update(version=2))
    bundle("manifest-extra-member.srefbundle", lambda m: m.update(generated_by="a writer that added a member"))


def package_around(recipe_path: Path) -> tuple[bytes, list]:
    """Package an existing corpus recipe unchanged, with no assets.

    Reusing a recipe the corpus already validates keeps these fixtures about the
    container. A hand-written carrier would be one more document to get wrong,
    and getting it wrong would look like an archive defect.
    """
    recipe = recipe_path.read_bytes()
    manifest = compact_json(
        {
            "sref_package": {"version": "0.1.0"},
            "recipe": {
                "path": "recipe.json",
                "media_type": "application/json",
                "sha256": hashlib.sha256(recipe).hexdigest(),
                "size": len(recipe),
            },
            "assets": [],
        }
    )
    entries = [entry("recipe.json", recipe), entry("manifest.json", manifest)]
    return package_bytes(entries), entries


def build_valid_archive_fixtures(recipe: bytes, manifest: bytes, base: list) -> None:
    """Build valid archive fixtures indexed for both reader and writer capabilities.

    Ensures valid archives exercise extensions, unknown members, and unknown
    registry IDs so readers and writers are tested for full preservation. Carrier
    recipes are sourced from ROOT.
    """
    roundtrip = ROOT / "tests" / "roundtrip"

    # Three asset media types in one package, one of them binary.
    binary = bytes(range(256)) * 8
    declaration = {
        "id": "8binary-note",
        "path": "assets/notes.bin",
        "media_type": "application/octet-stream",
        "sha256": hashlib.sha256(binary).hexdigest(),
        "size": len(binary),
    }
    rich_recipe = copy.deepcopy(json.loads(recipe))
    rich_recipe["assets"].append(copy.deepcopy(declaration))
    rich_recipe_bytes = compact_json(rich_recipe)
    rich_manifest = copy.deepcopy(json.loads(manifest))
    rich_manifest["assets"].append(copy.deepcopy(declaration))
    rich_manifest["recipe"]["sha256"] = hashlib.sha256(rich_recipe_bytes).hexdigest()
    rich_manifest["recipe"]["size"] = len(rich_recipe_bytes)
    write_package(
        "valid-media-types.sref",
        [
            entry("recipe.json", rich_recipe_bytes),
            entry("manifest.json", compact_json(rich_manifest)),
            *base[2:],
            entry("assets/notes.bin", binary),
        ],
    )

    for name, source in (
        ("valid-extensions.sref", "extension-preservation.recipe.json"),
        ("valid-forward-members.sref", "forward-compatible-member-depths.recipe.json"),
        ("valid-forward-units.sref", "forward-compatible-unit-shapes.recipe.json"),
    ):
        _data, entries = package_around(roundtrip / source)
        write_package(name, entries)


def build_multi_member_bundle() -> None:
    """A bundle of three mixed members, so reversal differs from a swap.

    One member has assets and two do not; one carries extensions.
    """
    ordered = [
        ("1r00001", "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
         (DESTINATION / "valid-with-asset.sref").read_bytes()),
        ("r000002", "minimal", minimal_package()),
        ("r000003", "extension-preservation",
         (DESTINATION / "valid-extensions.sref").read_bytes()),
    ]
    write_archive(
        BUNDLE_DESTINATION / "valid-three-members.srefbundle",
        [member("manifest.json", bundle_manifest(ordered))]
        + [member(f"recipes/{mid}.sref", data) for mid, _rid, data in ordered],
    )


def build_translation_bundle() -> None:
    """Two renditions that name each other by bundle-local recipe ID."""
    ordered = [
        ("r000001", "carottes-roties",
         package_around(ROOT / "tests" / "roundtrip" / "translation-preservation.recipe.json")[0]),
        ("r000002", "ofenrueebli",
         package_around(ROOT / "tests" / "valid" / "translation-counterpart.recipe.json")[0]),
    ]
    write_archive(
        BUNDLE_DESTINATION / "valid-linked-translations.srefbundle",
        [member("manifest.json", bundle_manifest(ordered))]
        + [member(f"recipes/{mid}.sref", data) for mid, _rid, data in ordered],
    )


def build_bundle_fixtures() -> None:
    with_asset = (DESTINATION / "valid-with-asset.sref").read_bytes()
    minimal = minimal_package()
    ordered = [
        ("1r00001", "3f2504e0-4f89-41d3-9a0c-0305e82c3301", with_asset),
        ("r000002", "minimal", minimal),
    ]
    manifest = bundle_manifest(ordered)

    base = [member("manifest.json", manifest)] + [
        member(f"recipes/{member_id}.sref", data)
        for member_id, _recipe_id, data in ordered
    ]

    def bundle(name: str, entries: list[tuple[zipfile.ZipInfo, bytes]]) -> None:
        write_archive(BUNDLE_DESTINATION / name, entries)

    bundle("valid.srefbundle", base)
    build_bundle_manifest_schema_fixtures(manifest, base)
    bundle(
        "manifest-duplicate-format.srefbundle",
        [
            member(
                "manifest.json",
                duplicate_json_member(manifest, b'"format":"sref-bundle"'),
            ),
            *base[1:],
        ],
    )
    first_member_id = b'"member_id":"1r00001"'
    bundle(
        "manifest-duplicate-member-id.srefbundle",
        [
            member(
                "manifest.json",
                duplicate_json_member(manifest, first_member_id),
            ),
            *base[1:],
        ],
    )
    bundle(
        "manifest-trailing-value.srefbundle",
        [member("manifest.json", manifest + b"{}\n"), *base[1:]],
    )
    bundle("missing-member.srefbundle", base[:-1])
    bundle(
        "undeclared-member.srefbundle",
        base + [member("recipes/extra.sref", minimal)],
    )
    bundle(
        "undeclared-root-entry.srefbundle",
        base + [member("notes.txt", b"a bundle carries recipes and nothing else\n")],
    )

    # Same length, different bytes: only the digest can catch this.
    midpoint = len(with_asset) // 2
    tampered = (
        with_asset[:midpoint]
        + bytes([with_asset[midpoint] ^ 1])
        + with_asset[midpoint + 1 :]
    )
    bundle(
        "member-digest-mismatch.srefbundle",
        [base[0], member("recipes/1r00001.sref", tampered), base[2]],
    )
    bundle(
        "member-size-mismatch.srefbundle",
        [base[0], member("recipes/1r00001.sref", with_asset + b"\n"), base[2]],
    )

    same_recipe_twice = [
        ("r000001", "minimal", minimal),
        ("r000002", "minimal", minimal_package("Another Minimal Recipe")),
    ]
    bundle(
        "duplicate-recipe-id.srefbundle",
        [member("manifest.json", bundle_manifest(same_recipe_twice))]
        + [
            member(f"recipes/{member_id}.sref", data)
            for member_id, _recipe_id, data in same_recipe_twice
        ],
    )

    missing_member_id = copy.deepcopy(json.loads(manifest))
    del missing_member_id["recipes"][0]["member_id"]
    bundle(
        "missing-member-id.srefbundle",
        [member("manifest.json", compact_json(missing_member_id)), *base[1:]],
    )

    duplicated = copy.deepcopy(json.loads(manifest))
    duplicated["recipes"].append(copy.deepcopy(duplicated["recipes"][0]))
    bundle(
        "duplicate-member-id.srefbundle",
        [member("manifest.json", compact_json(duplicated)), *base[1:]],
    )

    # The member is present and verifies; its path simply is not derived from
    # its bundle-local member identity.
    renamed = copy.deepcopy(json.loads(manifest))
    renamed["recipes"][1]["path"] = "recipes/application-name.sref"
    bundle(
        "member-path-mismatch.srefbundle",
        [
            member("manifest.json", compact_json(renamed)),
            base[1],
            member("recipes/application-name.sref", minimal),
        ],
    )

    # The member is a genuine package; it just carries a different recipe than
    # the bundle manifest says it does.
    relabelled = bundle_manifest(
        [
            ("1r00001", "3f2504e0-4f89-41d3-9a0c-0305e82c3301", with_asset),
            ("r000002", "minimal", with_asset),
        ]
    )
    bundle(
        "recipe-id-disagreement.srefbundle",
        [
            member("manifest.json", relabelled),
            base[1],
            member("recipes/r000002.sref", with_asset),
        ],
    )

    # A member whose digest is right and whose package is broken: verifying the
    # bundle is not the same as validating what it carries.
    broken = (DESTINATION / "missing-asset.sref").read_bytes()
    broken_manifest = bundle_manifest(
        [("1r00001", "3f2504e0-4f89-41d3-9a0c-0305e82c3301", broken)]
    )
    bundle(
        "invalid-member-package.srefbundle",
        [
            member("manifest.json", broken_manifest),
            member("recipes/1r00001.sref", broken),
        ],
    )

    empty = compact_json({"format": "sref-bundle", "version": 1, "recipes": []})
    bundle("empty-bundle.srefbundle", [member("manifest.json", empty)])

    stamped = copy.deepcopy(json.loads(manifest))
    stamped["generated_at"] = "2026-08-27T00:00:00Z"
    bundle(
        "bundle-manifest-timestamp.srefbundle",
        [member("manifest.json", compact_json(stamped)), *base[1:]],
    )

    bundle("missing-bundle-manifest.srefbundle", base[1:])
    bundle(
        "unsafe-member-path.srefbundle",
        base + [member("../escape.sref", minimal)],
    )
    (BUNDLE_DESTINATION / "not-a-zip.srefbundle").write_bytes(
        b"This is not a ZIP archive.\n"
    )


def build_writer_refusal_fixtures() -> None:
    """A package and a bundle a writer must refuse to emit.

    The other archive fixtures are invalid as archives, which a writer
    recomputes and so cannot break; these ask a writer to refuse.

    The package fixture is indexed for the reader and writer in one case because
    both report the underlying `unknown-unit` requirement. The bundle fixture
    has separate reader and writer cases. Both report the normative
    `unknown-unit` category, but a reader reports that the bundle has an invalid
    member package while a writer, which is handed recipes rather than member
    packages, reports the underlying `unknown-unit` requirement. Keeping those
    snapshot-scoped requirement IDs separate is the distinction the two-level
    failure contract was designed to express.

    These fixtures name a unit that is not in the registry the document
    declares. A reader must refuse to load them and a writer must refuse to
    produce them.
    """
    recipe = (ROOT / "tests" / "invalid" / "unknown-unit.recipe.json").read_bytes()
    manifest = compact_json(
        {
            "sref_package": {"version": "0.1.0"},
            "recipe": {
                "path": "recipe.json",
                "media_type": "application/json",
                "sha256": hashlib.sha256(recipe).hexdigest(),
                "size": len(recipe),
            },
            "assets": [],
        }
    )
    entries = [entry("recipe.json", recipe), entry("manifest.json", manifest)]
    write_package("unknown-unit.sref", entries)

    members = [("r000001", "unknown-unit", package_bytes(entries))]
    bundle_entries = [member("manifest.json", bundle_manifest(members))] + [
        member(f"recipes/{member_id}.sref", data)
        for member_id, _recipe_id, data in members
    ]
    write_archive(BUNDLE_DESTINATION / "unknown-unit-member.srefbundle", bundle_entries)
    write_archive(BUNDLE_DESTINATION / "unknown-unit-writer.srefbundle", bundle_entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed archive fixtures differ from a clean rebuild",
    )
    arguments = parser.parse_args()

    if not arguments.check:
        build_fixtures()
        build_manifest_schema_fixtures()
        build_bundle_fixtures()
        build_writer_refusal_fixtures()
        build_multi_member_bundle()
        build_translation_bundle()
        return

    global DESTINATION, BUNDLE_DESTINATION
    committed_packages = DESTINATION
    committed_bundles = BUNDLE_DESTINATION
    with tempfile.TemporaryDirectory(prefix="sref-archive-fixtures-") as temporary:
        DESTINATION = Path(temporary) / "packages"
        BUNDLE_DESTINATION = Path(temporary) / "bundles"
        DESTINATION.mkdir(parents=True)
        BUNDLE_DESTINATION.mkdir(parents=True)
        build_fixtures()
        build_manifest_schema_fixtures()
        # Bundles carry packages, so they are built from the packages that were
        # just rebuilt rather than from the committed ones.
        build_bundle_fixtures()
        build_writer_refusal_fixtures()
        build_multi_member_bundle()
        build_translation_bundle()
        compare("package", DESTINATION, committed_packages, "*.sref")
        compare("bundle", BUNDLE_DESTINATION, committed_bundles, "*.srefbundle")


def compare(kind: str, built: Path, committed: Path, pattern: str) -> None:
    built_names = {path.name for path in built.glob(pattern)}
    committed_names = {path.name for path in committed.glob(pattern)}
    if built_names != committed_names:
        missing = sorted(built_names - committed_names)
        extra = sorted(committed_names - built_names)
        raise SystemExit(f"{kind} fixture set differs; missing={missing}, extra={extra}")
    changed = [
        name
        for name in sorted(built_names)
        if (built / name).read_bytes() != (committed / name).read_bytes()
    ]
    if changed:
        raise SystemExit(f"{kind} fixtures require rebuilding: {changed}")


if __name__ == "__main__":
    main()
