#!/usr/bin/env python3
"""Tests for the conformance runner and the semantic comparison it uses.

Scripted adapters cover every way an adapter can behave, including answering
with nonsense, exiting nonzero, or refusing for a plausible but wrong reason.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_archive_fixtures as fixtures
import semantics
from runner import Adapter, AdapterError, declaration, run

ROOT = pathlib.Path(__file__).resolve().parent.parent

MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "accepts-valid",
            "capabilities": ["json-reader"],
            "fixture": "tests/valid/minimal.recipe.json",
            "expected": "valid",
        },
        {
            "id": "rejects-invalid",
            "capabilities": ["json-reader"],
            "fixture": "tests/invalid/duplicate-step-id.recipe.json",
            "expected": "invalid",
            "error_category": "invalid-artifact",
            "requirement_id": "duplicate-step-id",
        },
    ],
}

#: A manifest with one writer case, for the artifact checks. A writer case is a
#: valid fixture: the question is whether the implementation can produce it.
WRITER_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "writes-valid",
            "capabilities": ["json-writer"],
            "fixture": "tests/valid/minimal.recipe.json",
            "expected": "valid",
        },
    ],
}

MULTI_CAPABILITY_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "reads-and-writes",
            "capabilities": ["json-reader", "json-writer"],
            "fixture": "tests/valid/minimal.recipe.json",
            "expected": "valid",
        },
    ],
}

#: A writer case the implementation has to refuse. The fixture is a request,
#: not a document to read: a writer asked for a recipe naming a unit its own
#: registry does not have must decline to produce one.
WRITER_REFUSAL_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "refuses-unknown-unit",
            "capabilities": ["json-writer"],
            "fixture": "tests/invalid/unknown-unit.recipe.json",
            "expected": "invalid",
            "validation": "semantic",
            "error_category": "unknown-unit",
            "requirement_id": "unknown-unit",
        },
    ],
}

#: The asset-free package, whose manifest still has to carry `assets: []`.
ASSET_FREE_PACKAGE_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "writes-an-asset-free-package",
            "capabilities": ["package-writer"],
            "fixture": "tests/packages/valid-no-assets.sref",
            "expected": "valid",
        },
    ],
}

PACKAGE_WRITER_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "writes-a-package",
            "capabilities": ["package-writer"],
            "fixture": "tests/packages/valid-with-asset.sref",
            "expected": "valid",
        },
    ],
}

BUNDLE_WRITER_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "writes-a-bundle",
            "capabilities": ["bundle-writer"],
            "fixture": "tests/bundles/valid.srefbundle",
            "expected": "valid",
        },
    ],
}


RESOLUTION_MANIFEST = {
    "sref_version": "0.1.0",
    "unit_registry_version": "0.1.0",
    "cases": [
        {
            "id": "resolves-measures",
            "capabilities": ["unit-resolution"],
            "fixture": "tests/resolution/unit-resolution.json",
            "expected": "valid",
        },
    ],
}


def scripted(body: str) -> list[str]:
    """A one-off adapter whose whole behaviour is the script it is given."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    with handle:
        handle.write(body)
    return [sys.executable, handle.name]


DECLARES = """
import json, sys
if sys.argv[1] == "capabilities":
    print(json.dumps({"implementation": "scripted", "version": "0",
                      "sref_version": "0.1.0", "unit_registry_version": "0.1.0",
                      "capabilities": %s}))
else:
    print(json.dumps(%s))
"""


def adapter_for(answer: dict, capabilities: list[str] | None = None) -> Adapter:
    command = scripted(DECLARES % (json.dumps(capabilities or ["json-reader"]), json.dumps(answer)))
    adapter = Adapter(command=command)
    adapter.describe()
    return adapter


#: `DECLARES` embeds its answer as a Python literal, which cannot carry the
#: JSON `null` a resolution answer uses for a measure that must stay
#: unresolved. This one carries the answer as JSON text and parses it, so an
#: adapter can say what the specification requires it to be able to say.
ANSWERS = """
import json, sys
if sys.argv[1] == "capabilities":
    print(json.dumps({"implementation": "scripted", "version": "0",
                      "sref_version": "0.1.0", "unit_registry_version": "0.1.0",
                      "capabilities": %s}))
else:
    print(json.dumps(json.loads(%s)))
"""


def answering(answer: dict, capabilities: list[str]) -> Adapter:
    command = scripted(
        ANSWERS % (json.dumps(capabilities), repr(json.dumps(answer)))
    )
    adapter = Adapter(command=command)
    adapter.describe()
    return adapter


