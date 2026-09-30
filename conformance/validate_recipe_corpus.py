#!/usr/bin/env python3
"""Validate and loss-audit the pinned SREF slice in recipe-corpus.

The corpus remains a separate repository.  This program consumes only the
derived SREF JSON documents and generated fidelity report named by
``recipe-corpus.json``; it never reads source recipes, observations, scans, or
application exports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate import (
    DuplicateKeyError,
    NonFiniteNumberError,
    ROOT,
    load_json,
    recipe_semantic_errors,
    validator,
)


CONFIG_PATH = ROOT / "conformance" / "recipe-corpus.json"
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
# SREF target verdicts, in the corpus's order. `mapping_unverified` records a
# limitation of the corpus audit rather than of the format, so it must never be
# read as a gap in SREF.
CLASSIFICATIONS = (
    "exact",
    "semantics_unverified",
    "misrepresented",
    "sref_unsupported",
    "mapping_unverified",
    "accidentally_lost",
    "upstream_lost",
)
# Defect verdicts, each with its detailed report list and expected-count key.
DEFECTS = (
    ("accidentally_lost", "expected_accidental_losses", "accidental SREF losses"),
    ("misrepresented", "expected_misrepresentations", "SREF misrepresentations"),
)
CASE_DISPOSITIONS = (
    "evaluated",
    "reference_only",
    "non_executable",
)
# Which transition a verdict evaluates.
INPUT_BOUNDARIES = (
    "sref_input",
    "application_export",
    "bridge_input",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=os.environ.get("SREF_RECIPE_CORPUS_ROOT", ROOT.parent / "recipe-corpus"),
        help=(
            "checkout of the recipe-corpus commit pinned by conformance/recipe-corpus.json "
            "(default: $SREF_RECIPE_CORPUS_ROOT or ../recipe-corpus)"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="consumer manifest to use (default: conformance/recipe-corpus.json)",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict) or config.get("schema_version") != 3:
        raise ValueError("recipe-corpus configuration must have schema_version 3")
    corpus = config.get("corpus")
    cases = config.get("cases")
    audit = config.get("loss_audit")
    if (
        not isinstance(corpus, dict)
        or not isinstance(cases, list)
        or not cases
        or not isinstance(audit, dict)
    ):
        raise ValueError(
            "recipe-corpus configuration requires corpus metadata, cases, and loss_audit"
        )
    for field in ("commit", "targets_directory"):
        if not isinstance(corpus.get(field), str) or not corpus[field]:
            raise ValueError(f"recipe-corpus configuration requires corpus.{field}")
    if not GIT_COMMIT_RE.fullmatch(corpus["commit"]):
        raise ValueError("recipe-corpus configuration requires a full immutable Git commit")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("recipe-corpus case must be an object")
        case_id = case.get("id")
        fixture = case.get("fixture")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError("recipe-corpus cases require unique IDs")
        if not isinstance(fixture, str) or not fixture or Path(fixture).is_absolute():
            raise ValueError(f"{case_id}: fixture must be a relative path")
        if Path(fixture).parts != (Path(fixture).name,):
            raise ValueError(f"{case_id}: fixture must be a filename, not a path")
        if case.get("rights") != "redistributable":
            raise ValueError(f"{case_id}: only redistributable corpus targets are permitted")
        case_ids.add(case_id)

    report = audit.get("report")
    target = audit.get("target")
    expected = audit.get("expected_classifications")
    expected_feature_count = audit.get("expected_feature_count")
    full_corpus = audit.get("full_corpus")
    if not isinstance(report, str) or not report or Path(report).is_absolute():
        raise ValueError("loss_audit.report must be a relative path")
    if not isinstance(target, dict) or target.get("kind") != "sref":
        raise ValueError("loss_audit.target.kind must be sref")
    if not isinstance(target.get("version"), str) or not GIT_COMMIT_RE.fullmatch(
        target["version"]
    ):
        raise ValueError("loss_audit.target.version must be a full immutable Git commit")
    target_directory = Path(corpus["targets_directory"])
    if len(target_directory.parts) < 2 or target_directory.parts[-2] != target["version"]:
        raise ValueError("loss_audit target version must match the targets directory")
    if not isinstance(expected, dict) or set(expected) != set(CLASSIFICATIONS):
        raise ValueError(
            "loss_audit.expected_classifications must contain every classification"
        )
    if any(
        not isinstance(expected[name], int) or expected[name] < 0
        for name in CLASSIFICATIONS
    ):
        raise ValueError(
            "loss_audit expected classification counts must be nonnegative integers"
        )
    if not isinstance(expected_feature_count, int) or expected_feature_count < 1:
        raise ValueError("loss_audit.expected_feature_count must be a positive integer")
    # Which concepts are defects is pinned exactly by the concept digest. This
    # names the review gate around them: how many there are, and the tracked
    # defects they are allowed to belong to.
    for _classification, key, label in DEFECTS:
        expected_defects = audit.get(key)
        if not isinstance(expected_defects, dict):
            raise ValueError(f"loss_audit.{key} must be an object")
        count = expected_defects.get("count")
        issues = expected_defects.get("issues")
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"expected {label} require a nonnegative count")
        if (
            not isinstance(issues, list)
            or (count and not issues)
            or any(not isinstance(issue, str) or not issue for issue in issues)
        ):
            raise ValueError(f"expected {label} require the issues that track them")
    if not isinstance(full_corpus, dict):
        raise ValueError("loss_audit.full_corpus is required")
    expected_representation_count = full_corpus.get("expected_representation_count")
    expected_dispositions = full_corpus.get("expected_dispositions")
    expected_concept_count = full_corpus.get("expected_concept_count")
    expected_concepts_sha256 = full_corpus.get("expected_concepts_sha256")
    expected_input_boundaries = full_corpus.get("expected_input_boundaries")
    if not isinstance(expected_representation_count, int) or expected_representation_count < 1:
        raise ValueError(
            "loss_audit.full_corpus.expected_representation_count must be positive"
        )
    if not isinstance(expected_dispositions, dict) or set(expected_dispositions) != set(
        CASE_DISPOSITIONS
    ):
        raise ValueError(
            "loss_audit.full_corpus.expected_dispositions must contain every disposition"
        )
    if any(
        not isinstance(expected_dispositions[name], int)
        or expected_dispositions[name] < 0
        for name in CASE_DISPOSITIONS
    ):
        raise ValueError(
            "loss_audit.full_corpus expected disposition counts must be nonnegative integers"
        )
    if sum(expected_dispositions.values()) != expected_representation_count:
        raise ValueError(
            "loss_audit.full_corpus disposition counts must equal representation count"
        )
    if expected_dispositions["non_executable"]:
        raise ValueError(
            "loss_audit.full_corpus cannot declare non_executable cases as complete"
        )
    if not isinstance(expected_concept_count, int) or expected_concept_count < 1:
        raise ValueError(
            "loss_audit.full_corpus.expected_concept_count must be positive"
        )
    if not isinstance(expected_input_boundaries, dict) or set(
        expected_input_boundaries
    ) != set(INPUT_BOUNDARIES):
        raise ValueError(
            "loss_audit.full_corpus.expected_input_boundaries must contain every boundary"
        )
    if any(
        not isinstance(expected_input_boundaries[name], int)
        or expected_input_boundaries[name] < 0
        for name in INPUT_BOUNDARIES
    ) or sum(expected_input_boundaries.values()) != expected_concept_count:
        raise ValueError(
            "loss_audit.full_corpus input-boundary counts must equal concept count"
        )
    if not isinstance(expected_concepts_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_concepts_sha256
    ):
        raise ValueError(
            "loss_audit.full_corpus.expected_concepts_sha256 must be a SHA-256 hex digest"
        )
    return config


def target_path(corpus_root: Path, targets_directory: str, fixture: str) -> Path:
    root = corpus_root.resolve()
    directory = (root / targets_directory).resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError("configured targets directory escapes corpus root") from exc
    path = (directory / fixture).resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError(f"fixture {fixture!r} escapes configured targets directory") from exc
    return path


def full_audit_target_path(
    corpus_root: Path, targets_directory: str, fixture: str
) -> Path:
    """Resolve a full-audit fixture named relative to the target directory."""
    fixture_path = Path(fixture)
    if fixture_path.is_absolute() or fixture_path.parts != ("targets", fixture_path.name):
        raise ValueError("full-corpus target fixture must be targets/<filename>")
    return target_path(corpus_root, targets_directory, fixture_path.name)


def corpus_path(corpus_root: Path, relative_path: str, label: str) -> Path:
    root = corpus_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"configured {label} escapes corpus root") from exc
    return path


def derived_asset_errors(document: dict[str, Any], fixture: Path) -> list[str]:
    """Validate files referenced by an unpackaged derived recipe target."""
    errors: list[str] = []
    version_root = fixture.parent.parent.resolve()
    assets = document.get("assets", [])
    if not isinstance(assets, list):
        return errors
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("id", "<unknown>")
        relative = asset.get("path")
        if not isinstance(relative, str):
            continue
        path = (version_root / relative).resolve()
        try:
            path.relative_to(version_root)
        except ValueError:
            errors.append(f"asset {asset_id}: path escapes the target version directory")
            continue
        if not path.is_file():
            errors.append(f"asset {asset_id}: missing file {path}")
            continue
        data = path.read_bytes()
        if isinstance(asset.get("size"), int) and asset["size"] != len(data):
            errors.append(
                f"asset {asset_id}: size mismatch: expected {asset['size']}, found {len(data)}"
            )
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if isinstance(asset.get("sha256"), str) and asset["sha256"] != actual_sha256:
            errors.append(
                f"asset {asset_id}: SHA-256 mismatch: expected {asset['sha256']}, "
                f"found {actual_sha256}"
            )
    return errors


def loss_identity(loss: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(loss.get("case_id", "")),
        str(loss.get("concept_id", "")),
        str(loss.get("issue", "")),
    )


CONCEPT_FIELDS = (
    "case_id",
    "concept_id",
    "source_concept_id",
    "feature",
    "classification",
    "boundary",
    "basis",
    "sref_capability",
)


def concept_identity(concept: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        concept[field] if isinstance(concept.get(field), str) else ""
        for field in CONCEPT_FIELDS
    )


def canonical_concept_digest(concepts: list[dict[str, Any]]) -> str:
    """Pin every verdict together with the reasoning that produced it.

    Including the basis and capability means a repin cannot keep a verdict's
    label while silently changing why it was reached.
    """
    canonical = [
        dict(zip(CONCEPT_FIELDS, identity))
        for identity in sorted(concept_identity(concept) for concept in concepts)
    ]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def report_representation_ids(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Read the corpus denominator from its public representation inventory."""
    failures: list[str] = []
    representations = report.get("representations")
    if not isinstance(representations, list):
        return [], ["loss audit report has no representation inventory"]
    ids: list[str] = []
    for representation in representations:
        case_id = representation.get("case_id") if isinstance(representation, dict) else None
        if not isinstance(case_id, str) or not case_id:
            failures.append("loss audit representation inventory has an invalid case ID")
            continue
        ids.append(case_id)
    if len(ids) != len(set(ids)):
        failures.append("loss audit representation inventory has duplicate case IDs")
    counts = report.get("counts")
    if not isinstance(counts, dict) or counts.get("representations") != len(ids):
        failures.append("loss audit representation inventory does not match its count")
    return sorted(ids), failures


