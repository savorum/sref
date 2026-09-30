#!/usr/bin/env python3
"""Deterministic adversarial tests for SREF's untrusted-input boundaries.

The committed conformance archives prove particular published error
categories. These tests serve a different purpose: generate hostile shapes at
runtime, turn large production limits down to cheap test-sized ceilings, and
prove that the canonical validator fails closed without giant binary fixtures.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import pathlib
import random
import stat
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import validate


ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def compact(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def entry(
    name: str,
    data: bytes,
    *,
    mode: int = stat.S_IFREG | 0o644,
    compression: int = zipfile.ZIP_STORED,
) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.create_system = 3
    info.external_attr = mode << 16
    info.compress_type = compression
    return info, data


def archive(entries: list[tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as destination:
        for info, data in entries:
            destination.writestr(info, data)
    return output.getvalue()


def package(
    recipe: dict | None = None,
    assets: list[tuple[str, str, bytes]] | None = None,
) -> bytes:
    document = copy.deepcopy(recipe or json.loads(
        (ROOT / "tests/valid/minimal.recipe.json").read_text(encoding="utf-8")
    ))
    declarations = []
    entries = []
    for asset_id, media_type, data in assets or []:
        path = f"assets/{asset_id}.bin"
        declaration = {
            "id": asset_id,
            "path": path,
            "media_type": media_type,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        declarations.append(declaration)
        entries.append(entry(path, data, compression=zipfile.ZIP_DEFLATED))
    if declarations:
        document["assets"] = declarations
    recipe_bytes = compact(document)
    manifest = {
        "sref_package": {"version": "0.1.0"},
        "recipe": {
            "path": "recipe.json",
            "media_type": "application/json",
            "sha256": hashlib.sha256(recipe_bytes).hexdigest(),
            "size": len(recipe_bytes),
        },
        "assets": declarations,
    }
    return archive([
        entry("recipe.json", recipe_bytes),
        entry("manifest.json", compact(manifest)),
        *entries,
    ])


def bundle(members: list[tuple[str, str, bytes]]) -> bytes:
    manifest = {
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
    return archive([
        entry("manifest.json", compact(manifest)),
        *(entry(f"recipes/{member_id}.sref", data) for member_id, _, data in members),
    ])


class ValidatorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recipe_validator = validate.validator("recipe.schema.json")
        cls.manifest_validator = validate.validator("manifest.schema.json")
        cls.bundle_validator = validate.validator("bundle-manifest.schema.json")
        registry = validate.load_json(ROOT / "registry/units.json")
        cls.units = {unit["id"]: unit for unit in registry["units"]}

    def package_errors(self, data: bytes) -> list[str]:
        return validate.validate_package_bytes(
            data, self.recipe_validator, self.manifest_validator, self.units
        )

    def bundle_errors(self, data: bytes) -> list[str]:
        with tempfile.NamedTemporaryFile(suffix=".srefbundle") as handle:
            handle.write(data)
            handle.flush()
            return validate.validate_bundle(
                pathlib.Path(handle.name),
                self.recipe_validator,
                self.manifest_validator,
                self.bundle_validator,
                self.units,
            )


class StrictJSON(ValidatorTestCase):
    def test_pathological_nesting_is_refused_before_the_recursive_parser(self):
        data = ("[" * (validate.MAX_JSON_DEPTH + 1) + "]" * (validate.MAX_JSON_DEPTH + 1)).encode()
        with self.assertRaisesRegex(validate.JSONDepthError, "depth limit"):
            validate.load_json_bytes(data)

    def test_brackets_and_escaped_quotes_inside_strings_do_not_spend_depth(self):
        value = '[{\\"still a string\\":[]}]' * 200
        self.assertEqual(validate.load_json_bytes(compact({"value": value})), {"value": value})

    def test_a_huge_integer_is_refused_before_arbitrary_precision_allocation(self):
        data = b"1" * (validate.MAX_JSON_NUMBER_CHARACTERS + 1)
        with self.assertRaisesRegex(validate.JSONNumberLimitError, "digit limit"):
            validate.load_json_bytes(data)

    def test_a_finite_looking_number_that_overflows_binary_float_is_refused(self):
        with self.assertRaisesRegex(validate.NonFiniteNumberError, "nonfinite"):
            validate.load_json_bytes(b"1e1000000")

    def test_malformed_utf8_is_refused(self):
        with self.assertRaises(UnicodeDecodeError):
            validate.load_json_bytes(b'{"title":"\xff"}')

    def test_seeded_json_byte_fuzz_never_leaks_an_unexpected_exception(self):
        generator = random.Random(0x53524546)
        expected = (
            json.JSONDecodeError,
            UnicodeDecodeError,
            validate.DuplicateKeyError,
            validate.JSONDepthError,
            validate.JSONNumberLimitError,
            validate.NonFiniteNumberError,
        )
        for _ in range(500):
            data = generator.randbytes(generator.randrange(0, 257))
            try:
                validate.load_json_bytes(data)
            except expected:
                pass


class ArchivePreflight(ValidatorTestCase):
    def collision_errors(self, left: str, right: str) -> list[str]:
        return self.package_errors(archive([
            entry("recipe.json", b"{}"),
            entry("manifest.json", b"{}"),
            entry(left, b"one"),
            entry(right, b"two"),
        ]))

    def test_case_colliding_paths_are_duplicates(self):
        errors = self.collision_errors("assets/Photo.jpg", "assets/photo.jpg")
        self.assertTrue(any("duplicate archive entry" in error for error in errors), errors)

    def test_composed_and_decomposed_unicode_paths_are_duplicates(self):
        errors = self.collision_errors("assets/caf\u00e9.txt", "assets/cafe\u0301.txt")
        self.assertTrue(any("duplicate archive entry" in error for error in errors), errors)

    def test_path_attacks_are_refused_before_extraction(self):
        attacks = {
            "../escape": "unsafe path segment",
            "/absolute": "absolute path",
            "C:/drive": "drive-letter path",
            "assets\\backslash": "backslash in path",
            "assets//empty": "unsafe path segment",
            "assets/./dot": "unsafe path segment",
            "assets/control\x01": "control character in path",
        }
        for path, marker in attacks.items():
            with self.subTest(path=path):
                self.assertTrue(any(
                    marker in error
                    for error in validate.path_errors(path, "entry")
                ))

    def test_every_nonregular_unix_entry_type_is_refused(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFSOCK):
            with self.subTest(mode=mode):
                errors = self.package_errors(archive([
                    entry("recipe.json", b"{}"),
                    entry("manifest.json", b"{}"),
                    entry("assets/node", b"target", mode=mode | 0o600),
                ]))
                self.assertTrue(any("nonregular archive entry" in error for error in errors), errors)

    def test_paths_have_a_finite_length_policy(self):
        path = "assets/" + "a" * validate.MAX_PATH_LENGTH
        self.assertTrue(any("path exceeds length limit" in error for error in validate.path_errors(path, "entry")))


class ResourceCeilings(ValidatorTestCase):
    def test_every_package_archive_ceiling_is_reachable_with_small_inputs(self):
        data = archive([
            entry("recipe.json", b"{}"),
            entry("manifest.json", b"{}"),
            entry("assets/filler", b"0" * 256, compression=zipfile.ZIP_DEFLATED),
        ])
        probes = (
            ("MAX_PACKAGE_BYTES", 8, "compressed-byte limit"),
            ("MAX_ARCHIVE_ENTRIES", 2, "archive-entry limit"),
            ("MAX_EXPANDED_BYTES", 64, "expanded-byte limit"),
            ("MAX_ENTRY_BYTES", 64, "entry assets/filler exceeds byte limit"),
            ("MAX_COMPRESSION_RATIO", 2, "compression-ratio limit"),
        )
        for name, ceiling, marker in probes:
            with self.subTest(limit=name), mock.patch.object(validate, name, ceiling):
                errors = self.package_errors(data)
                self.assertTrue(any(marker in error for error in errors), errors)

    def test_every_outer_bundle_ceiling_is_reachable_with_small_inputs(self):
        data = archive([
            entry("manifest.json", b"{}"),
            entry("recipes/r000001.sref", b"0" * 256, compression=zipfile.ZIP_DEFLATED),
            entry("recipes/r000002.sref", b"0" * 256, compression=zipfile.ZIP_DEFLATED),
        ])
        probes = (
            ("MAX_BUNDLE_BYTES", 8, "compressed-byte limit"),
            ("MAX_BUNDLE_MEMBERS", 1, "member limit"),
            ("MAX_EXPANDED_BYTES", 64, "expanded-byte limit"),
            ("MAX_ENTRY_BYTES", 64, "entry recipes/r000001.sref exceeds byte limit"),
            ("MAX_COMPRESSION_RATIO", 2, "compression-ratio limit"),
        )
        for name, ceiling, marker in probes:
            with self.subTest(limit=name), mock.patch.object(validate, name, ceiling):
                errors = self.bundle_errors(data)
                self.assertTrue(any(marker in error for error in errors), errors)

    def test_package_and_bundle_manifests_have_a_byte_limit(self):
        oversized = b'{"padding":"' + b"x" * 128 + b'"}'
        package_bytes = archive([
            entry("recipe.json", b"{}"),
            entry("manifest.json", oversized),
        ])
        bundle_bytes = archive([entry("manifest.json", oversized)])
        with mock.patch.object(validate, "MAX_JSON_BYTES", 64):
            self.assertIn("manifest.json exceeds JSON byte limit", self.package_errors(package_bytes))
            self.assertIn("manifest.json exceeds JSON byte limit", self.bundle_errors(bundle_bytes))

    def test_a_compression_bomb_inside_a_bundle_member_is_checked_recursively(self):
        inner = package(assets=[("bomb", "application/octet-stream", b"0" * 4096)])
        outer = bundle([("r000001", "minimal", inner)])
        with mock.patch.object(validate, "MAX_COMPRESSION_RATIO", 5):
            errors = self.bundle_errors(outer)
        self.assertTrue(any(
            "bundle member r000001" in error and "compression-ratio limit" in error
            for error in errors
        ), errors)

    def test_seeded_archive_byte_fuzz_always_returns_a_diagnostic(self):
        generator = random.Random(0x5A4950)
        for _ in range(250):
            data = generator.randbytes(generator.randrange(0, 513))
            self.assertTrue(self.package_errors(data))
            self.assertTrue(self.bundle_errors(data))


class StructuralWork(ValidatorTestCase):
    def test_thousand_scale_recipe_collections_have_finite_schema_caps(self):
        schema = validate.load_json(ROOT / "schema/recipe.schema.json")
        probes = (
            (schema["properties"]["ingredient_sections"], 1000),
            (schema["properties"]["instruction_sections"], 1000),
            (schema["properties"]["assets"], 10000),
            (schema["$defs"]["ingredientSection"]["properties"]["ingredients"], 10000),
            (schema["$defs"]["instructionSection"]["properties"]["steps"], 10000),
        )
        for definition, expected in probes:
            with self.subTest(expected=expected):
                self.assertEqual(definition["maxItems"], expected)
                limit_validator = validate.Draft202012Validator(
                    {"type": "array", "maxItems": definition["maxItems"]}
                )
                errors = list(limit_validator.iter_errors([None] * (expected + 1)))
                self.assertTrue(any(error.validator == "maxItems" for error in errors))

    def test_rationals_are_bounded_before_fraction_construction(self):
        with self.assertRaisesRegex(ValueError, "unsigned 64-bit"):
            validate.rational(str(validate.UINT64_MAX + 1))

    def test_unit_conversion_cycles_remain_a_rejected_graph(self):
        registry = validate.load_json(ROOT / "tests/registry/conversion-cycle.json")
        errors = validate.registry_semantic_errors(registry)
        self.assertTrue(any("conversion cycle" in error for error in errors), errors)

    def test_misleading_asset_media_type_is_never_used_to_decode_content(self):
        # SREF requires content verification before unsafe decoding or
        # rendering. The format validator performs neither: it treats asset
        # bytes as opaque and verifies only their declared size and digest.
        hostile = b"<svg><script>not executed</script></svg>"
        errors = self.package_errors(package(assets=[("photo", "image/png", hostile)]))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