class Declaration(unittest.TestCase):
    def test_an_adapter_without_a_version_is_refused(self):
        adapter = Adapter(command=scripted(
            'import json,sys; print(json.dumps({"implementation": "x", "capabilities": []}))'
        ))
        with self.assertRaises(AdapterError):
            adapter.describe()

    def test_an_unknown_capability_is_refused(self):
        adapter = Adapter(command=scripted(DECLARES % (json.dumps(["telepathy"]), "{}")))
        with self.assertRaises(AdapterError):
            adapter.describe()

    def test_a_nonzero_exit_is_an_adapter_failure_not_a_rejection(self):
        # A crash is not a rejection.
        adapter = Adapter(command=scripted("import sys; sys.exit(3)"))
        with self.assertRaises(AdapterError):
            adapter.describe()


class Outcomes(unittest.TestCase):
    def _run(self, answer: dict, capabilities: list[str] | None = None):
        return run(adapter_for(answer, capabilities), MANIFEST)

    def test_accepting_a_valid_fixture_and_rejecting_an_invalid_one_passes(self):
        # The scripted adapter answers the same way twice, so exactly one of
        # the two cases can pass at a time; this checks the accepting half.
        results = self._run({"outcome": "accepted"})
        self.assertEqual(results[0].outcome, "pass")
        self.assertEqual(results[1].outcome, "wrong-verdict")

    def test_rejecting_for_the_declared_reason_passes(self):
        results = self._run({
            "outcome": "rejected",
            "error_category": "invalid-artifact",
            "requirement_id": "duplicate-step-id",
        })
        self.assertEqual(results[1].outcome, "pass")
        self.assertTrue(results[1].confirmed)

    def test_rejecting_under_another_category_is_reported_separately(self):
        results = self._run({
            "outcome": "rejected",
            "error_category": "unsafe-archive",
            "requirement_id": "duplicate-step-id",
        })
        self.assertEqual(results[1].outcome, "wrong-category")
        self.assertIn("unsafe-archive", results[1].detail)

    def test_the_right_category_for_another_requirement_is_a_wrong_requirement(self):
        results = self._run({
            "outcome": "rejected",
            "error_category": "invalid-artifact",
            "requirement_id": "duplicate-asset-id",
        })
        self.assertEqual(results[1].outcome, "wrong-requirement")
        self.assertIn("duplicate-asset-id", results[1].detail)

    def test_a_rejection_naming_no_requirement_passes_unconfirmed(self):
        # `requirement_id` is optional (section 22.1).
        results = self._run({"outcome": "rejected", "error_category": "invalid-artifact"})
        self.assertEqual(results[1].outcome, "pass")
        self.assertFalse(results[1].confirmed)

    def test_a_rejection_naming_no_category_blames_the_adapter(self):
        # The category is required of a refusal.
        results = self._run({"outcome": "rejected"})
        self.assertEqual(results[1].outcome, "adapter-error")

    def test_a_category_outside_the_normative_set_blames_the_adapter(self):
        results = self._run({"outcome": "rejected", "error_category": "invalid-quantity"})
        self.assertEqual(results[1].outcome, "adapter-error")
        self.assertIn("invalid-quantity", results[1].detail)

    def test_an_undeclared_capability_is_unsupported_rather_than_failed(self):
        results = self._run({"outcome": "accepted"}, capabilities=["bundle-writer"])
        self.assertEqual([result.outcome for result in results], ["unsupported", "unsupported"])

    def test_an_unparseable_answer_blames_the_adapter(self):
        adapter = Adapter(command=scripted(
            'import json,sys\n'
            'print(json.dumps({"implementation":"x","version":"0","sref_version":"0.1.0",'
            '"unit_registry_version":"0.1.0","capabilities":["json-reader"]})'
            ') if sys.argv[1]=="capabilities" else print("not json")'
        ))
        adapter.describe()
        results = run(adapter, MANIFEST)
        self.assertEqual(results[0].outcome, "adapter-error")