def validate_full_corpus(
    corpus_root: Path,
    targets_directory: str,
    report: dict[str, Any],
    target: dict[str, str],
    bucket: dict[str, Any],
    expected: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[tuple[str, Path]]]:
    """Require a complete, concept-level account of the corpus denominator."""
    failures: list[str] = []
    evaluated_targets: list[tuple[str, Path]] = []
    representation_ids, inventory_failures = report_representation_ids(report)
    failures.extend(inventory_failures)
    if len(representation_ids) != expected["expected_representation_count"]:
        failures.append(
            "loss audit representation denominator changed: "
            f"expected {expected['expected_representation_count']}, "
            f"found {len(representation_ids)}"
        )
    representation_features = {
        item["case_id"]: set(item.get("features", []))
        for item in report.get("representations", [])
        if isinstance(item, dict)
        and isinstance(item.get("case_id"), str)
        and isinstance(item.get("features"), list)
        and all(isinstance(feature, str) and feature for feature in item["features"])
    }

    fidelity = report["fidelity"]
    full_corpus = fidelity.get("full_corpus")
    target_key = f"{target['kind']}:{target['version']}"
    target_inventory = None
    if isinstance(full_corpus, dict):
        for candidate in full_corpus.get("targets", []):
            if (
                isinstance(candidate, dict)
                and candidate.get("kind") == target["kind"]
                and candidate.get("version") == target["version"]
            ):
                target_inventory = candidate
                break
    if target_inventory is None:
        return (
            failures + [f"loss audit report has no full-corpus inventory for {target_key}"],
            [],
            evaluated_targets,
        )

    dispositions = target_inventory.get("case_dispositions")
    disposition_by_case: dict[str, dict[str, Any]] = {}
    if not isinstance(dispositions, list):
        failures.append("full-corpus inventory has no case dispositions")
    else:
        for item in dispositions:
            case_id = item.get("case_id") if isinstance(item, dict) else None
            disposition = item.get("disposition") if isinstance(item, dict) else None
            if not isinstance(case_id, str) or not case_id:
                failures.append("full-corpus inventory has a disposition without a case ID")
                continue
            if case_id in disposition_by_case:
                failures.append(f"full-corpus inventory has duplicate disposition for {case_id}")
                continue
            if disposition not in CASE_DISPOSITIONS:
                failures.append(
                    f"full-corpus inventory has unsupported disposition {disposition!r} for {case_id}"
                )
                continue
            disposition_by_case[case_id] = item
        inventory_set = set(representation_ids)
        disposition_set = set(disposition_by_case)
        missing = sorted(inventory_set - disposition_set)
        undeclared = sorted(disposition_set - inventory_set)
        if missing:
            failures.append(
                "full-corpus inventory has silently unevaluated cases: " + ", ".join(missing)
            )
        if undeclared:
            failures.append(
                "full-corpus inventory names cases outside the denominator: "
                + ", ".join(undeclared)
            )

    actual_dispositions = {
        disposition: sum(
            1
            for item in disposition_by_case.values()
            if item.get("disposition") == disposition
        )
        for disposition in CASE_DISPOSITIONS
    }
    if actual_dispositions != expected["expected_dispositions"]:
        failures.append(
            "loss audit full-corpus disposition counts changed: "
            f"expected {expected['expected_dispositions']}, found {actual_dispositions}"
        )
    blocked = sorted(
        case_id
        for case_id, item in disposition_by_case.items()
        if item.get("disposition") == "non_executable"
    )
    if blocked:
        failures.append(
            "full-corpus loss audit is incomplete; non-executable cases remain: "
            + ", ".join(blocked)
        )
    if target_inventory.get("unevaluated_case_ids") != []:
        failures.append("full-corpus loss audit has unevaluated cases")
    if target_inventory.get("complete") is not True:
        failures.append("full-corpus SREF loss audit is not complete")
    for case_id, item in sorted(disposition_by_case.items()):
        if item.get("disposition") != "evaluated":
            continue
        fixture = item.get("target_fixture")
        if not isinstance(fixture, str) or not fixture:
            failures.append(
                f"full-corpus evaluated case {case_id} has no derived SREF target fixture"
            )
            continue
        try:
            fixture_path = full_audit_target_path(corpus_root, targets_directory, fixture)
        except ValueError as exc:
            failures.append(f"full-corpus evaluated case {case_id}: {exc}")
            continue
        if not fixture_path.is_file():
            failures.append(
                f"full-corpus evaluated case {case_id}: missing target {fixture_path}"
            )
            continue
        evaluated_targets.append((case_id, fixture_path))

    concepts = bucket.get("concepts")
    valid_concepts: list[dict[str, Any]] = []
    if not isinstance(concepts, list):
        failures.append("loss audit target has no concept-level classifications")
        return failures, valid_concepts, evaluated_targets
    concept_keys: set[tuple[str, str]] = set()
    concepts_by_case: dict[str, list[dict[str, Any]]] = {}
    for concept in concepts:
        if not isinstance(concept, dict):
            failures.append("loss audit target has a non-object concept classification")
            continue
        (
            case_id,
            concept_id,
            source_concept_id,
            feature,
            classification,
            boundary,
            basis,
            capability,
        ) = concept_identity(concept)
        if not all((case_id, concept_id, source_concept_id, feature, boundary, basis, capability)):
            failures.append("loss audit target concept classification is missing required fields")
            continue
        if boundary not in INPUT_BOUNDARIES:
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} has an invalid evaluation boundary"
            )
            continue
        if classification not in CLASSIFICATIONS:
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} has an invalid SREF verdict"
            )
            continue
        if (classification == "upstream_lost") != (boundary != "sref_input"):
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} disagrees with its evaluation boundary"
            )
            continue
        # An audit limitation must never be recorded as a limitation of SREF.
        if classification == "sref_unsupported" and capability != "none":
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} reports a format gap for a supported capability"
            )
            continue
        if classification == "mapping_unverified" and basis not in (
            "no-audit-detector-for-capability",
            "no-target-to-inspect",
        ):
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} reports an unverified mapping without an audit-limitation basis"
            )
            continue
        if case_id not in disposition_by_case:
            failures.append(
                f"loss audit target concept {case_id}/{concept_id} is outside the denominator"
            )
            continue
        key = (case_id, concept_id)
        if key in concept_keys:
            failures.append(f"loss audit target has duplicate concept {case_id}/{concept_id}")
            continue
        concept_keys.add(key)
        valid_concepts.append(concept)
        concepts_by_case.setdefault(case_id, []).append(concept)

    for case_id, item in sorted(disposition_by_case.items()):
        if item.get("disposition") in ("evaluated", "reference_only") and not concepts_by_case.get(
            case_id
        ):
            failures.append(f"full-corpus loss audit has no concepts for {case_id}")
        declared_features = representation_features.get(case_id)
        classified_features = {
            concept["feature"] for concept in concepts_by_case.get(case_id, [])
        }
        if declared_features is None:
            failures.append(
                f"full-corpus loss audit cannot read declared features for {case_id}"
            )
        elif missing_features := sorted(declared_features - classified_features):
            failures.append(
                f"full-corpus loss audit has unclassified declared features for {case_id}: "
                + ", ".join(missing_features)
            )
    if len(valid_concepts) != expected["expected_concept_count"]:
        failures.append(
            "loss audit concept denominator changed: "
            f"expected {expected['expected_concept_count']}, found {len(valid_concepts)}"
        )
    actual_input_boundaries = {
        boundary: sum(
            1
            for concept in valid_concepts
            if concept.get("boundary") == boundary
        )
        for boundary in INPUT_BOUNDARIES
    }
    if actual_input_boundaries != expected["expected_input_boundaries"]:
        failures.append(
            "loss audit input-boundary counts changed: "
            f"expected {expected['expected_input_boundaries']}, "
            f"found {actual_input_boundaries}"
        )
    actual_digest = canonical_concept_digest(valid_concepts)
    if actual_digest != expected["expected_concepts_sha256"]:
        failures.append(
            "loss audit concept classifications changed: "
            f"expected {expected['expected_concepts_sha256']}, found {actual_digest}"
        )

    classifications = bucket.get("classifications")
    if isinstance(classifications, dict) and set(classifications) == set(CLASSIFICATIONS):
        computed = {
            classification: sum(
                1
                for concept in valid_concepts
                if concept["classification"] == classification
            )
            for classification in CLASSIFICATIONS
        }
        if classifications != computed:
            failures.append(
                "loss audit classification totals do not match concept-level classifications"
            )
    return failures, valid_concepts, evaluated_targets


