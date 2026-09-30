#!/usr/bin/env python3
"""Regression tests for the external recipe-corpus consumer."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_recipe_corpus import CLASSIFICATIONS, canonical_concept_digest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "conformance" / "validate_recipe_corpus.py"
CONFIG = ROOT / "conformance" / "recipe-corpus.json"
SAMPLE = ROOT / "tests" / "valid" / "minimal.recipe.json"


class RecipeCorpusConsumerTests(unittest.TestCase):
    def make_corpus(
        self,
        missing: str | None = None,
        accidentally_lost: list[dict[str, object]] | None = None,
        evaluated_cases: list[str] | None = None,
    ) -> tuple[Path, Path]:
        workspace = Path(tempfile.mkdtemp(prefix="sref-recipe-corpus-"))
        self.addCleanup(shutil.rmtree, workspace, ignore_errors=True)
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        config["corpus"]["commit"] = "0" * 40
        config_path = workspace / "recipe-corpus.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        targets = workspace / config["corpus"]["targets_directory"]
        targets.mkdir(parents=True)
        for case in config["cases"]:
            if case["id"] != missing:
                shutil.copyfile(SAMPLE, targets / case["fixture"])
        losses = accidentally_lost or []
        case_ids = evaluated_cases or [case["id"] for case in config["cases"]]
        audit = config["loss_audit"]
        concepts: list[dict[str, str]] = []
        classifications = dict(audit["expected_classifications"])
        # Each verdict has one basis the consumer accepts, and the capability
        # must agree with the verdict, so the fixture builds them together.
        basis_for = {
            "exact": ("normative-representation-verified", "variants", "sref_input"),
            "semantics_unverified": ("normative-representation-present-but-unverified", "variants", "sref_input"),
            "misrepresented": ("normative-representation-contradicts-source", "step-temperatures", "sref_input"),
            "sref_unsupported": ("no-normative-representation-in-revision", "none", "sref_input"),
            "mapping_unverified": ("no-audit-detector-for-capability", "opaque-quantity", "sref_input"),
            "accidentally_lost": ("normative-representation-absent-from-target", "ingredient-optional", "sref_input"),
            "upstream_lost": ("absent-before-sref-boundary", "instruction-sections", "application_export"),
        }
        concept_index = 0
        for classification, count in classifications.items():
            basis, capability, boundary = basis_for[classification]
            for _ in range(count):
                concepts.append(
                    {
                        "case_id": case_ids[concept_index % len(case_ids)],
                        "concept_id": f"concept-{concept_index}",
                        "source_concept_id": f"concept-{concept_index}",
                        "feature": f"feature-{concept_index}",
                        "classification": classification,
                        "boundary": boundary,
                        "basis": basis,
                        "sref_capability": capability,
                    }
                )
                concept_index += 1
        representations: list[dict[str, object]] = []
        for case_id in case_ids:
            representations.append(
                {
                    "case_id": case_id,
                    "features": [
                        concept["feature"]
                        for concept in concepts
                        if concept["case_id"] == case_id
                    ],
                }
            )
        audit["full_corpus"] = {
            "expected_representation_count": len(case_ids),
            "expected_dispositions": {
                "evaluated": len(case_ids),
                "reference_only": 0,
                "non_executable": 0,
            },
            "expected_concept_count": len(concepts),
            "expected_input_boundaries": {
                "sref_input": sum(1 for item in concepts if item["boundary"] == "sref_input"),
                "application_export": sum(1 for item in concepts if item["boundary"] == "application_export"),
                "bridge_input": 0,
            },
            "expected_concepts_sha256": canonical_concept_digest(concepts),
        }
        # Every concept-level defect appears in the report's detailed list with
        # a linked issue, exactly as the generators emit it.
        def defects(classification: str) -> list[dict[str, object]]:
            return [
                {
                    "case_id": item["case_id"],
                    "concept_id": item["concept_id"],
                    "target": dict(audit["target"]),
                    "issue": "savorum/recipe-corpus#21",
                }
                for item in concepts
                if item["classification"] == classification
            ]

        if not losses:
            losses = defects("accidentally_lost")
        misrepresentations = defects("misrepresented")
        for key, items in (
            ("expected_accidental_losses", losses),
            ("expected_misrepresentations", misrepresentations),
        ):
            audit[key] = {
                "count": len(items),
                "issues": sorted({str(item["issue"]) for item in items if item.get("issue")}),
            }
        report = workspace / audit["report"]
        report.parent.mkdir(parents=True)
        report.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "counts": {"representations": len(representations)},
                    "representations": representations,
                    "accounting": {
                        "status": "full-corpus-audit-complete",
                        "basis": "Every indexed representation carries an explicit disposition.",
                    },
                    "fidelity": {
                        "basis": "Derived from the capability registry and the generated target.",
                        "classification_order": [
                            "exact",
                            "normalized",
                            "authored_only",
                            "intentionally_unsupported",
                            "accidentally_lost",
                        ],
                        "sref_verdict_order": list(CLASSIFICATIONS),
                        "current_targets": {
                            audit["target"]["kind"]: audit["target"]["version"]
                        },
                        "declared_slice": {
                            "targets": [
                                {
                                    **audit["target"],
                                    "required_case_ids": [
                                        case["id"] for case in config["cases"]
                                    ],
                                    "completed_case_ids": case_ids,
                                    "missing_case_ids": sorted(
                                        set(case["id"] for case in config["cases"])
                                        - set(case_ids)
                                    ),
                                    "undeclared_case_ids": [],
                                    "complete": len(case_ids) == len(config["cases"]),
                                }
                            ]
                        },
                        "by_target": {
                            f"{audit['target']['kind']}:{audit['target']['version']}": {
                                "cases": case_ids,
                                "classifications": classifications,
                                "concepts": concepts,
                                "features": {
                                    f"feature-{index}": 1
                                    for index in range(audit["expected_feature_count"])
                                },
                            }
                        },
                        "full_corpus": {
                            "targets": [
                                {
                                    **audit["target"],
                                    "case_dispositions": [
                                        {
                                            "case_id": case_id,
                                            "disposition": "evaluated",
                                            "target_fixture": "targets/" + next(
                                                case["fixture"]
                                                for case in config["cases"]
                                                if case["id"] == case_id
                                            ),
                                        }
                                        for case_id in case_ids
                                    ],
                                    "unevaluated_case_ids": [],
                                    "complete": True,
                                }
                            ]
                        },
                        "stale_evaluations": [],
                        "accidentally_lost": losses,
                        "misrepresented": misrepresentations,
                    },
                }
            ),
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "-c",
                "user.name=SREF test",
                "-c",
                "user.email=sref-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "test corpus",
            ],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        config["corpus"]["commit"] = commit
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return workspace, config_path

    def run_consumer(self, corpus: Path, config: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--corpus-root",
                str(corpus),
                "--config",
                str(config),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_derived_targets_from_external_corpus_path(self) -> None:
        corpus, config = self.make_corpus()
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 0, result.stderr)
        declared = json.loads(config.read_text(encoding="utf-8"))
        audit = declared["loss_audit"]
        count = len(declared["cases"])
        self.assertIn(f"validated {count} executable", result.stdout)
        self.assertIn(
            f"loss-audited {audit['full_corpus']['expected_concept_count']} concepts "
            f"across {count} representations and {audit['expected_feature_count']} features",
            result.stdout,
        )

    def test_rejects_missing_selected_target(self) -> None:
        corpus, config = self.make_corpus(missing="rc-000051")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("rc-000051: missing target", result.stderr)

    def test_rejects_missing_asset_referenced_by_a_derived_target(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        fixture = (
            corpus
            / configuration["corpus"]["targets_directory"]
            / configuration["cases"][0]["fixture"]
        )
        document = json.loads(fixture.read_text())
        document["assets"] = [
            {
                "id": "missing-image",
                "path": "assets/missing.jpg",
                "media_type": "image/jpeg",
                "sha256": "0" * 64,
                "size": 1,
                "role": "image",
            }
        ]
        fixture.write_text(json.dumps(document), encoding="utf-8")
        subprocess.run(["git", "-C", str(corpus), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(corpus),
                "-c",
                "user.name=SREF test",
                "-c",
                "user.email=sref-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "add missing asset reference",
            ],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(corpus), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        configuration["corpus"]["commit"] = commit
        config.write_text(json.dumps(configuration), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("asset missing-image: missing file", result.stderr)

    def test_rejects_checkout_at_an_unpinned_commit(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text(encoding="utf-8"))
        configuration["corpus"]["commit"] = "0" * 40
        config.write_text(json.dumps(configuration), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 2)
        self.assertIn("checkout is not at the pinned commit", result.stderr)

    def test_rejects_incomplete_declared_loss_audit(self) -> None:
        case_ids = [case["id"] for case in json.loads(CONFIG.read_text())["cases"]]
        corpus, config = self.make_corpus(evaluated_cases=case_ids[:-1])
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("completed_case_ids does not match configured cases", result.stderr)
        self.assertIn("declared slice has missing SREF evaluations", result.stderr)

    def test_rejects_silently_unevaluated_representation(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        dispositions = report["fidelity"]["full_corpus"]["targets"][0][
            "case_dispositions"
        ]
        dispositions.pop()
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("silently unevaluated cases", result.stderr)

    def test_rejects_non_executable_representation(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["full_corpus"]["targets"][0]["case_dispositions"][0][
            "disposition"
        ] = "non_executable"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("non-executable cases remain", result.stderr)

    def test_accepts_reference_only_case_with_concept_evaluation(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        disposition = report["fidelity"]["full_corpus"]["targets"][0][
            "case_dispositions"
        ][0]
        disposition["disposition"] = "reference_only"
        del disposition["target_fixture"]
        configuration["loss_audit"]["full_corpus"]["expected_dispositions"] = {
            "evaluated": len(configuration["cases"]) - 1,
            "reference_only": 1,
            "non_executable": 0,
        }
        config.write_text(json.dumps(configuration), encoding="utf-8")
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_changed_concept_when_aggregate_totals_still_match(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["by_target"][
            f"{configuration['loss_audit']['target']['kind']}:"
            f"{configuration['loss_audit']['target']['version']}"
        ]["concepts"][0]["concept_id"] = "substituted-concept"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("concept classifications changed", result.stderr)

    def test_rejects_changed_source_concept_mapping(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["by_target"][
            f"{configuration['loss_audit']['target']['kind']}:"
            f"{configuration['loss_audit']['target']['version']}"
        ]["concepts"][0]["source_concept_id"] = "substituted-source-concept"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("concept classifications changed", result.stderr)

    def test_rejects_upstream_loss_disguised_as_sref_classification(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        concept = report["fidelity"]["by_target"][
            f"{configuration['loss_audit']['target']['kind']}:"
            f"{configuration['loss_audit']['target']['version']}"
        ]["concepts"][0]
        concept["boundary"] = "application_export"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("disagrees with its evaluation boundary", result.stderr)

    # An audit limitation must never be reported as a limitation of SREF.
    def test_rejects_audit_limitation_reported_as_a_format_gap(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        concepts = report["fidelity"]["by_target"][
            f"{configuration['loss_audit']['target']['kind']}:"
            f"{configuration['loss_audit']['target']['version']}"
        ]["concepts"]
        concept = next(item for item in concepts if item["classification"] == "mapping_unverified")
        concept["classification"] = "sref_unsupported"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reports a format gap for a supported capability", result.stderr)

    def test_rejects_unverified_mapping_without_an_audit_limitation_basis(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        concepts = report["fidelity"]["by_target"][
            f"{configuration['loss_audit']['target']['kind']}:"
            f"{configuration['loss_audit']['target']['version']}"
        ]["concepts"]
        concept = next(item for item in concepts if item["classification"] == "mapping_unverified")
        concept["basis"] = "normative-representation-present"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("without an audit-limitation basis", result.stderr)

    def test_rejects_report_that_does_not_separate_accounting_from_fidelity(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        del report["accounting"]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not separate representation accounting from fidelity", result.stderr)

    def test_accepts_retained_superseded_evaluation_for_a_currently_audited_case(
        self,
    ) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["stale_evaluations"] = [
            {
                "case_id": configuration["cases"][0]["id"],
                "target_kind": "sref",
                "evaluated_version": "1" * 40,
                "current_version": configuration["loss_audit"]["target"]["version"],
            }
        ]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_case_whose_only_sref_evaluation_is_superseded(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["stale_evaluations"] = [
            {
                "case_id": "rc-999999",
                "target_kind": "sref",
                "evaluated_version": "1" * 40,
                "current_version": configuration["loss_audit"]["target"]["version"],
            }
        ]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "presents superseded SREF evaluations as current for: rc-999999",
            result.stderr,
        )

    def test_rejects_undeclared_accidental_loss(self) -> None:
        configuration = json.loads(CONFIG.read_text())
        target = configuration["loss_audit"]["target"]
        corpus, config = self.make_corpus(
            accidentally_lost=[
                {
                    "case_id": "rc-000043",
                    "target": target,
                    "concept_id": "lost-timer",
                    "feature": "multiple-timers",
                    "issue": "savorum/sref#999",
                }
            ]
        )
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("accidental SREF losses count does not match", result.stderr)

    def test_rejects_accidental_loss_tracked_by_an_unreviewed_issue(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["accidentally_lost"][0]["issue"] = "savorum/sref#999"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tracked by unreviewed issues: savorum/sref#999", result.stderr)

    def test_rejects_accidental_loss_without_a_linked_defect(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        del report["fidelity"]["accidentally_lost"][0]["issue"]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn("without a linked defect", result.stderr)

    def test_rejects_misrepresentation_tracked_by_an_unreviewed_issue(self) -> None:
        corpus, config = self.make_corpus()
        configuration = json.loads(config.read_text())
        report_path = corpus / configuration["loss_audit"]["report"]
        report = json.loads(report_path.read_text())
        report["fidelity"]["misrepresented"][0]["issue"] = "savorum/sref#999"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_consumer(corpus, config)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "SREF misrepresentations tracked by unreviewed issues: savorum/sref#999",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