class Declarations(unittest.TestCase):
    def test_a_capability_is_demonstrated_only_when_every_case_passed(self):
        adapter = adapter_for({"outcome": "accepted"})
        results = run(adapter, MANIFEST)
        claim = declaration(adapter, MANIFEST, results)
        self.assertEqual(claim["capabilities_claimed"], ["json-reader"])
        self.assertEqual(claim["capabilities_demonstrated"], [])

    def test_a_refusal_that_named_its_requirement_is_counted_apart(self):
        confirmed = adapter_for({
            "outcome": "rejected",
            "error_category": "invalid-artifact",
            "requirement_id": "duplicate-step-id",
        })
        claim = declaration(confirmed, MANIFEST, run(confirmed, MANIFEST))
        self.assertEqual(claim["requirements"], {"confirmed": 1, "unconfirmed": 0})

        vague = adapter_for({"outcome": "rejected", "error_category": "invalid-artifact"})
        claim = declaration(vague, MANIFEST, run(vague, MANIFEST))
        self.assertEqual(claim["requirements"], {"confirmed": 0, "unconfirmed": 1})

    def test_the_version_is_the_corpus_and_not_the_adapter_aspiration(self):
        adapter = adapter_for({"outcome": "accepted"})
        adapter.declaration["sref_version"] = "9.9.9"
        claim = declaration(adapter, MANIFEST, [])
        self.assertEqual(claim["sref_version"], "0.1.0")


class CapabilitySelection(unittest.TestCase):
    def test_a_capability_filter_does_not_run_another_capability_on_the_same_case(self):
        adapter = adapter_for(
            {"outcome": "accepted"},
            ["json-reader", "json-writer"],
        )
        results = run(adapter, MULTI_CAPABILITY_MANIFEST, only={"json-reader"})
        self.assertEqual([result.capability for result in results], ["json-reader"])


class Semantics(unittest.TestCase):
    def test_member_order_is_not_meaning(self):
        self.assertTrue(semantics.equivalent({"a": 1, "b": 2}, {"b": 2, "a": 1}))

    def test_array_order_is_meaning(self):
        self.assertFalse(semantics.equivalent({"a": [1, 2]}, {"a": [2, 1]}))

    def test_an_omitted_default_equals_an_explicit_one(self):
        self.assertTrue(semantics.equivalent({"approximate": False}, {}))
        self.assertTrue(semantics.equivalent({"optional": False}, {}))

    def test_an_authored_true_is_not_a_default(self):
        self.assertFalse(semantics.equivalent({"optional": True}, {}))

    def test_a_number_is_not_its_string_spelling(self):
        # An unknown member holding 4 and one holding "4" are different
        # documents, and a reader may not decide they are not.
        self.assertFalse(semantics.equivalent({"a": 4}, {"a": "4"}))

    def test_an_exact_rational_that_became_a_decimal_is_a_difference(self):
        self.assertFalse(semantics.equivalent({"value": "9/4"}, {"value": 2.25}))

    def test_a_difference_names_the_member_that_changed(self):
        detail = semantics.difference({"a": {"b": [1, 2]}}, {"a": {"b": [1, 3]}})
        self.assertEqual(detail, "a.b[1]: 2 became 3")

    def test_a_lost_member_is_reported_as_lost(self):
        self.assertIn("lost", semantics.difference({"a": 1, "b": 2}, {"a": 1}))


class Resolutions(unittest.TestCase):
    """Resolution submits a decision context and compares the identities that
    come back, including occurrences that must stay unresolved.
    """

    def corpus(self):
        return json.loads(
            (ROOT / "tests" / "resolution" / "unit-resolution.json").read_text(encoding="utf-8")
        )

    def answering(self, resolutions):
        return answering(
            {"outcome": "accepted", "resolutions": resolutions}, ["unit-resolution"]
        )

    def test_matching_every_vector_passes(self):
        expected = {case["id"]: case["expected"] for case in self.corpus()["cases"]}
        results = run(self.answering(expected), RESOLUTION_MANIFEST)
        self.assertEqual([result.outcome for result in results], ["pass"])

    def test_inventing_a_convention_fails(self):
        # The vector supplies no decision at all, so a teaspoon that comes back
        # with an identity has been guessed rather than resolved.
        expected = {case["id"]: case["expected"] for case in self.corpus()["cases"]}
        expected["compound-sum-no-decision"] = {
            "outcome": "resolved",
            "units": {
                "spoon-large": "volume.tablespoon.us.customary",
                "spoon-small": "volume.teaspoon.us.customary",
            },
        }
        results = run(self.answering(expected), RESOLUTION_MANIFEST)
        self.assertEqual(results[0].outcome, "wrong-resolution")
        self.assertIn("compound-sum-no-decision", results[0].detail)

    def test_settling_a_conflict_fails(self):
        expected = {case["id"]: case["expected"] for case in self.corpus()["cases"]}
        expected["conflicting-ingredient-conventions"] = {
            "outcome": "resolved",
            "units": {"cup": "volume.cup.us.customary"},
        }
        results = run(self.answering(expected), RESOLUTION_MANIFEST)
        self.assertEqual(results[0].outcome, "wrong-resolution")

    def test_an_unanswered_vector_fails(self):
        expected = {case["id"]: case["expected"] for case in self.corpus()["cases"]}
        removed = expected.pop("compound-sum-ingredient-convention")
        self.assertIsNotNone(removed)
        results = run(self.answering(expected), RESOLUTION_MANIFEST)
        self.assertEqual(results[0].outcome, "wrong-resolution")
        self.assertIn("no answer", results[0].detail)

    def test_an_answer_without_resolutions_is_an_adapter_defect(self):
        adapter = answering({"outcome": "accepted"}, ["unit-resolution"])
        results = run(adapter, RESOLUTION_MANIFEST)
        self.assertEqual(results[0].outcome, "adapter-error")

    def test_an_implementation_may_decline_the_capability(self):
        adapter = answering(
            {"outcome": "unsupported", "detail": "no resolution context accepted"},
            ["unit-resolution"],
        )
        results = run(adapter, RESOLUTION_MANIFEST)
        self.assertEqual(results[0].outcome, "unsupported")