def defect_failures(
    reported: Any,
    target: dict[str, Any],
    expected: dict[str, Any],
    classified: int | None,
    label: str,
) -> list[str]:
    if not isinstance(reported, list):
        return [f"loss audit {label} list is missing"]
    failures: list[str] = []
    defects = [
        defect
        for defect in reported
        if isinstance(defect, dict) and defect.get("target") == target
    ]
    if len(defects) != expected["count"]:
        failures.append(
            f"{label} changed: expected {expected['count']}, found {len(defects)}"
        )
    unlinked = sorted(
        f"{defect.get('case_id')}/{defect.get('concept_id')}"
        for defect in defects
        if not isinstance(defect.get("issue"), str) or not defect["issue"]
    )
    if unlinked:
        failures.append(f"{label} without a linked defect: " + ", ".join(unlinked))
    untracked = sorted(
        {
            defect["issue"]
            for defect in defects
            if isinstance(defect.get("issue"), str)
            and defect["issue"] not in expected["issues"]
        }
    )
    if untracked:
        failures.append(f"{label} tracked by unreviewed issues: " + ", ".join(untracked))
    if classified is not None and classified != len(defects):
        failures.append(f"{label} count does not match the detailed list")
    return failures


def validate_loss_audit(
    corpus_root: Path, config: dict[str, Any]
) -> tuple[list[str], dict[str, int], int, list[tuple[str, Path]]]:
    audit = config["loss_audit"]
    target = audit["target"]
    target_key = f"{target['kind']}:{target['version']}"
    failures: list[str] = []
    try:
        report_path = corpus_path(corpus_root, audit["report"], "loss audit report")
        report = load_json(report_path)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        DuplicateKeyError,
        NonFiniteNumberError,
    ) as exc:
        return [f"loss audit report is invalid: {exc}"], {}, 0, []

    if not isinstance(report, dict) or report.get("schema_version") != 3:
        return ["loss audit report must have schema_version 3"], {}, 0, []
    fidelity = report.get("fidelity")
    if not isinstance(fidelity, dict):
        return ["loss audit report has no fidelity object"], {}, 0, []
    # The consumer pins the SREF verdict vocabulary. The report's separate
    # `classification_order` describes source and importer observations, which
    # are a different judgement and are not this gate's concern.
    if fidelity.get("sref_verdict_order") != list(CLASSIFICATIONS):
        failures.append("loss audit SREF verdict vocabulary changed")
    if not isinstance(fidelity.get("basis"), str) or not fidelity["basis"]:
        failures.append("loss audit does not state the basis of its classifications")
    accounting = report.get("accounting")
    if not isinstance(accounting, dict) or not isinstance(accounting.get("basis"), str):
        failures.append("loss audit report does not separate representation accounting from fidelity")
    current_targets = fidelity.get("current_targets")
    if (
        not isinstance(current_targets, dict)
        or current_targets.get(target["kind"]) != target["version"]
    ):
        failures.append(f"loss audit report does not register current target {target_key}")

    expected_cases = sorted(case["id"] for case in config["cases"])
    declared_slice = fidelity.get("declared_slice")
    slice_target = None
    if isinstance(declared_slice, dict):
        for candidate in declared_slice.get("targets", []):
            if (
                isinstance(candidate, dict)
                and candidate.get("kind") == target["kind"]
                and candidate.get("version") == target["version"]
            ):
                slice_target = candidate
                break
    if slice_target is None:
        failures.append(f"loss audit report has no declared slice for {target_key}")
    else:
        for field in ("required_case_ids", "completed_case_ids"):
            values = slice_target.get(field)
            if not isinstance(values, list) or sorted(values) != expected_cases:
                failures.append(f"declared slice {field} does not match configured cases")
        if slice_target.get("missing_case_ids") != []:
            failures.append("declared slice has missing SREF evaluations")
        if slice_target.get("undeclared_case_ids") != []:
            failures.append("declared slice has undeclared SREF evaluations")
        if slice_target.get("complete") is not True:
            failures.append("declared SREF loss-audit slice is not complete")

    by_target = fidelity.get("by_target")
    bucket = by_target.get(target_key) if isinstance(by_target, dict) else None
    if not isinstance(bucket, dict):
        return failures + [f"loss audit report has no target bucket {target_key}"], {}, 0, []

    full_corpus_failures, _concepts, evaluated_targets = validate_full_corpus(
        corpus_root,
        config["corpus"]["targets_directory"],
        report,
        target,
        bucket,
        audit["full_corpus"],
    )
    failures.extend(full_corpus_failures)
    representation_ids, _inventory_failures = report_representation_ids(report)
    cases = bucket.get("cases")
    if not isinstance(cases, list) or sorted(cases) != representation_ids:
        failures.append("loss audit target cases do not match the full representation denominator")

    classifications = bucket.get("classifications")
    if not isinstance(classifications, dict) or set(classifications) != set(CLASSIFICATIONS):
        failures.append("loss audit target classification counts are incomplete")
        classifications = {}
    elif any(
        not isinstance(classifications[name], int) or classifications[name] < 0
        for name in CLASSIFICATIONS
    ):
        failures.append("loss audit target classification counts are invalid")
        classifications = {}
    elif classifications != audit["expected_classifications"]:
        failures.append(
            "loss audit classification counts changed: "
            f"expected {audit['expected_classifications']}, found {classifications}"
        )

    features = bucket.get("features")
    feature_count = len(features) if isinstance(features, dict) else 0
    if feature_count != audit["expected_feature_count"]:
        failures.append(
            "loss audit feature coverage changed: "
            f"expected {audit['expected_feature_count']}, found {feature_count}"
        )

    stale = fidelity.get("stale_evaluations")
    if not isinstance(stale, list):
        failures.append("loss audit stale-evaluation list is missing")
    else:
        # A case's only SREF evaluation may not be against an older revision.
        current_cases = set(cases) if isinstance(cases, list) else set()
        superseded = sorted(
            {
                item["case_id"]
                for item in stale
                if isinstance(item, dict)
                and item.get("target_kind") == target["kind"]
                and isinstance(item.get("case_id"), str)
                and item["case_id"] not in current_cases
            }
        )
        if superseded:
            failures.append(
                "loss audit presents superseded SREF evaluations as current for: "
                + ", ".join(superseded)
            )

    for classification, key, label in DEFECTS:
        failures.extend(
            defect_failures(
                fidelity.get(classification),
                target,
                audit[key],
                classifications.get(classification) if classifications else None,
                label,
            )
        )

    return failures, classifications, feature_count, evaluated_targets