class AgainstTheRealCorpus(unittest.TestCase):
    """The runner has to work on the corpus it ships with, not only on scripts."""

    def test_a_do_nothing_adapter_reports_every_case_as_unsupported(self):
        manifest = json.loads((ROOT / "conformance" / "manifest.json").read_text(encoding="utf-8"))
        adapter = Adapter(command=scripted(DECLARES % (json.dumps([]), "{}")))
        adapter.describe()
        results = run(adapter, manifest)
        self.assertEqual(len(results), len(manifest["cases"]))
        self.assertTrue(all(result.outcome == "unsupported" for result in results))


class EmittedArtifacts(unittest.TestCase):
    """A returned writer artifact is validated independently of the adapter."""

    def _run(self, answer: dict):
        adapter = adapter_for(answer, ["json-writer"])
        return run(adapter, WRITER_MANIFEST)

    def valid_document(self) -> str:
        return (ROOT / "tests/valid/minimal.recipe.json").read_text(encoding="utf-8")

    def test_an_artifact_the_corpus_accepts_passes(self):
        results = self._run({"outcome": "accepted", "artifact": self.valid_document()})
        self.assertEqual([result.outcome for result in results], ["pass"])

    def test_an_artifact_the_corpus_rejects_fails_however_the_adapter_answered(self):
        document = json.loads(self.valid_document())
        document["id"] = "INVALID ID"
        results = self._run({"outcome": "accepted", "artifact": json.dumps(document)})
        self.assertEqual([result.outcome for result in results], ["wrote-invalid"])

    def test_an_adapter_returning_no_artifact_still_passes_but_is_recorded(self):
        # Passes, but the declaration lists the capability as unwitnessed.
        adapter = adapter_for({"outcome": "accepted"}, ["json-writer"])
        results = run(adapter, WRITER_MANIFEST)
        self.assertEqual([result.outcome for result in results], ["pass"])
        self.assertEqual(
            declaration(adapter, WRITER_MANIFEST, results)["capabilities_unwitnessed"],
            ["json-writer"],
        )

    def test_one_adapter_run_cannot_mark_another_as_unwitnessed(self):
        first = adapter_for({"outcome": "accepted"}, ["json-writer"])
        first_results = run(first, WRITER_MANIFEST)

        second = adapter_for(
            {"outcome": "accepted", "artifact": self.valid_document()},
            ["json-writer"],
        )
        second_results = run(second, WRITER_MANIFEST)

        self.assertEqual(
            declaration(first, WRITER_MANIFEST, first_results)["capabilities_unwitnessed"],
            ["json-writer"],
        )
        self.assertEqual(
            declaration(second, WRITER_MANIFEST, second_results)["capabilities_unwitnessed"],
            [],
        )

    def test_an_artifact_that_does_not_decode_blames_the_adapter(self):
        results = self._run(
            {"outcome": "accepted", "artifact": "not base64", "artifact_encoding": "base64"}
        )
        self.assertEqual([result.outcome for result in results], ["adapter-error"])

    def test_an_unknown_artifact_encoding_blames_the_adapter(self):
        results = self._run(
            {"outcome": "accepted", "artifact": "x", "artifact_encoding": "rot13"}
        )
        self.assertEqual([result.outcome for result in results], ["adapter-error"])


class WriterRefusals(unittest.TestCase):
    """A writer case can require a refusal, and the refusal is checked."""

    def _run(self, answer: dict):
        return run(adapter_for(answer, ["json-writer"]), WRITER_REFUSAL_MANIFEST)

    def test_writing_what_the_case_forbids_is_a_wrong_verdict(self):
        results = self._run({"outcome": "accepted"})
        self.assertEqual([result.outcome for result in results], ["wrong-verdict"])

    def test_refusing_for_the_declared_reason_passes(self):
        results = self._run({
            "outcome": "rejected",
            "error_category": "unknown-unit",
            "requirement_id": "unknown-unit",
        })
        self.assertEqual([result.outcome for result in results], ["pass"])

    def test_refusing_under_another_category_is_reported_separately(self):
        results = self._run({
            "outcome": "rejected",
            "error_category": "invalid-artifact",
            "requirement_id": "unknown-unit",
        })
        self.assertEqual([result.outcome for result in results], ["wrong-category"])
        self.assertEqual(results[0].expected, "unknown-unit")
        self.assertEqual(results[0].requirement, "unknown-unit")

    def test_an_adapter_that_cannot_answer_fails_as_an_adapter(self):
        # A crash is not a refusal.
        adapter = Adapter(command=scripted(
            'import json,sys\n'
            'print(json.dumps({"implementation":"x","version":"0","sref_version":"0.1.0",'
            '"unit_registry_version":"0.1.0","capabilities":["json-writer"]})'
            ') if sys.argv[1]=="capabilities" else sys.exit(4)'
        ))
        adapter.describe()
        results = run(adapter, WRITER_REFUSAL_MANIFEST)
        self.assertEqual([result.outcome for result in results], ["adapter-error"])

    def test_a_capability_with_no_executed_case_is_not_demonstrated(self):
        # No bundle case ran, so the claimed capability is not demonstrated.
        adapter = adapter_for(
            {
                "outcome": "rejected",
                "error_category": "unknown-unit",
                "requirement_id": "unknown-unit",
            },
            ["json-writer", "bundle-writer"],
        )
        results = run(adapter, WRITER_REFUSAL_MANIFEST)
        claim = declaration(adapter, WRITER_REFUSAL_MANIFEST, results)
        self.assertEqual(claim["capabilities_demonstrated"], ["json-writer"])
        self.assertEqual(claim["capabilities_unexercised"], ["bundle-writer"])


def repackage(source: bytes, change) -> bytes:
    """Rebuild a package fixture with one part of it altered.

    `change` is handed the recipe document, the manifest document and the
    archive's other files, and edits them in place, producing output that is
    valid but not what was asked for.
    """
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        recipe = json.loads(archive.read("recipe.json"))
        manifest = json.loads(archive.read("manifest.json"))
        files = {
            name: archive.read(name)
            for name in archive.namelist()
            if name not in ("recipe.json", "manifest.json")
        }
    change(recipe, manifest, files)
    recipe_bytes = fixtures.compact_json(recipe)
    manifest["recipe"]["sha256"] = hashlib.sha256(recipe_bytes).hexdigest()
    manifest["recipe"]["size"] = len(recipe_bytes)
    return fixtures.package_bytes(
        [
            fixtures.entry("recipe.json", recipe_bytes),
            fixtures.entry("manifest.json", fixtures.compact_json(manifest)),
        ]
        + [fixtures.entry(name, data) for name, data in files.items()]
    )