def checked_out_commit(corpus_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(corpus_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise ValueError(
            "recipe-corpus root must be a Git checkout at the pinned commit"
            + (f": {detail}" if detail else "")
        ) from exc
    commit = result.stdout.strip()
    if not GIT_COMMIT_RE.fullmatch(commit):
        raise ValueError(f"recipe-corpus Git checkout returned invalid HEAD {commit!r}")
    return commit


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, DuplicateKeyError, NonFiniteNumberError) as exc:
        print(f"FAIL recipe-corpus configuration: {exc}", file=sys.stderr)
        return 2

    corpus = config["corpus"]
    corpus_root = args.corpus_root.resolve()
    if not corpus_root.is_dir():
        print(f"FAIL recipe-corpus checkout not found: {corpus_root}", file=sys.stderr)
        return 2
    try:
        actual_commit = checked_out_commit(corpus_root)
    except ValueError as exc:
        print(f"FAIL recipe-corpus checkout: {exc}", file=sys.stderr)
        return 2
    if actual_commit != corpus["commit"]:
        print(
            "FAIL recipe-corpus checkout is not at the pinned commit: "
            f"expected {corpus['commit']}, found {actual_commit}",
            file=sys.stderr,
        )
        return 2

    recipe_validator = validator("recipe.schema.json")
    units_document = load_json(ROOT / "registry" / "units.json")
    units = {unit["id"]: unit for unit in units_document["units"]}
    failures: list[str] = []
    for case in config["cases"]:
        try:
            fixture = target_path(
                corpus_root, corpus["targets_directory"], case["fixture"]
            )
        except ValueError as exc:
            failures.append(f"{case['id']}: {exc}")
            continue
        if not fixture.is_file():
            failures.append(f"{case['id']}: missing target {fixture}")
            continue
        try:
            document = load_json(fixture)
        except (OSError, UnicodeDecodeError, ValueError, DuplicateKeyError, NonFiniteNumberError) as exc:
            failures.append(f"{case['id']}: invalid JSON: {exc}")
            continue
        errors = [str(error) for error in recipe_validator.iter_errors(document)]
        if not errors:
            errors.extend(recipe_semantic_errors(document, units))
            errors.extend(derived_asset_errors(document, fixture))
        if errors:
            failures.append(f"{case['id']}: {'; '.join(errors)}")

    audit_failures, classifications, feature_count, full_audit_targets = validate_loss_audit(
        corpus_root, config
    )
    failures.extend(audit_failures)

    selected_target_paths = {
        target_path(corpus_root, corpus["targets_directory"], case["fixture"])
        for case in config["cases"]
    }
    for case_id, fixture in full_audit_targets:
        if fixture in selected_target_paths:
            continue
        try:
            document = load_json(fixture)
        except (OSError, UnicodeDecodeError, ValueError, DuplicateKeyError, NonFiniteNumberError) as exc:
            failures.append(f"{case_id}: invalid full-corpus target JSON: {exc}")
            continue
        errors = [str(error) for error in recipe_validator.iter_errors(document)]
        if not errors:
            errors.extend(recipe_semantic_errors(document, units))
            errors.extend(derived_asset_errors(document, fixture))
        if errors:
            failures.append(f"{case_id}: {'; '.join(errors)}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    classified = sum(classifications.values())
    summary = ", ".join(
        f"{classifications[name]} {name}" for name in CLASSIFICATIONS
    )
    full_corpus = config["loss_audit"]["full_corpus"]
    dispositions = full_corpus["expected_dispositions"]
    concept_count = full_corpus["expected_concept_count"]
    print(
        f"validated {len(full_audit_targets)} executable recipe-corpus SREF targets; "
        f"loss-audited {concept_count} concepts across "
        f"{full_corpus['expected_representation_count']} representations and "
        f"{feature_count} features ({summary}; "
        f"{dispositions['reference_only']} reference-only) from {corpus_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