class EmittedPackages(unittest.TestCase):
    """Controls for the package half of the artifact check: adapters reporting
    success while handing over something the corpus must refuse.
    """

    def request(self) -> bytes:
        return (ROOT / "tests/packages/valid-with-asset.sref").read_bytes()

    def _run(self, artifact: bytes, manifest=PACKAGE_WRITER_MANIFEST):
        adapter = adapter_for(
            {
                "outcome": "accepted",
                "artifact": base64.b64encode(artifact).decode("ascii"),
                "artifact_encoding": "base64",
            },
            ["package-writer"],
        )
        return run(adapter, manifest)

    def test_the_package_it_was_asked_for_passes(self):
        results = self._run(self.request())
        self.assertEqual([result.outcome for result in results], ["pass"])

    def test_an_asset_free_package_without_the_assets_member_is_invalid(self):
        # A manifest missing its required `assets` array.
        recipe = (ROOT / "tests/valid/minimal.recipe.json").read_bytes()
        manifest = {
            "sref_package": {"version": "0.1.0"},
            "recipe": {
                "path": "recipe.json",
                "media_type": "application/json",
                "sha256": hashlib.sha256(recipe).hexdigest(),
                "size": len(recipe),
            },
        }
        artifact = fixtures.package_bytes([
            fixtures.entry("recipe.json", recipe),
            fixtures.entry("manifest.json", fixtures.compact_json(manifest)),
        ])
        results = self._run(artifact, ASSET_FREE_PACKAGE_MANIFEST)
        self.assertEqual([result.outcome for result in results], ["wrote-invalid"])
        self.assertIn("assets", results[0].detail)

    def test_a_package_stamped_with_another_version_is_invalid(self):
        artifact = repackage(
            self.request(),
            lambda recipe, manifest, files: manifest["sref_package"].update(version="9.9.9"),
        )
        results = self._run(artifact)
        self.assertEqual([result.outcome for result in results], ["wrote-invalid"])

    def test_a_valid_package_saying_something_else_is_lossy(self):
        # Valid, but not what was asked for.
        artifact = repackage(
            self.request(),
            lambda recipe, manifest, files: recipe.update(title="Something Else"),
        )
        results = self._run(artifact)
        self.assertEqual([result.outcome for result in results], ["lossy"])
        self.assertIn("title", results[0].detail)

    def test_an_asset_returned_as_different_bytes_is_lossy(self):
        def replace(recipe, manifest, files):
            data = files["assets/source.txt"]
            altered = bytes([data[0] ^ 1]) + data[1:]
            files["assets/source.txt"] = altered
            digest = hashlib.sha256(altered).hexdigest()
            for table in (recipe["assets"], manifest["assets"]):
                for asset in table:
                    if asset["path"] == "assets/source.txt":
                        asset["sha256"] = digest

        results = self._run(repackage(self.request(), replace))
        self.assertEqual([result.outcome for result in results], ["lossy"])
        self.assertIn("5source-note", results[0].detail)

    def test_a_dropped_asset_is_lossy(self):
        def drop(recipe, manifest, files):
            files.pop("assets/source.txt")
            recipe["assets"] = [a for a in recipe["assets"] if a["id"] != "5source-note"]
            manifest["assets"] = [a for a in manifest["assets"] if a["id"] != "5source-note"]
            recipe["image_refs"] = [r for r in recipe.get("image_refs", []) if r != "5source-note"]
            for section in recipe.get("instruction_sections", []):
                for step in section.get("steps", []):
                    step["image_refs"] = [
                        ref for ref in step.get("image_refs", []) if ref != "5source-note"
                    ]
                    if not step["image_refs"]:
                        step.pop("image_refs")

        results = self._run(repackage(self.request(), drop))
        self.assertEqual([result.outcome for result in results], ["lossy"])
        self.assertIn("5source-note", results[0].detail)


class EmittedBundles(unittest.TestCase):
    def request(self) -> bytes:
        return (ROOT / "tests/bundles/valid.srefbundle").read_bytes()

    def _run(self, artifact: bytes):
        adapter = adapter_for(
            {
                "outcome": "accepted",
                "artifact": base64.b64encode(artifact).decode("ascii"),
                "artifact_encoding": "base64",
            },
            ["bundle-writer"],
        )
        return run(adapter, BUNDLE_WRITER_MANIFEST)

    def test_the_bundle_it_was_asked_for_passes(self):
        self.assertEqual([r.outcome for r in self._run(self.request())], ["pass"])

    def test_a_reordered_bundle_is_lossy(self):
        # Reordered members: every digest still matches.
        with zipfile.ZipFile(io.BytesIO(self.request())) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            members = {
                name: archive.read(name)
                for name in archive.namelist()
                if name != "manifest.json"
            }
        manifest["recipes"].reverse()
        artifact = fixtures.package_bytes(
            [fixtures.entry("manifest.json", fixtures.compact_json(manifest))]
            + [fixtures.entry(name, data) for name, data in members.items()]
        )
        results = self._run(artifact)
        self.assertEqual([result.outcome for result in results], ["lossy"])
        self.assertIn("bundle members changed", results[0].detail)


if __name__ == "__main__":
    unittest.main()
