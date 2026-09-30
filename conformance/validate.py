#!/usr/bin/env python3

"""Validate the SREF schemas and bundled conformance fixtures."""

from __future__ import annotations

import functools
import hashlib
import io
import json
import math
import re
import stat
import sys
import unicodedata
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource
except ImportError as exc:
    raise SystemExit(
        "jsonschema with Draft 2020-12 support is required to run conformance validation"
    ) from exc


ROOT = Path(__file__).resolve().parent.parent
UINT64_MAX = 2**64 - 1
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ENTRY_BYTES = 128 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_002
MAX_COMPRESSION_RATIO = 200
MAX_PATH_LENGTH = 512
MAX_JSON_DEPTH = 128
MAX_JSON_NUMBER_CHARACTERS = 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
# Reference-reader policy, not a bundle-format validity constraint.
MAX_BUNDLE_MEMBERS = 10_000
SUPPORTED_RECIPE_VERSION = (0, 4, 0)
SUPPORTED_REGISTRY_VERSION = (0, 2, 0)

# This recognizes regular and private-use BCP 47 forms. Grandfathered tags are
# handled by the explicit registry below.
BCP47_RE = re.compile(
    r"^(?:"
    r"(?:[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
    r"(?:-[A-Za-z]{4})?"
    r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*"
    r"(?:-[0-9A-WY-Za-wy-z](?:-[A-Za-z0-9]{2,8})+)*"
    r"(?:-x(?:-[A-Za-z0-9]{1,8})+)?"
    r"|x(?:-[A-Za-z0-9]{1,8})+"
    r")$"
)
BCP47_GRANDFATHERED = {
    tag.casefold()
    for tag in (
        "art-lojban",
        "cel-gaulish",
        "en-GB-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "no-bok",
        "no-nyn",
        "sgn-BE-FR",
        "sgn-BE-NL",
        "sgn-CH-DE",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    )
}

#: The normative failure categories of specification section 22.1.
FAILURE_CATEGORIES = (
    "invalid-artifact",
    "unsupported-format-version",
    "unsupported-registry-version",
    "unknown-unit",
    "integrity-failure",
    "unsafe-archive",
    "resource-limit",
)

#: How this validator's own findings map onto those categories, in the order
#: sections 15 and 19 apply them: limits and archive structure before anything
#: is read out of the archive, then declarations against bytes. It lets a
#: fixture be checked for carrying more than one category of defect. Anything
#: unmatched is `invalid-artifact`, the specification's fallback.
_RESOURCE_LIMIT_MARKERS = (
    "exceeds compression-ratio limit",
    "exceeds compressed-byte limit",
    "exceeds expanded-byte limit",
    "exceeds archive-entry limit",
    "exceeds member limit",
    "exceeds byte limit",
    "exceeds JSON byte limit",
    "path exceeds length limit",
)
_UNSAFE_ARCHIVE_MARKERS = (
    "duplicate archive entry",
    "nonregular archive entry",
    "encrypted archive entry",
)
#: Path faults are only archive faults when the entry is the archive's. The
#: same wording addressed to a recipe's asset declaration is a section 12
#: violation in a document, and stays `invalid-artifact`.
_ARCHIVE_ENTRY_PREFIX = "archive entry "
_INTEGRITY_MARKERS = (
    "digest mismatch",
    "size mismatch",
    "missing asset entry",
    "missing bundle member",
    "undeclared archive entry",
    "undeclared bundle entry",
    "differs from manifest",
    "recipe and manifest asset IDs differ",
    "but carries",
)
_UNKNOWN_UNIT_MARKER = "unknown unit "
#: A recipe says so in prose; a package or bundle manifest says so through the
#: schema constant that pins its container version, whose rejection message
#: names the version that was expected.
_UNSUPPORTED_FORMAT_MARKERS = (
    "unsupported recipe version",
    "'0.1.0' was expected",
    "1 was expected",
)
_UNSUPPORTED_REGISTRY_MARKER = "unsupported unit-registry version"


def failure_category(message: str) -> str:
    """Classify one validator finding under specification section 22.1."""
    if any(marker in message for marker in _RESOURCE_LIMIT_MARKERS):
        return "resource-limit"
    if any(marker in message for marker in _UNSAFE_ARCHIVE_MARKERS):
        return "unsafe-archive"
    if message.startswith(_ARCHIVE_ENTRY_PREFIX) and ": " in message:
        return "unsafe-archive"
    if _UNSUPPORTED_REGISTRY_MARKER in message:
        return "unsupported-registry-version"
    if any(marker in message for marker in _UNSUPPORTED_FORMAT_MARKERS):
        return "unsupported-format-version"
    if _UNKNOWN_UNIT_MARKER in message:
        return "unknown-unit"
    if any(marker in message for marker in _INTEGRITY_MARKERS):
        return "integrity-failure"
    return "invalid-artifact"


EXPECTED_ERROR_MARKERS: dict[str, tuple[str, ...]] = {
    "duplicate-unit-id": ("unit registry contains duplicate IDs",),
    "nonpositive-unit-multiplier": ("conversion multiplier must be positive",),
    "affine-nontemperature-unit": (
        "affine conversion is limited to temperature",
    ),
    "unknown-unit-base": ("base unit mass.missing does not exist",),
    "unit-conversion-cycle": ("conversion cycle",),
    "multiple-dimension-bases": (
        "expected exactly one physical base unit, found 2",
    ),
    "duplicate-normalized-unit-alias": ("duplicate normalized alias",),
    "active-unit-replacement": ("should not be valid under", "replacement"),
    "missing-unit-replacement": ("replacement does not exist",),
    "active-unit-without-alias": ("active unit has no parsing aliases",),
    "physical-unit-reference-required": ("physical unit has no reference",),
    "duplicate-unit-alias-set": ("duplicate alias set",),
    "missing-format-version": ("'version' is a required property",),
    "legacy-string-author": ("'Jane Doe' is not of type 'object'",),
    "author-name-required": ("'name' is a required property",),
    "unknown-author-kind": ("'team' is not one of",),
    "author-kind-label-requires-other": ("'other' was expected",),
    "absolute-author-url-required": ("'/authors/jane-doe' does not match",),
    "source-identity-required": ("is not valid under any of the given schemas",),
    "source-application-required": ("'application' is a required property",),
    "duplicate-authored-category": ("has non-unique elements",),
    "invalid-publication-chronology": ("is not valid under any of the given schemas",),
    "invalid-publication-date": ("is not valid under any of the given schemas",),
    "noncanonical-rational-syntax": ("'1.5'", "not valid under any of the given schemas"),
    "unsupported-format-version": ("unsupported recipe version",),
    "unsupported-registry-version": ("unsupported unit-registry version",),
    "unreduced-rational": ("fraction must be reduced",),
    "range-order": ("range minimum exceeds maximum",),
    "duplicate-ingredient-id": ("duplicate ingredient ID",),
    "dangling-ingredient-reference": ("dangling ingredient reference",),
    "ingredient-use-reference-required": ("'ingredient_ref' is a required property",),
    "choice-use-quantity": ("whole-choice use cannot carry quantity",),
    "equipment-name-required": ("'name' is a required property",),
    "duplicate-step-ingredient-reference": ("duplicate ingredient reference",),
    "temperature-ingredient-use": ("cannot be an ingredient-use quantity",),
    "dangling-step-image-reference": ("dangling step image reference",),
    "step-image-media-type": ("step image source-note is not an image",),
    "dangling-recipe-image-reference": ("dangling recipe image reference",),
    "recipe-image-media-type": ("recipe image source-note is not an image",),
    "duplicate-recipe-image-reference": ("has non-unique elements",),
    "primary-image-not-in-image-refs": (
        "primary image hero-image is not present in recipe image_refs",
    ),
    "legacy-primary-image-role": ("'primary-image'", "is not one of"),
    "legacy-step-image-role": ("'step-image'", "is not one of"),
    "unknown-unit": ("unknown unit",),
    "member-not-defined-by-version": ("is not defined by SREF",),
    "duplicate-json-member": ("duplicate JSON member",),
    "nonfinite-json-number": ("nonfinite JSON number",),
    "invalid-language-tag": ("invalid BCP 47 language tag",),
    # Matched on the member-name pattern rather than on one fixture's name,
    # because three fixtures break three different parts of the same rule:
    # too few labels, an empty label, and no reversed domain at all.
    "invalid-extension-name": ("does not match", "(?!x-)"),
    "extension-cannot-satisfy-core": ("'title' is a required property",),
    "duplicate-step-id": ("duplicate step ID",),
    "step-text-required": ("'text' is a required property",),
    "optional-must-be-boolean": ("'yes' is not of type 'boolean'",),
    "variant-nesting": ("must not contain nested variants",),
    "variant-restructures-recipe": ("must not restructure the recipe",),
    "duplicate-section-id": ("duplicate ingredient section ID",),
    "duplicate-instruction-section-id": ("duplicate instruction section ID",),
    "duplicate-step-image-reference": ("has non-unique elements",),
    "duplicate-asset-id": ("duplicate asset ID",),
    "duplicate-asset-path": ("duplicate asset path",),
    "unsafe-asset-path": ("unsafe path segment",),
    "noncanonical-denominator": ("fraction denominator must exceed one",),
    "rational-out-of-range": ("rational numerator exceeds unsigned 64-bit range",),
    "prohibited-control-character": ("prohibited C0 control character",),
    "primary-image-media-type": ("is not an image",),
    "invalid-temperature-unit": ("is not a temperature unit",),
    "opaque-temperature-conflict": ("is not valid under any of the given schemas",),
    "negative-zero-temperature": ("negative zero is not canonical",),
    "temperature-as-quantity": ("cannot be an ingredient quantity",),
    "temperature-package-size": ("cannot describe package size",),
    "temperature-yield": ("cannot describe recipe yield",),
    "temperature-equipment": ("cannot describe equipment quantity",),
    "temperature-purpose-kind-required": ("'kind' is a required property",),
    "temperature-purpose-unknown-kind": ("'steam' is not one of",),
    "temperature-purpose-other-label-required": ("'label' is a required property",),
    "nonphysical-package-size": ("is not physical",),
    "timing-other-without-label": ("'label' is a required property",),
    "timing-unknown-kind": ("'sitting-about' is not one of",),
    "timing-id-required": ("'id' is a required property",),
    "timing-without-duration": ("'duration' is a required property",),
    "timing-duration-conflict": ("is not valid under any of the given schemas",),
    "timing-invalid-attention": ("'sometimes' is not one of",),
    "duplicate-step-timing-reference": ("has non-unique elements",),
    "timing-summary-expression-required": ("is not of type 'object'",),
    "microwave-power-conflict": ("is not valid under any of the given schemas",),
    "microwave-percent-out-of-range": ("power percent must be greater than 0 and at most 100",),
    "microwave-choice-duration-must-be-opaque": ("'text' is a required property",),
    "microwave-choice-shared-power-conflict": ("choice schedule must not also carry shared rated output or power",),
    "microwave-choice-duplicate-conditions": ("duplicate microwave choice conditions",),
    "translation-counterpart-required": ("is not valid under any of the given schemas",),
    "translation-unknown-relation": ("is not one of ['original', 'translation', 'alternate']",),
    "translation-invalid-language": ("invalid BCP 47 language tag",),
    "translation-single-original": ("more than one translation original",),
    "translation-requires-document-language": ("translations require the recipe's own language",),
    "translation-self-reference": ("translation refers to this recipe's own ID",),
    "duplicate-variant-id": ("duplicate variant ID",),
    "dangling-claim-variant-reference": ("dangling variant reference",),
    "dependency-self-reference": ("recipe dependency refers to this recipe's own ID",),
    "dependency-identity-required": ("is not valid under any of the given schemas",),
    "temperature-nutrition-basis": ("cannot describe nutrition basis",),
    "nutrition-duplicate-nutrient": ("duplicate nutrient",),
    "nutrition-energy-mass-unit": ("is not one of ['kcal', 'kJ']",),
    "nutrition-mass-energy-unit": ("is not one of ['g', 'mg', 'mcg']",),
    "nutrition-quantity-basis-without-quantity": ("'quantity' is a required property",),
    "nutrition-unspecified-basis-with-quantity": ("False schema does not allow",),
    "nutrition-opaque-value-with-amount": ("is not valid under any of the given schemas",),
    "nutrition-other-without-label": ("'label' is a required property",),
    "nutrition-unknown-basis": ("is not one of ['recipe', 'serving', 'quantity', 'unspecified']",),
    "nutrition-empty-nutrients": ("should be non-empty",),
    "dietary-claim-suitability-required": ("'suitability' is a required property",),
    "dietary-claim-unknown-diet": ("'paleo' is not one of",),
    "allergen-presence-required": ("'presence' is a required property",),
    "allergen-unknown-presence": ("'trace' is not one of",),
    "allergen-substance-required": ("'substance' is a required property",),
    "asset-license-identity-required": ("is not valid under any of the given schemas",),
    "asset-relative-source-url": ("does not match",),
    "singular-yield-member": ("is not defined by SREF",),
    "empty-yields": ("should be non-empty",),
    "duplicate-timing-id": ("duplicate timing ID",),
    "dangling-step-timing-reference": ("dangling timing reference",),
    "normalization-source-required": ("'source_text' is a required property",),
    "normalization-warning-required": ("'warnings' is a required property",),
    "nested-quantity-alternative": ("is not valid under any of the given schemas",),
    "alternative-inside-sum": ("is not valid under any of the given schemas",),
    "missing-asset-entry": ("missing asset entry",),
    "undeclared-archive-entry": ("undeclared archive entry",),
    "asset-digest-mismatch": ("asset 5source-note: digest mismatch",),
    "asset-size-mismatch": ("asset 5source-note: size mismatch",),
    "recipe-digest-mismatch": ("recipe digest mismatch",),
    "recipe-manifest-disagreement": ("differs from manifest",),
    "duplicate-manifest-asset": ("duplicate manifest asset ID",),
    "unsafe-archive-path": ("unsafe path segment",),
    "backslash-archive-path": ("backslash in path",),
    "absolute-archive-path": ("absolute path",),
    "drive-letter-archive-path": ("drive-letter path",),
    "control-character-archive-path": ("control character in path",),
    "empty-archive-path-segment": ("unsafe path segment",),
    "duplicate-archive-entry": ("duplicate archive entry",),
    "nonregular-archive-entry": ("nonregular archive entry",),
    "missing-manifest": ("exactly one manifest.json",),
    "missing-recipe": ("exactly one recipe.json",),
    "malformed-package-json": ("invalid package JSON",),
    "duplicate-package-manifest-member": (
        "invalid package JSON",
        "duplicate JSON member",
    ),
    "trailing-package-manifest-value": ("invalid package JSON", "Extra data"),
    "compression-ratio-limit": ("exceeds compression-ratio limit",),
    "invalid-zip": ("invalid ZIP package",),
    "missing-bundle-member": ("missing bundle member",),
    "undeclared-bundle-entry": ("undeclared bundle entry",),
    "bundle-member-digest-mismatch": ("bundle member 1r00001: digest mismatch",),
    "bundle-member-size-mismatch": ("bundle member 1r00001: size mismatch",),
    "bundle-member-id-required": ("'member_id' is a required property",),
    "duplicate-bundle-member-id": ("duplicate bundle member ID",),
    "bundle-member-path-mismatch": ("is not recipes/r000002.sref",),
    "bundle-recipe-id-disagreement": (
        "declares recipe minimal but carries 3f2504e0-4f89-41d3-9a0c-0305e82c3301",
    ),
    "empty-bundle": ("[] should be non-empty",),
    "bundle-manifest-timestamp": ("'generated_at' was unexpected",),
    "duplicate-bundle-manifest-member": (
        "invalid bundle JSON",
        "duplicate JSON member",
    ),
    "trailing-bundle-manifest-value": ("invalid bundle JSON", "Extra data"),
    "missing-bundle-manifest": ("exactly one manifest.json",),
    "unsafe-bundle-member-path": ("unsafe path segment",),
    "bundle-entry-outside-recipes": ("bundle member path must start with recipes/",),
    "invalid-zip-bundle": ("invalid ZIP bundle",),
}


#: Per-case assertions for categories that cover many rules, such as
#: `malformed-package-json` and `invalid-bundle-member-package`, where one
#: marker per category would let a fixture fail for some other reason.
EXPECTED_CASE_MARKERS = {
    "choice-single-branch": ("is too short",),
    "choice-nested": ("False schema does not allow",),
    "choice-shared-quantity": ("False schema does not allow",),
    "choice-unknown-relation": ("is not one of",),
    "choice-missing-relation": ("'relation' is a required property",),
    "choice-branch-without-name": ("'name' is a required property",),
    "minimum-neither-collection": ("is not valid under any of the given schemas",),
    "minimum-empty-ingredient-collection": ("should be non-empty",),
    "minimum-empty-instruction-collection": ("should be non-empty",),
    "minimum-null-ingredient-collection": ("is not of type 'array'",),
    "minimum-null-instruction-collection": ("is not of type 'array'",),
    "variant-nested": ("'variants':", "should not be valid under"),
    "variant-embedded-recipe": (
        "'ingredient_sections':",
        "should not be valid under",
    ),
    "bundle-invalid-member-package": ("bundle member 1r00001: missing asset entry",),
    "bundle-member-unknown-unit": (
        "bundle member r000001:",
        "unknown unit volume.scoop.mystery",
    ),
    "package-manifest-missing-assets": ("'assets' is a required property",),
    "package-manifest-missing-package-header": ("'sref_package' is a required property",),
    "package-manifest-unsupported-package-version": ("'0.1.0' was expected",),
    "package-manifest-wrong-recipe-path": ("'recipe.json' was expected",),
    "package-manifest-wrong-recipe-media-type": ("'application/json' was expected",),
    "package-manifest-extra-member": ("'generated_by' was unexpected",),
    "bundle-manifest-wrong-format": ("'sref-bundle' was expected",),
    "bundle-manifest-missing-format": ("'format' is a required property",),
    "bundle-manifest-wrong-version": ("1 was expected",),
    "bundle-manifest-extra-member": ("'generated_by' was unexpected",),
}


def category_failures(case: dict[str, Any], errors: list[Any]) -> list[str]:
    """Check a case's declared category against what this validator found.

    The category must be one the specification publishes and the one this
    validator reaches, and the fixture must carry no other category of defect,
    or an implementation could correctly report either. Several findings of
    the same category are fine.
    """
    declared = case["error_category"]
    failures: list[str] = []
    if declared not in FAILURE_CATEGORIES:
        failures.append(f"{case['id']}: {declared} is not a normative failure category")
        return failures
    found = {failure_category(str(error)) for error in errors}
    if declared not in found:
        failures.append(
            f"{case['id']}: declares {declared}, and this validator found "
            f"{', '.join(sorted(found))}"
        )
    elif found != {declared}:
        failures.append(
            f"{case['id']}: asserts {declared} but carries independent defects in "
            f"{', '.join(sorted(found))}; a fixture asserting a category must "
            "isolate that fault"
        )
    return failures


class DuplicateKeyError(ValueError):
    """Raised when a JSON object repeats a member name."""


class NonFiniteNumberError(ValueError):
    """Raised when JSON contains NaN or an infinity token."""


class JSONDepthError(ValueError):
    """Raised before parsing JSON nested beyond the reader's finite policy."""


class JSONNumberLimitError(ValueError):
    """Raised before allocating an arbitrarily large JSON number."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def reject_nonfinite_number(value: str) -> None:
    raise NonFiniteNumberError(f"nonfinite JSON number {value}")


def parse_json_integer(value: str) -> int:
    if len(value.lstrip("-")) > MAX_JSON_NUMBER_CHARACTERS:
        raise JSONNumberLimitError("JSON integer exceeds digit limit")
    return int(value)


def parse_json_float(value: str) -> float:
    if len(value) > MAX_JSON_NUMBER_CHARACTERS:
        raise JSONNumberLimitError("JSON number exceeds character limit")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise NonFiniteNumberError(f"nonfinite JSON number {value}")
    return parsed


def check_json_depth(value: str) -> None:
    """Reject excessive object/array nesting before the recursive parser runs.

    Brackets inside strings are data, including after escaped quotes, so the
    preflight tracks the small part of JSON string syntax needed to ignore
    them. Full syntax remains the standard parser's job.
    """
    depth = 0
    in_string = False
    escaped = False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise JSONDepthError(
                    f"JSON nesting exceeds depth limit {MAX_JSON_DEPTH}"
                )
        elif character in "]}":
            depth -= 1


def load_json(path: Path) -> Any:
    return load_json_bytes(path.read_bytes())


def load_json_bytes(data: bytes) -> Any:
    text = data.decode("utf-8")
    check_json_depth(text)
    return json.loads(
        text,
        object_pairs_hook=unique_object,
        parse_constant=reject_nonfinite_number,
        parse_int=parse_json_integer,
        parse_float=parse_json_float,
    )


def validator(schema_name: str, registry: Registry | None = None) -> Draft202012Validator:
    schema = load_json(ROOT / "schema" / schema_name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema,
        registry=registry or Registry(),
        format_checker=FormatChecker(),
    )


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse a version already checked against the schema's canonical syntax."""
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def version_text(value: tuple[int, int, int]) -> str:
    return ".".join(str(component) for component in value)


def supported_version_error(
    declared_text: str,
    supported: tuple[int, int, int],
    subject: str,
) -> str | None:
    declared = parse_version(declared_text)
    if declared[0] == supported[0]:
        return None
    supported_text = ".".join(str(component) for component in supported)
    return (
        f"unsupported {subject} version {declared_text}; reader supports "
        f"{supported_text} and compatible newer versions"
    )


@functools.lru_cache(maxsize=1)
def version_scoped_validator() -> Draft202012Validator:
    """The recipe schema with its forward-compatibility openness removed.

    The published schema leaves objects open so older readers can read newer
    documents. Closing `additionalProperties` leaves section 13's rule for the
    declared version: its defined members, plus `x-` extensions.
    """
    schema = load_json(ROOT / "schema" / "recipe.schema.json")
    return Draft202012Validator(_closed(schema))


def _closed(node: Any) -> Any:
    if isinstance(node, dict):
        closed = {name: _closed(value) for name, value in node.items()}
        if closed.get("additionalProperties") is True:
            closed["additionalProperties"] = False
        return closed
    if isinstance(node, list):
        return [_closed(item) for item in node]
    return node


def allows_unknown_members(recipe: dict[str, Any]) -> bool:
    """Whether this document is a newer one being read for its known subset.

    Keyed on the recipe version alone. A newer unit registry widens the unit
    vocabulary and says nothing about which members exist, so the two
    compatibility lines stay independent (section 5).
    """
    header = recipe.get("sref")
    if not isinstance(header, dict) or "version" not in header:
        return False
    try:
        declared = parse_version(header["version"])
    except (ValueError, TypeError):
        return False
    return (
        declared[0] == SUPPORTED_RECIPE_VERSION[0] and declared > SUPPORTED_RECIPE_VERSION
    )


def version_scoped_member_errors(recipe: dict[str, Any]) -> list[str]:
    """Members the declared version does not define.

    In a document declaring the version this build implements, an unrecognized
    non-`x-` member is a mistake rather than opaque future data.
    """
    if allows_unknown_members(recipe):
        return []
    errors = []
    for error in version_scoped_validator().iter_errors(recipe):
        if error.validator != "additionalProperties":
            # Everything else is the ordinary schema's business, and reporting
            # it twice would give one fault two categories.
            continue
        if not error.absolute_path and declares_singular_yield(recipe):
            unexpected = set(recipe) - set(error.schema.get("properties", {}))
            if unexpected == {"yield"}:
                continue
        location = ".".join(str(part) for part in error.absolute_path) or "document"
        errors.append(f"{location}: {error.message}, so it is not defined by SREF")
    if declares_singular_yield(recipe):
        for member in ("yields", "nutrition", "dietary_claims", "allergen_declarations"):
            if member in recipe:
                errors.append(f"{member}: added in 0.4.0, so it is not defined by SREF")
    return errors


def declares_singular_yield(recipe: dict[str, Any]) -> bool:
    """A document that declares a version before 0.4.0 carries one `yield`, not `yields`."""
    header = recipe.get("sref")
    try:
        return parse_version(header["version"]) < (0, 4, 0)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def allows_unknown_unit_ids(recipe: dict[str, Any]) -> bool:
    header = recipe.get("sref")
    if not isinstance(header, dict) or "unit_registry" not in header:
        return False
    declared = parse_version(header["unit_registry"])
    return (
        declared[0] == SUPPORTED_REGISTRY_VERSION[0]
        and declared > SUPPORTED_REGISTRY_VERSION
    )


def rational(value: str) -> Fraction:
    if "/" not in value:
        numerator = int(value)
        if numerator > UINT64_MAX:
            raise ValueError("rational numerator exceeds unsigned 64-bit range")
        return Fraction(numerator, 1)
    numerator_text, denominator_text = value.split("/", 1)
    numerator = int(numerator_text)
    denominator = int(denominator_text)
    if denominator <= 1:
        raise ValueError("fraction denominator must exceed one")
    if numerator <= 0:
        raise ValueError("fraction numerator must be positive")
    if numerator > UINT64_MAX:
        raise ValueError("rational numerator exceeds unsigned 64-bit range")
    if denominator > UINT64_MAX:
        raise ValueError("rational denominator exceeds unsigned 64-bit range")
    if math.gcd(numerator, denominator) != 1:
        raise ValueError("fraction must be reduced")
    return Fraction(numerator, denominator)


def signed_rational(value: str) -> Fraction:
    if value == "-0":
        raise ValueError("negative zero is not canonical")
    if value.startswith("-"):
        return -rational(value[1:])
    return rational(value)


def amount_errors(amount: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    try:
        if "value" in amount:
            rational(amount["value"])
        else:
            minimum = rational(amount["min"])
            maximum = rational(amount["max"])
            if minimum > maximum:
                errors.append(f"{location}: range minimum exceeds maximum")
    except (KeyError, ValueError) as exc:
        errors.append(f"{location}: {exc}")
    return errors


def signed_amount_errors(amount: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    try:
        if "value" in amount:
            signed_rational(amount["value"])
        else:
            minimum = signed_rational(amount["min"])
            maximum = signed_rational(amount["max"])
            if minimum > maximum:
                errors.append(f"{location}: range minimum exceeds maximum")
    except (KeyError, ValueError) as exc:
        errors.append(f"{location}: {exc}")
    return errors


def quantity_errors(
    quantity: dict[str, Any],
    location: str,
    unit_ids: set[str],
    allow_unknown_units: bool = False,
) -> list[str]:
    errors: list[str] = []
    kind = quantity.get("kind")
    if kind == "simple":
        errors.extend(amount_errors(quantity["amount"], f"{location}.amount"))
        unit = quantity.get("unit")
        if unit is not None and unit not in unit_ids and not allow_unknown_units:
            errors.append(f"{location}: unknown unit {unit}")
    elif kind == "sum":
        for index, term in enumerate(quantity["terms"]):
            errors.extend(
                quantity_errors(
                    term,
                    f"{location}.terms[{index}]",
                    unit_ids,
                    allow_unknown_units,
                )
            )
    elif kind == "alternatives":
        for index, option in enumerate(quantity["options"]):
            errors.extend(
                quantity_errors(
                    option,
                    f"{location}.options[{index}]",
                    unit_ids,
                    allow_unknown_units,
                )
            )
    return errors


def quantity_unit_ids(quantity: dict[str, Any]) -> list[str]:
    kind = quantity.get("kind")
    if kind == "simple":
        return [quantity["unit"]] if "unit" in quantity else []
    if kind == "sum":
        return [
            unit_id
            for term in quantity["terms"]
            for unit_id in quantity_unit_ids(term)
        ]
    if kind == "alternatives":
        return [
            unit_id
            for option in quantity["options"]
            for unit_id in quantity_unit_ids(option)
        ]
    return []


def temperature_errors(
    temperature: dict[str, Any],
    location: str,
    units: dict[str, dict[str, Any]],
    allow_unknown_units: bool = False,
) -> list[str]:
    if "text" in temperature:
        # The schema makes this branch exclusive with numeric members. Its
        # authored text is authoritative and deliberately has no unit lookup,
        # conversion, or inferred numeric interpretation.
        return []
    errors = signed_amount_errors(temperature["amount"], f"{location}.amount")
    unit_id = temperature["unit"]
    unit = units.get(unit_id)
    if unit is None and not allow_unknown_units:
        errors.append(f"{location}: unknown unit {unit_id}")
    elif unit is not None and (
        unit.get("kind") != "physical" or unit.get("dimension") != "temperature"
    ):
        errors.append(f"{location}: unit {unit_id} is not a temperature unit")
    return errors


def duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def normalized_path_duplicates(values: list[str]) -> set[str]:
    """Paths that collide after portable filesystem normalization.

    NFC closes the composed/decomposed Unicode alias used by filesystems such
    as HFS+, and case folding closes the collision on case-insensitive
    filesystems. The original spelling is returned for a useful diagnostic;
    no unsafe path is rewritten into an accepted one.
    """
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        key = unicodedata.normalize("NFC", value).casefold()
        if key in seen:
            repeated.add(value)
        seen.add(key)
    return repeated


def language_tag_errors(value: str, location: str) -> list[str]:
    if value.casefold() not in BCP47_GRANDFATHERED and not BCP47_RE.fullmatch(value):
        return [f"{location}: invalid BCP 47 language tag {value!r}"]
    return []


def control_character_errors(value: Any, location: str = "document") -> list[str]:
    errors: list[str] = []
    if isinstance(value, str):
        for character in value:
            codepoint = ord(character)
            if codepoint < 0x20 and character not in {"\t", "\n", "\r"}:
                errors.append(
                    f"{location}: prohibited C0 control character U+{codepoint:04X}"
                )
                break
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(control_character_errors(item, f"{location}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(control_character_errors(key, f"{location} member name"))
            errors.extend(control_character_errors(item, f"{location}.{key}"))
    return errors


# A variant preserves authored content; it may not nest or embed a recipe.
VARIANT_RECIPE_MEMBERS = (
    "ingredient_sections",
    "instruction_sections",
    "yields",
    "nutrition",
    "times",
)


def variant_errors(recipe: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    variants = recipe.get("variants")
    if not isinstance(variants, list):
        return errors
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            continue
        label = variant.get("title") or f"index {index}"
        if "variants" in variant:
            errors.append(f"variant {label} must not contain nested variants")
        embedded = sorted(
            member for member in VARIANT_RECIPE_MEMBERS if member in variant
        )
        if embedded:
            errors.append(
                f"variant {label} must not restructure the recipe: "
                + ", ".join(embedded)
            )
    return errors


def microwave_power_errors(power: dict[str, Any], location: str) -> list[str]:
    """Validate numeric microwave-power meaning that JSON Schema cannot express."""
    errors: list[str] = []
    if "percent" in power:
        try:
            value = rational(power["percent"])
        except ValueError as exc:
            return [f"{location}: {exc}"]
        if value <= 0 or value > 100:
            errors.append(
                f"{location}: power percent must be greater than 0 and at most 100"
            )
    return errors


def microwave_errors(microwave: dict[str, Any], location: str) -> list[str]:
    """Validate one source-authored microwave annotation and its schedule."""
    errors: list[str] = []
    power = microwave.get("power")
    if power is not None:
        errors.extend(microwave_power_errors(power, f"{location}.power"))

    choices = microwave.get("choices", [])
    if choices and ("rated_output_watts" in microwave or "power" in microwave):
        errors.append(
            f"{location}: choice schedule must not also carry shared rated output or power"
        )

    seen: set[str] = set()
    for index, choice in enumerate(choices):
        choice_power = choice.get("power")
        if choice_power is not None:
            errors.extend(
                microwave_power_errors(choice_power, f"{location}.choices[{index}].power")
            )
        condition = json.dumps(
            {
                key: choice[key]
                for key in ("rated_output_watts", "power")
                if key in choice
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        if condition in seen:
            errors.append(f"{location}: duplicate microwave choice conditions")
        seen.add(condition)
    return errors


def translation_errors(recipe: dict[str, Any]) -> list[str]:
    """Validate declared translation relationships (section 6.9)."""
    translations = recipe.get("translations", [])
    if not translations:
        return []
    errors: list[str] = []
    if "language" not in recipe:
        errors.append("translations require the recipe's own language")
    originals = 0
    for index, translation in enumerate(translations):
        location = f"translations[{index}]"
        errors.extend(language_tag_errors(translation["language"], f"{location}.language"))
        if translation["relation"] == "original":
            originals += 1
        if translation.get("recipe_id") == recipe["id"]:
            errors.append(f"{location}: translation refers to this recipe's own ID")
    if originals > 1:
        errors.append("more than one translation original")
    return errors


def claim_errors(recipe: dict[str, Any]) -> list[str]:
    """Validate variant IDs and the claims scoped to them (sections 6.7, 6.11)."""
    errors: list[str] = []
    variant_ids = [
        variant["id"]
        for variant in recipe.get("variants", [])
        if isinstance(variant, dict) and "id" in variant
    ]
    for repeated in duplicates(variant_ids):
        errors.append(f"duplicate variant ID {repeated}")
    known = set(variant_ids)
    for member in ("dietary_claims", "allergen_declarations"):
        for index, claim in enumerate(recipe.get(member, [])):
            reference = claim.get("variant_ref")
            if reference is not None and reference not in known:
                errors.append(f"{member}[{index}]: dangling variant reference {reference}")
    return errors


def nutrition_errors(
    recipe: dict[str, Any], units: dict[str, dict[str, Any]], allow_unknown_units: bool
) -> list[str]:
    """Validate authored nutrition statements (section 6.10)."""
    errors: list[str] = []
    for index, statement in enumerate(recipe.get("nutrition", [])):
        location = f"nutrition[{index}]"
        quantity = statement["basis"].get("quantity")
        if quantity is not None:
            errors.extend(
                bounded_quantity_errors(
                    quantity, f"{location}.basis.quantity", units, allow_unknown_units,
                    "nutrition basis",
                )
            )
        seen: set[tuple[str, str]] = set()
        for nutrient_index, nutrient in enumerate(statement["nutrients"]):
            nutrient_location = f"{location}.nutrients[{nutrient_index}]"
            if "amount" in nutrient:
                errors.extend(amount_errors(nutrient["amount"], nutrient_location))
            identity = (nutrient["nutrient"], nutrient.get("label", ""))
            if identity in seen:
                errors.append(f"{nutrient_location}: duplicate nutrient {identity[0]}")
            seen.add(identity)
    return errors


def bounded_quantity_errors(
    quantity: dict[str, Any],
    location: str,
    units: dict[str, dict[str, Any]],
    allow_unknown_units: bool,
    subject: str,
) -> list[str]:
    errors = quantity_errors(quantity, location, set(units), allow_unknown_units)
    for unit_id in quantity_unit_ids(quantity):
        unit = units.get(unit_id)
        if unit is not None and unit.get("dimension") == "temperature":
            errors.append(f"{location}: temperature unit {unit_id} cannot describe {subject}")
    return errors


def recipe_semantic_errors(
    recipe: dict[str, Any], units: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    unit_ids = set(units)
    allow_unknown_units = allows_unknown_unit_ids(recipe)
    errors.extend(control_character_errors(recipe))
    errors.extend(version_scoped_member_errors(recipe))

    header = recipe.get("sref")
    if isinstance(header, dict):
        recipe_version_error = supported_version_error(
            header["version"], SUPPORTED_RECIPE_VERSION, "recipe"
        )
        if recipe_version_error is not None:
            errors.append(recipe_version_error)
        registry_version_error = supported_version_error(
            header["unit_registry"], SUPPORTED_REGISTRY_VERSION, "unit-registry"
        )
        if registry_version_error is not None:
            errors.append(registry_version_error)

    for field in ("language", "source_locale"):
        if field in recipe:
            errors.extend(language_tag_errors(recipe[field], field))

    errors.extend(variant_errors(recipe))
    errors.extend(translation_errors(recipe))
    errors.extend(claim_errors(recipe))
    errors.extend(nutrition_errors(recipe, units, allow_unknown_units))

    for index, equipment in enumerate(recipe.get("equipment", [])):
        quantity = equipment.get("quantity")
        if quantity is None:
            continue
        location = f"equipment[{index}].quantity"
        errors.extend(
            quantity_errors(quantity, location, unit_ids, allow_unknown_units)
        )
        for unit_id in quantity_unit_ids(quantity):
            unit = units.get(unit_id)
            if unit is not None and unit.get("dimension") == "temperature":
                errors.append(
                    f"{location}: temperature unit {unit_id} cannot describe "
                    "equipment quantity"
                )

    ingredient_section_ids = [section["id"] for section in recipe.get("ingredient_sections", [])]
    for repeated in duplicates(ingredient_section_ids):
        errors.append(f"duplicate ingredient section ID {repeated}")

    ingredients = [
        ingredient
        for section in recipe.get("ingredient_sections", [])
        for ingredient in section["ingredients"]
    ]
    choice_ids = {ingredient["id"] for ingredient in ingredients if "alternatives" in ingredient}
    ingredients += [branch for ingredient in ingredients for branch in ingredient.get("alternatives", [])]
    ingredient_ids = [ingredient["id"] for ingredient in ingredients]
    ingredient_id_set = set(ingredient_ids)
    for repeated in duplicates(ingredient_ids):
        errors.append(f"duplicate ingredient ID {repeated}")

    for ingredient in ingredients:
        location = f"ingredient {ingredient['id']}"
        if "quantity" in ingredient:
            errors.extend(
                quantity_errors(
                    ingredient["quantity"],
                    location,
                    unit_ids,
                    allow_unknown_units,
                )
            )
            for unit_id in quantity_unit_ids(ingredient["quantity"]):
                unit = units.get(unit_id)
                if unit is not None and unit.get("dimension") == "temperature":
                    errors.append(
                        f"{location}: temperature unit {unit_id} cannot be an "
                        "ingredient quantity"
                    )
        if "package_size" in ingredient:
            errors.extend(
                quantity_errors(
                    ingredient["package_size"],
                    f"{location}.package_size",
                    unit_ids,
                    allow_unknown_units,
                )
            )
            package_unit_id = ingredient["package_size"]["unit"]
            package_unit = units.get(package_unit_id)
            if package_unit is not None and package_unit.get("kind") != "physical":
                errors.append(
                    f"{location}.package_size: unit {package_unit_id} is not physical"
                )
            elif package_unit is not None and package_unit.get("dimension") == "temperature":
                errors.append(
                    f"{location}.package_size: temperature unit {package_unit_id} "
                    "cannot describe package size"
                )
        reference = ingredient.get("recipe")
        if isinstance(reference, dict) and reference.get("recipe_id") == recipe["id"]:
            errors.append(f"{location}: recipe dependency refers to this recipe's own ID")
        if "temperature" in ingredient:
            errors.extend(
                temperature_errors(
                    ingredient["temperature"],
                    f"{location}.temperature",
                    units,
                    allow_unknown_units,
                )
            )

    instruction_section_ids = [
        section["id"] for section in recipe.get("instruction_sections", [])
    ]
    for repeated in duplicates(instruction_section_ids):
        errors.append(f"duplicate instruction section ID {repeated}")

    steps = [
        step
        for section in recipe.get("instruction_sections", [])
        for step in section["steps"]
    ]
    step_ids = [step["id"] for step in steps]
    for repeated in duplicates(step_ids):
        errors.append(f"duplicate step ID {repeated}")

    timings = recipe.get("times", {}).get("assertions", [])
    timing_ids = [timing["id"] for timing in timings]
    timing_id_set = set(timing_ids)
    for repeated in duplicates(timing_ids):
        errors.append(f"duplicate timing ID {repeated}")
    for timing in timings:
        microwave = timing.get("microwave")
        if microwave is not None:
            errors.extend(microwave_errors(microwave, f"timing {timing['id']}.microwave"))

    for step in steps:
        ingredient_uses = step.get("ingredient_uses", [])
        ingredient_references = [
            ingredient_use["ingredient_ref"] for ingredient_use in ingredient_uses
        ]
        for repeated in duplicates(ingredient_references):
            errors.append(
                f"step {step['id']}: duplicate ingredient reference {repeated}"
            )
        for index, ingredient_use in enumerate(ingredient_uses):
            reference = ingredient_use["ingredient_ref"]
            if reference not in ingredient_id_set:
                errors.append(
                    f"step {step['id']}: dangling ingredient reference {reference}"
                )
            quantity = ingredient_use.get("quantity")
            if quantity is not None and reference in choice_ids:
                errors.append(f"step {step['id']}: whole-choice use cannot carry quantity")
            if quantity is not None:
                location = f"step {step['id']}.ingredient_uses[{index}].quantity"
                errors.extend(
                    quantity_errors(
                        quantity,
                        location,
                        unit_ids,
                        allow_unknown_units,
                    )
                )
                for unit_id in quantity_unit_ids(quantity):
                    unit = units.get(unit_id)
                    if unit is not None and unit.get("dimension") == "temperature":
                        errors.append(
                            f"{location}: temperature unit {unit_id} cannot be an "
                            "ingredient-use quantity"
                        )
        for reference in step.get("timing_refs", []):
            if reference not in timing_id_set:
                errors.append(
                    f"step {step['id']}: dangling timing reference {reference}"
                )
        for index, temperature in enumerate(step.get("temperatures", [])):
            errors.extend(
                temperature_errors(
                    temperature,
                    f"step {step['id']}.temperatures[{index}]",
                    units,
                    allow_unknown_units,
                )
            )

    assets = recipe.get("assets", [])
    asset_ids = [asset["id"] for asset in assets]
    asset_paths = [asset["path"] for asset in assets]
    for repeated in duplicates(asset_ids):
        errors.append(f"duplicate asset ID {repeated}")
    for repeated in normalized_path_duplicates(asset_paths):
        errors.append(f"duplicate asset path {repeated}")
    for asset in assets:
        errors.extend(path_errors(asset["path"], f"asset {asset['id']}"))

    assets_by_id = {asset["id"]: asset for asset in assets}
    for step in steps:
        for reference in step.get("image_refs", []):
            asset = assets_by_id.get(reference)
            if asset is None:
                errors.append(
                    f"step {step['id']}: dangling step image reference {reference}"
                )
            elif not asset["media_type"].startswith("image/"):
                errors.append(
                    f"step {step['id']}: step image {reference} is not an image"
                )

    recipe_image_refs = recipe.get("image_refs", [])
    for reference in recipe_image_refs:
        asset = assets_by_id.get(reference)
        if asset is None:
            errors.append(f"dangling recipe image reference {reference}")
        elif not asset["media_type"].startswith("image/"):
            errors.append(f"recipe image {reference} is not an image")

    primary_image = recipe.get("primary_image")
    if primary_image is not None:
        matches = [asset for asset in assets if asset["id"] == primary_image]
        if not matches:
            errors.append(f"primary image {primary_image} does not resolve")
        elif not matches[0]["media_type"].startswith("image/"):
            errors.append(f"primary image {primary_image} is not an image")
        elif primary_image not in recipe_image_refs:
            errors.append(
                f"primary image {primary_image} is not present in recipe image_refs"
            )

    singular = [recipe["yield"]] if declares_singular_yield(recipe) and "yield" in recipe else []
    for index, assertion in enumerate(singular + recipe.get("yields", [])):
        if "quantity" in assertion:
            errors.extend(
                bounded_quantity_errors(
                    assertion["quantity"], f"yields[{index}]", units, allow_unknown_units,
                    "recipe yield",
                )
            )

    return errors


def registry_semantic_errors(unit_registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(control_character_errors(unit_registry, "unit registry"))
    units = {unit["id"]: unit for unit in unit_registry["units"]}
    if len(units) != len(unit_registry["units"]):
        errors.append("unit registry contains duplicate IDs")

    base_units_by_dimension: dict[str, list[str]] = {}

    for unit_id, unit in units.items():
        if unit.get("status") == "active" and not unit.get("aliases"):
            errors.append(f"{unit_id}: active unit has no parsing aliases")
        if unit.get("kind") == "physical" and not unit.get("references"):
            errors.append(f"{unit_id}: physical unit has no reference")

        definition = unit.get("definition")
        if definition is not None and definition["kind"] == "base":
            base_units_by_dimension.setdefault(unit["dimension"], []).append(unit_id)

        alias_set_keys: list[str] = []
        for language in unit.get("labels", {}):
            errors.extend(language_tag_errors(language, f"{unit_id}.labels"))

        for alias_index, alias_set in enumerate(unit.get("aliases", [])):
            alias_set_keys.append(
                f"{alias_set['language'].casefold()}:{alias_set['case_sensitive']}"
            )
            errors.extend(
                language_tag_errors(
                    alias_set["language"], f"{unit_id}.aliases[{alias_index}].language"
                )
            )
            forms = alias_set["forms"]
            for form in forms:
                if unicodedata.normalize("NFC", form) != form or form != form.strip():
                    errors.append(
                        f"{unit_id}.aliases[{alias_index}]: alias {form!r} is not "
                        "NFC or has surrounding whitespace"
                    )
            comparison_forms = [
                match_key(form, alias_set["case_sensitive"]) for form in forms
            ]
            for repeated in duplicates(comparison_forms):
                errors.append(
                    f"{unit_id}.aliases[{alias_index}]: duplicate normalized alias "
                    f"{repeated!r}"
                )
        for repeated in duplicates(alias_set_keys):
            errors.append(f"{unit_id}: duplicate alias set {repeated}")

        if unit.get("status") == "deprecated":
            replacement = unit.get("replacement")
            if replacement not in units:
                errors.append(f"{unit_id}: replacement does not exist")
            elif replacement == unit_id:
                errors.append(f"{unit_id}: replacement refers to itself")
            elif units[replacement].get("status") != "active":
                errors.append(f"{unit_id}: replacement is not active")
        elif "replacement" in unit:
            errors.append(f"{unit_id}: active unit cannot declare a replacement")

        if definition is None or definition["kind"] == "base":
            continue

        if definition["kind"] == "affine" and unit.get("dimension") != "temperature":
            errors.append(f"{unit_id}: affine conversion is limited to temperature")

        base_id = definition["base_unit"]
        base = units.get(base_id)
        if base is None:
            errors.append(f"{unit_id}: base unit {base_id} does not exist")
        else:
            if base.get("kind") != "physical":
                errors.append(f"{unit_id}: base unit is not physical")
            if base.get("dimension") != unit.get("dimension"):
                errors.append(f"{unit_id}: base unit has a different dimension")
            if base.get("definition", {}).get("kind") != "base":
                errors.append(f"{unit_id}: conversion must target a dimension base unit")

        try:
            multiplier = signed_rational(definition["multiplier"])
            if multiplier <= 0:
                errors.append(f"{unit_id}: conversion multiplier must be positive")
            if "offset" in definition:
                signed_rational(definition["offset"])
        except ValueError as exc:
            errors.append(f"{unit_id}: {exc}")

    for unit_id in units:
        visited: set[str] = set()
        cursor = unit_id
        while True:
            definition = units[cursor].get("definition")
            if definition is None or definition["kind"] == "base":
                break
            cursor = definition["base_unit"]
            if cursor not in units:
                break
            if cursor in visited or cursor == unit_id:
                errors.append(f"{unit_id}: conversion cycle")
                break
            visited.add(cursor)

    physical_dimensions = {
        unit["dimension"]
        for unit in units.values()
        if unit.get("kind") == "physical"
    }
    for dimension in physical_dimensions:
        bases = base_units_by_dimension.get(dimension, [])
        if len(bases) != 1:
            errors.append(
                f"{dimension}: expected exactly one physical base unit, found {len(bases)}"
            )

    return errors



def match_key(value: str, case_sensitive: bool) -> str:
    """The text alias comparison sees.

    Both sides are put in canonical composition (NFC), so a composed and a
    decomposed spelling of one form match. A case-insensitive set additionally
    compares under Unicode case folding. Compatibility mappings, accent
    stripping, and script conversion are never applied.
    """
    composed = unicodedata.normalize("NFC", value)
    return composed if case_sensitive else composed.casefold()


def alias_owners(units: dict[str, Any], form: str) -> set[str]:
    """Every registered unit that names `form`, in any locale.

    This is candidate discovery, not lookup. Section 9.5 keeps the two apart:
    enumerating what a written form could mean is what makes a decision
    offerable, and it never authorizes selecting a sibling locale on its own.
    """
    owners: set[str] = set()
    for unit_id, unit in units.items():
        for alias_set in unit.get("aliases", []):
            sensitive = alias_set["case_sensitive"]
            for registered in alias_set["forms"]:
                if match_key(registered, sensitive) == match_key(form, sensitive):
                    owners.add(unit_id)
    return owners


def locale_chain(locale: str) -> list[str]:
    """The RFC 4647 lookup chain of docs/quantity-and-units.md."""
    parts = locale.split("-")
    chain = []
    while parts:
        chain.append("-".join(parts))
        parts = parts[:-1]
        if len(parts) > 1 and len(parts[-1]) == 1:
            parts = parts[:-1]
    return chain


def locale_lookup(units: dict[str, Any], form: str, locale: str) -> str | None:
    """Section 9.2 lookup: the first level with candidates supplies all of them.

    A level that produces more than one candidate is ambiguous and resolves to
    nothing; a less specific level never joins or replaces it.
    """
    if not locale:
        return None
    for level in locale_chain(locale):
        candidates = set()
        for unit_id, unit in units.items():
            for alias_set in unit.get("aliases", []):
                if alias_set["language"].casefold() != level.casefold():
                    continue
                sensitive = alias_set["case_sensitive"]
                for registered in alias_set["forms"]:
                    if match_key(registered, sensitive) == match_key(form, sensitive):
                        candidates.add(unit_id)
        if candidates:
            return next(iter(candidates)) if len(candidates) == 1 else None
    return None


def resolution_result(
    case: dict[str, Any],
    units: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Apply specification section 9.5 to one resolution vector.

    The precedence is the specification's, in its order: an explicit source
    meaning first because a decision may not override one, then an occurrence
    interpretation, then an ingredient convention, then the locale lookup of
    section 9.2. A contradictory context is reported rather than settled by
    answer order, so conflict detection precedes all of it.
    """
    interpretations: dict[str, str] = {}
    conventions: dict[str, str] = {}
    for decision in case.get("decisions", []):
        if decision["kind"] == "occurrence-interpretation":
            held = interpretations.get(decision["occurrence"])
            if held is not None and held != decision["unit"]:
                return {"outcome": "conflict", "conflict": "occurrence"}
            interpretations[decision["occurrence"]] = decision["unit"]
        else:
            held = conventions.get(decision["ingredient"])
            if held is not None and held != decision["profile"]:
                return {"outcome": "conflict", "conflict": "convention"}
            conventions[decision["ingredient"]] = decision["profile"]

    resolved: dict[str, Any] = {}
    for occurrence in case["occurrences"]:
        resolved[occurrence["id"]] = resolve_occurrence(
            occurrence, case.get("source_locale", ""), interpretations, conventions,
            units, profiles,
        )
    return {"outcome": "resolved", "units": resolved}


def resolve_occurrence(
    occurrence: dict[str, Any],
    locale: str,
    interpretations: dict[str, str],
    conventions: dict[str, str],
    units: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> str | None:
    explicit = occurrence.get("explicit_unit")
    if explicit is not None:
        return explicit

    chosen = interpretations.get(occurrence["id"])
    if chosen is not None:
        return chosen

    profile_id = conventions.get(occurrence["ingredient"])
    if profile_id is not None:
        selected = profiles[profile_id]["units"].get(occurrence["family"])
        if selected is not None:
            return selected

        # Inside an explicit convention scope, a contested family the profile
        # does not cover stays unresolved rather than falling back to the
        # locale, which would mix conventions in one ingredient. Uncontested
        # units keep resolving from their own evidence.
        if contested_family(units, occurrence["family"]):
            return None

    return locale_lookup(units, occurrence["form"], locale)


def contested_family(units: dict[str, Any], family: str) -> bool:
    """Whether more than one registered identity answers for this measure.

    `volume.cup` is contested; `mass.gram` is not, because nothing else is
    called a gram.
    """
    answers = 0
    for unit_id in units:
        if unit_id == family or unit_id.startswith(family + "."):
            answers += 1
    return answers > 1


def resolution_corpus_errors(
    corpus: dict[str, Any], units: dict[str, Any]
) -> list[str]:
    """Check the corpus against the registry and against its own expectations."""
    errors: list[str] = []
    registry_version = corpus["unit_registry"]
    profiles: dict[str, dict[str, Any]] = {}
    for profile in corpus["profiles"]:
        if profile["id"] in profiles:
            errors.append(f"{profile['id']}: duplicate profile")
        profiles[profile["id"]] = profile
        if profile["unit_registry"] != registry_version:
            errors.append(f"{profile['id']}: profile names another registry version")
        for family, unit_id in profile["units"].items():
            if unit_id not in units:
                errors.append(f"{profile['id']}: {unit_id} is not a registered unit")
            elif not (unit_id == family or unit_id.startswith(family + ".")):
                errors.append(
                    f"{profile['id']}: {unit_id} does not belong to family {family}"
                )

    seen: set[str] = set()
    for case in corpus["cases"]:
        if case["id"] in seen:
            errors.append(f"{case['id']}: duplicate case ID")
        seen.add(case["id"])
        if "source_locale" in case:
            errors.extend(
                language_tag_errors(case["source_locale"], f"{case['id']}.source_locale")
            )
        errors.extend(control_character_errors(case, f"resolution.{case['id']}"))

        occurrences = {occurrence["id"]: occurrence for occurrence in case["occurrences"]}
        if len(occurrences) != len(case["occurrences"]):
            errors.append(f"{case['id']}: duplicate occurrence ID")
        for occurrence in case["occurrences"]:
            explicit = occurrence.get("explicit_unit")
            if explicit is not None and explicit not in units:
                errors.append(f"{case['id']}: {explicit} is not a registered unit")
            owners = alias_owners(units, occurrence["form"])
            if not owners:
                errors.append(
                    f"{case['id']}: {occurrence['form']!r} is not a registry alias"
                )
        for decision in case.get("decisions", []):
            if decision["kind"] == "occurrence-interpretation":
                if decision["occurrence"] not in occurrences:
                    errors.append(
                        f"{case['id']}: an interpretation addresses no occurrence"
                    )
                    continue
                form = occurrences[decision["occurrence"]]["form"]
                # A decision selects among the interpretations the registry
                # already associates with the authored form. It cannot rename
                # a measure into a unit the source never wrote.
                if decision["unit"] not in alias_owners(units, form):
                    errors.append(
                        f"{case['id']}: {decision['unit']} is not an interpretation "
                        f"of {form!r}"
                    )
            elif decision["profile"] not in profiles:
                errors.append(f"{case['id']}: a convention names no profile")

        expected = case["expected"]
        actual = resolution_result(case, units, profiles)
        if actual != expected:
            errors.append(f"{case['id']}: expected {expected}, resolved {actual}")
        if expected["outcome"] == "resolved":
            if set(expected["units"]) != set(occurrences):
                errors.append(f"{case['id']}: expectation does not cover every occurrence")
            for unit_id in expected["units"].values():
                if unit_id is not None and unit_id not in units:
                    errors.append(f"{case['id']}: {unit_id} is not a registered unit")

    return errors

def fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def convert_value(
    value: Fraction,
    source: dict[str, Any],
    target: dict[str, Any],
) -> Fraction:
    source_definition = source["definition"]
    target_definition = target["definition"]

    source_multiplier = Fraction(1)
    source_offset = Fraction(0)
    if source_definition["kind"] != "base":
        source_multiplier = signed_rational(source_definition["multiplier"])
        source_offset = signed_rational(source_definition.get("offset", "0"))

    target_multiplier = Fraction(1)
    target_offset = Fraction(0)
    if target_definition["kind"] != "base":
        target_multiplier = signed_rational(target_definition["multiplier"])
        target_offset = signed_rational(target_definition.get("offset", "0"))

    base_value = value * source_multiplier + source_offset
    return (base_value - target_offset) / target_multiplier


def conversion_result(
    case: dict[str, Any], units: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    source = units.get(case["source_unit"])
    target = units.get(case["target_unit"])
    if source is None or target is None:
        return {"error": "unknown-unit"}
    if source.get("kind") != "physical" or target.get("kind") != "physical":
        return {"error": "nonphysical-unit"}
    if source.get("dimension") != target.get("dimension"):
        return {"error": "incompatible-dimension"}

    input_amount = case["input"]
    input_errors = signed_amount_errors(input_amount, case["id"])
    if input_errors:
        raise AssertionError("; ".join(input_errors))

    source_exact = source["definition"].get("exact", True)
    target_exact = target["definition"].get("exact", True)
    approximate = (
        input_amount.get("approximate", False)
        or not source_exact
        or not target_exact
    )

    if "value" in input_amount:
        converted_amount: dict[str, Any] = {
            "value": fraction_text(
                convert_value(signed_rational(input_amount["value"]), source, target)
            )
        }
    else:
        converted_amount = {
            "min": fraction_text(
                convert_value(signed_rational(input_amount["min"]), source, target)
            ),
            "max": fraction_text(
                convert_value(signed_rational(input_amount["max"]), source, target)
            ),
        }
    if approximate:
        converted_amount["approximate"] = True
    return {"amount": converted_amount, "approximate": approximate}


def path_errors(path: str, location: str) -> list[str]:
    errors: list[str] = []
    if len(path) > MAX_PATH_LENGTH:
        errors.append(f"{location}: path exceeds length limit {MAX_PATH_LENGTH}")
    if "\\" in path:
        errors.append(f"{location}: backslash in path")
    if path.startswith("/"):
        errors.append(f"{location}: absolute path")
    if re.match(r"^[A-Za-z]:", path):
        errors.append(f"{location}: drive-letter path")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        errors.append(f"{location}: control character in path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        errors.append(f"{location}: unsafe path segment")
    if not path.startswith("assets/"):
        errors.append(f"{location}: asset path must start with assets/")
    return errors


def validate_package(
    path: Path,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    if path.stat().st_size > MAX_PACKAGE_BYTES:
        return ["package exceeds compressed-byte limit"]
    return validate_package_bytes(
        path.read_bytes(), recipe_validator, manifest_validator, units
    )


def validate_package_bytes(
    data: bytes,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate untrusted package bytes without leaking archive exceptions."""
    try:
        return _validate_package_bytes(
            data, recipe_validator, manifest_validator, units
        )
    except (EOFError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        return [f"invalid ZIP package: {exc}"]


def _validate_package_bytes(
    data: bytes,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if len(data) > MAX_PACKAGE_BYTES:
        return ["package exceeds compressed-byte limit"]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]

        if len(infos) > MAX_ARCHIVE_ENTRIES:
            errors.append("package exceeds archive-entry limit")
        expanded_size = sum(info.file_size for info in infos)
        if expanded_size > MAX_EXPANDED_BYTES:
            errors.append("package exceeds expanded-byte limit")
        for info in infos:
            if info.file_size > MAX_ENTRY_BYTES:
                errors.append(f"archive entry {info.filename} exceeds byte limit")
            if (
                info.file_size > 0
                and info.compress_size > 0
                and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                errors.append(
                    f"archive entry {info.filename} exceeds compression-ratio limit"
                )

        for repeated in normalized_path_duplicates(names):
            errors.append(f"duplicate archive entry {repeated}")

        for info in infos:
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if mode and not stat.S_ISREG(mode):
                errors.append(f"nonregular archive entry {info.filename}")
            if info.flag_bits & 0x1:
                errors.append(f"encrypted archive entry {info.filename}")
            if info.filename not in {"recipe.json", "manifest.json"}:
                errors.extend(path_errors(info.filename, f"archive entry {info.filename}"))

        # A duplicate is already reported above; do not report it as absent.
        if "recipe.json" not in names:
            errors.append("archive must contain exactly one recipe.json")
        if "manifest.json" not in names:
            errors.append("archive must contain exactly one manifest.json")
        if errors:
            return errors

        recipe_bytes = archive.read("recipe.json")
        manifest_bytes = archive.read("manifest.json")
        if len(recipe_bytes) > MAX_JSON_BYTES:
            return ["recipe.json exceeds JSON byte limit"]
        if len(manifest_bytes) > MAX_JSON_BYTES:
            return ["manifest.json exceeds JSON byte limit"]
        try:
            recipe = load_json_bytes(recipe_bytes)
            manifest = load_json_bytes(manifest_bytes)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            DuplicateKeyError,
            NonFiniteNumberError,
            JSONDepthError,
            JSONNumberLimitError,
        ) as exc:
            return [f"invalid package JSON: {exc}"]

        errors.extend(str(error) for error in recipe_validator.iter_errors(recipe))
        errors.extend(str(error) for error in manifest_validator.iter_errors(manifest))
        if errors:
            return errors

        errors.extend(recipe_semantic_errors(recipe, units))

        recipe_entry = manifest["recipe"]
        if recipe_entry["size"] != len(recipe_bytes):
            errors.append("recipe size mismatch")
        if recipe_entry["sha256"] != hashlib.sha256(recipe_bytes).hexdigest():
            errors.append("recipe digest mismatch")

        recipe_assets = {asset["id"]: asset for asset in recipe.get("assets", [])}
        manifest_assets = {asset["id"]: asset for asset in manifest["assets"]}
        manifest_asset_ids = [asset["id"] for asset in manifest["assets"]]
        manifest_asset_paths = [asset["path"] for asset in manifest["assets"]]
        for repeated in duplicates(manifest_asset_ids):
            errors.append(f"duplicate manifest asset ID {repeated}")
        for repeated in normalized_path_duplicates(manifest_asset_paths):
            errors.append(f"duplicate manifest asset path {repeated}")
        if recipe_assets.keys() != manifest_assets.keys():
            errors.append("recipe and manifest asset IDs differ")

        declared_paths = {"recipe.json", "manifest.json"}
        for asset_id, recipe_asset in recipe_assets.items():
            manifest_asset = manifest_assets.get(asset_id)
            if manifest_asset is None:
                continue
            for field in ("path", "media_type", "sha256", "size"):
                if recipe_asset[field] != manifest_asset[field]:
                    errors.append(f"asset {asset_id}: {field} differs from manifest")
            asset_path = recipe_asset["path"]
            declared_paths.add(asset_path)
            if asset_path not in names:
                errors.append(f"missing asset entry {asset_path}")
                continue
            data = archive.read(asset_path)
            if len(data) != recipe_asset["size"]:
                errors.append(f"asset {asset_id}: size mismatch")
            if hashlib.sha256(data).hexdigest() != recipe_asset["sha256"]:
                errors.append(f"asset {asset_id}: digest mismatch")

        undeclared = set(names) - declared_paths
        for name in sorted(undeclared):
            errors.append(f"undeclared archive entry {name}")

    return errors


def bundle_path_errors(path: str, location: str) -> list[str]:
    errors: list[str] = []
    if len(path) > MAX_PATH_LENGTH:
        errors.append(f"{location}: path exceeds length limit {MAX_PATH_LENGTH}")
    if "\\" in path:
        errors.append(f"{location}: backslash in path")
    if path.startswith("/"):
        errors.append(f"{location}: absolute path")
    if re.match(r"^[A-Za-z]:", path):
        errors.append(f"{location}: drive-letter path")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        errors.append(f"{location}: control character in path")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        errors.append(f"{location}: unsafe path segment")
    if not path.startswith("recipes/"):
        errors.append(f"{location}: bundle member path must start with recipes/")
    return errors


def validate_bundle(
    path: Path,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    bundle_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate an untrusted bundle without leaking archive exceptions."""
    try:
        return _validate_bundle(
            path, recipe_validator, manifest_validator, bundle_validator, units
        )
    except (EOFError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        return [f"invalid ZIP bundle: {exc}"]


def _validate_bundle(
    path: Path,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    bundle_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    """Checks a bundle as a container and every member as a package in its own
    right. A member whose digest matches is not thereby a valid package, so the
    two checks are both performed and are reported separately."""
    errors: list[str] = []
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        return ["bundle exceeds compressed-byte limit"]
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]

        if len(infos) > MAX_BUNDLE_MEMBERS + 1:
            errors.append("bundle exceeds member limit")
        if sum(info.file_size for info in infos) > MAX_EXPANDED_BYTES:
            errors.append("bundle exceeds expanded-byte limit")
        for info in infos:
            if info.file_size > MAX_ENTRY_BYTES:
                errors.append(f"bundle entry {info.filename} exceeds byte limit")
            if (
                info.file_size > 0
                and info.compress_size > 0
                and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                errors.append(
                    f"bundle entry {info.filename} exceeds compression-ratio limit"
                )

        for repeated in normalized_path_duplicates(names):
            errors.append(f"duplicate archive entry {repeated}")

        for info in infos:
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if mode and not stat.S_ISREG(mode):
                errors.append(f"nonregular archive entry {info.filename}")
            if info.flag_bits & 0x1:
                errors.append(f"encrypted archive entry {info.filename}")
            if info.filename != "manifest.json":
                errors.extend(
                    bundle_path_errors(info.filename, f"archive entry {info.filename}")
                )

        if "manifest.json" not in names:
            errors.append("bundle must contain exactly one manifest.json")
        if errors:
            return errors

        manifest_bytes = archive.read("manifest.json")
        if len(manifest_bytes) > MAX_JSON_BYTES:
            return ["manifest.json exceeds JSON byte limit"]
        try:
            manifest = load_json_bytes(manifest_bytes)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            DuplicateKeyError,
            NonFiniteNumberError,
            JSONDepthError,
            JSONNumberLimitError,
        ) as exc:
            return [f"invalid bundle JSON: {exc}"]

        errors.extend(str(error) for error in bundle_validator.iter_errors(manifest))
        if errors:
            return errors

        declared = manifest["recipes"]
        for repeated in duplicates([item["member_id"] for item in declared]):
            errors.append(f"duplicate bundle member ID {repeated}")
        for repeated in normalized_path_duplicates([item["path"] for item in declared]):
            errors.append(f"duplicate bundle member path {repeated}")

        declared_paths = {"manifest.json"}
        for item in declared:
            member_id = item["member_id"]
            recipe_id = item["recipe_id"]
            expected = f"recipes/{member_id}.sref"
            declared_paths.add(item["path"])
            if item["path"] != expected:
                # The entry is declared, so it is not also reported as undeclared.
                errors.append(
                    f"bundle member path {item['path']} is not {expected}"
                )
                continue
            if item["path"] not in names:
                errors.append(f"missing bundle member {item['path']}")
                continue
            data = archive.read(item["path"])
            if len(data) != item["size"]:
                errors.append(f"bundle member {member_id}: size mismatch")
                continue
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                errors.append(f"bundle member {member_id}: digest mismatch")
                continue
            member_errors = validate_member(
                data, recipe_id, recipe_validator, manifest_validator, units
            )
            errors.extend(
                f"bundle member {member_id}: {message}" for message in member_errors
            )

        for name in sorted(set(names) - declared_paths):
            errors.append(f"undeclared bundle entry {name}")

    return errors


def validate_member(
    data: bytes,
    declared_recipe_id: str,
    recipe_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    units: dict[str, dict[str, Any]],
) -> list[str]:
    """A member has to stand on its own, so it is validated exactly as a
    standalone package would be, then checked against the identity the bundle
    manifest claims for it."""
    try:
        errors = validate_package_bytes(
            data, recipe_validator, manifest_validator, units
        )
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        return [f"invalid ZIP package: {exc}"]
    if errors:
        return errors
    with zipfile.ZipFile(io.BytesIO(data)) as member:
        document = load_json_bytes(member.read("recipe.json"))
    actual_recipe_id = document.get("id")
    if actual_recipe_id != declared_recipe_id:
        return [
            f"declares recipe {declared_recipe_id} but carries {actual_recipe_id}"
        ]
    return []



# Section 13's extension-name rule, implemented from the prose and tested
# against the schema pattern.
EXTENSION_NAME_CASES = (
    # name, valid, which part of the prose it exercises
    ("x-org.example.thing", True, "two domain labels and one local label"),
    ("x-org.example.foo.bar", True, "more than one local label"),
    ("x-com.example.recipe.display.compact", True, "deep local hierarchy"),
    ("x-sref.spec.round-trip.ordinal", True, "the reserved namespace at depth"),
    ("x-a1.b2.c3", True, "digits in every label"),
    ("x-org.ex-ample.thing", True, "interior hyphens"),
    ("x-org.example", False, "a domain with nothing inside it"),
    ("x-vendor", False, "no reversed domain at all"),
    ("x-", False, "no labels"),
    ("x-org..example.thing", False, "an empty label"),
    ("x-org.-example.thing", False, "a label starting with a hyphen"),
    ("x-org.example-.thing", False, "a label ending with a hyphen"),
    ("x-Org.Example.Thing", False, "uppercase"),
    ("x-org.example.thing.", False, "a trailing separator"),
    ("x-" + "a" * 64 + ".example.thing", False, "a label beyond 63 characters"),
    ("x-org.example." + "a" * 120, False, "a name beyond 128 characters"),
)


def prose_extension_name_valid(name: str) -> bool:
    """Section 13's rule, implemented from the prose rather than the pattern."""
    if not name.startswith("x-"):
        return True
    body = name[2:]
    if not body or len(body) > 128:
        return False
    labels = body.split(".")
    if len(labels) < 3:
        return False
    for label in labels:
        if not label or len(label) > 63:
            return False
        if not all(character.isascii() and (character.islower() or character.isdigit() or character == "-")
                   for character in label):
            return False
        if label[0] == "-" or label[-1] == "-":
            return False
    return True


def extension_name_errors(recipe_schema: dict[str, Any]) -> list[str]:
    pattern = recipe_schema["$defs"]["objectMemberName"]["pattern"]
    compiled = re.compile(pattern)
    errors = []
    for name, expected, exercises in EXTENSION_NAME_CASES:
        prose = prose_extension_name_valid(name)
        schema = bool(compiled.match(name))
        if prose != expected:
            errors.append(f"prose rule rejects {name!r} ({exercises})" if expected
                          else f"prose rule accepts {name!r} ({exercises})")
        if schema != expected:
            errors.append(f"schema pattern rejects {name!r} ({exercises})" if expected
                          else f"schema pattern accepts {name!r} ({exercises})")
        if prose != schema:
            errors.append(
                f"section 13 and objectMemberName disagree about {name!r} ({exercises}): "
                f"prose={prose} schema={schema}"
            )
    return errors

def main() -> int:
    recipe_schema = load_json(ROOT / "schema" / "recipe.schema.json")
    schema_registry = Registry().with_resource(
        recipe_schema["$id"], Resource.from_contents(recipe_schema)
    )

    recipe_validator = validator("recipe.schema.json")
    manifest_validator = validator("manifest.schema.json")
    bundle_validator = validator("bundle-manifest.schema.json")
    registry_validator = validator("unit-registry.schema.json")
    corpus_validator = validator("ingredient-line-corpus.schema.json", schema_registry)
    conversion_validator = validator("unit-conversion-corpus.schema.json")
    resolution_validator = validator("unit-resolution-corpus.schema.json")
    conformance_validator = validator("conformance-manifest.schema.json")

    # The reference reader deliberately rejects bundles above its finite local
    # safety policy, but the format must not make that policy a schema ceiling.
    # This probe is one member beyond the reference limit and would fail if a
    # maxItems constraint were reintroduced.
    schema_limit_probe = {
        "format": "sref-bundle",
        "version": 1,
        "recipes": [
            {
                "member_id": f"r{index:05d}",
                "recipe_id": f"recipe{index:05d}",
                "path": f"recipes/r{index:05d}.sref",
                "sha256": "0" * 64,
                "size": 0,
            }
            for index in range(MAX_BUNDLE_MEMBERS + 1)
        ],
    }
    schema_limit_errors = list(bundle_validator.iter_errors(schema_limit_probe))
    if schema_limit_errors:
        raise AssertionError(
            "bundle schema rejects a manifest above the reference reader limit: "
            + "; ".join(str(error) for error in schema_limit_errors)
        )

    extension_errors = extension_name_errors(recipe_schema)
    if extension_errors:
        raise AssertionError("; ".join(extension_errors))

    unit_registry = load_json(ROOT / "registry" / "units.json")
    registry_validator.validate(unit_registry)
    units = {unit["id"]: unit for unit in unit_registry["units"]}
    registry_errors = registry_semantic_errors(unit_registry)
    if registry_errors:
        raise AssertionError("; ".join(registry_errors))

    conversion_corpus = load_json(ROOT / "tests" / "units" / "conversions.json")
    conversion_validator.validate(conversion_corpus)
    if conversion_corpus["unit_registry"] != unit_registry["version"]:
        raise AssertionError("conversion corpus names a different unit registry")
    conversion_ids = [case["id"] for case in conversion_corpus["cases"]]
    if duplicates(conversion_ids):
        raise AssertionError("conversion corpus contains duplicate case IDs")
    for case in conversion_corpus["cases"]:
        actual = conversion_result(case, units)
        if actual != case["expected"]:
            raise AssertionError(
                f"{case['id']}: expected {case['expected']}, calculated {actual}"
            )

    resolution_corpus = load_json(ROOT / "tests" / "resolution" / "unit-resolution.json")
    resolution_validator.validate(resolution_corpus)
    if resolution_corpus["unit_registry"] != unit_registry["version"]:
        raise AssertionError("resolution corpus names a different unit registry")
    resolution_errors = resolution_corpus_errors(resolution_corpus, units)
    if resolution_errors:
        raise AssertionError("; ".join(resolution_errors))

    corpus = load_json(ROOT / "tests" / "amounts" / "ingredient-lines.json")
    corpus_validator.validate(corpus)
    case_ids = [case["id"] for case in corpus["cases"]]
    if duplicates(case_ids):
        raise AssertionError("ingredient-line corpus contains duplicate case IDs")
    if len({case["source_text"] for case in corpus["cases"]}) != len(corpus["cases"]):
        raise AssertionError("ingredient-line corpus contains duplicate source lines")
    for case in corpus["cases"]:
        if "source_locale" in case:
            locale_errors = language_tag_errors(
                case["source_locale"], f"{case['id']}.source_locale"
            )
            if locale_errors:
                raise AssertionError("; ".join(locale_errors))
        corpus_text_errors = control_character_errors(case, f"corpus.{case['id']}")
        if corpus_text_errors:
            raise AssertionError("; ".join(corpus_text_errors))
        if case["expected"].get("source_text") != case["source_text"]:
            raise AssertionError(f"{case['id']}: expected source text changed")
        semantic_errors = recipe_semantic_errors(
            {
                "ingredient_sections": [
                    {"id": "corpus", "ingredients": [case["expected"]]}
                ],
                "instruction_sections": [
                    {"id": "corpus", "steps": [{"id": "corpus", "text": "test"}]}
                ],
            },
            units,
        )
        if semantic_errors:
            raise AssertionError(f"{case['id']}: {'; '.join(semantic_errors)}")

    manifest = load_json(ROOT / "conformance" / "manifest.json")
    conformance_validator.validate(manifest)
    supported_recipe_text = version_text(SUPPORTED_RECIPE_VERSION)
    supported_registry_text = version_text(SUPPORTED_REGISTRY_VERSION)
    if recipe_schema["$id"] != f"urn:sref:schema:recipe:{supported_recipe_text}":
        raise AssertionError("recipe schema identifier and supported version disagree")
    if manifest["sref_version"] != supported_recipe_text:
        raise AssertionError("conformance manifest and supported recipe version disagree")
    if manifest["unit_registry_version"] != supported_registry_text:
        raise AssertionError(
            "conformance manifest and supported registry version disagree"
        )
    if unit_registry["version"] != supported_registry_text:
        raise AssertionError("unit registry and supported registry version disagree")
    for example_path in sorted((ROOT / "examples").glob("*.recipe.json")):
        example = load_json(example_path)
        if example["sref"] != {
            "version": supported_recipe_text,
            "unit_registry": supported_registry_text,
        }:
            raise AssertionError(
                f"{example_path.relative_to(ROOT)} does not name the released "
                "recipe and registry versions"
            )
    manifest_ids = [case["id"] for case in manifest["cases"]]
    if duplicates(manifest_ids):
        raise AssertionError("conformance manifest contains duplicate case IDs")
    manifest_fixtures = [case["fixture"] for case in manifest["cases"]]
    if duplicates(manifest_fixtures):
        raise AssertionError("conformance manifest contains duplicate fixture paths")

    required_fixtures = {
        "registry/units.json",
        "tests/amounts/ingredient-lines.json",
        "tests/resolution/unit-resolution.json",
        "tests/units/conversions.json",
    }
    for pattern in (
        "examples/*.recipe.json",
        "tests/valid/*.recipe.json",
        "tests/invalid/*.recipe.json",
        "tests/registry/*.json",
        "tests/roundtrip/*.recipe.json",
        "tests/packages/*.sref",
        "tests/bundles/*.srefbundle",
    ):
        required_fixtures.update(
            path.relative_to(ROOT).as_posix() for path in ROOT.glob(pattern)
        )
    unindexed_fixtures = required_fixtures - set(manifest_fixtures)
    if unindexed_fixtures:
        raise AssertionError(
            f"conformance fixtures are not indexed: {sorted(unindexed_fixtures)}"
        )

    failures: list[str] = []
    for case in manifest["cases"]:
        fixture = ROOT / case["fixture"]
        try:
            fixture.resolve().relative_to(ROOT.resolve())
        except ValueError:
            failures.append(f"{case['id']}: fixture escapes repository root")
            continue
        if not fixture.exists():
            failures.append(f"{case['id']}: missing fixture {case['fixture']}")
            continue

        if {"bundle-reader", "bundle-writer"}.intersection(case["capabilities"]):
            try:
                errors = validate_bundle(
                    fixture,
                    recipe_validator,
                    manifest_validator,
                    bundle_validator,
                    units,
                )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                errors = [f"invalid ZIP bundle: {exc}"]
        elif "package-reader" in case["capabilities"]:
            try:
                errors = validate_package(
                    fixture, recipe_validator, manifest_validator, units
                )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                errors = [f"invalid ZIP package: {exc}"]
        elif "ingredient-parser" in case["capabilities"]:
            errors = []
        elif "unit-conversion" in case["capabilities"]:
            errors = []
        elif "unit-resolution" in case["capabilities"]:
            errors = []
        elif "registry" in case["capabilities"] and case["fixture"].startswith(
            ("registry/", "tests/registry/")
        ):
            try:
                document = load_json(fixture)
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                DuplicateKeyError,
                NonFiniteNumberError,
                JSONDepthError,
                JSONNumberLimitError,
            ) as exc:
                errors = [f"invalid JSON: {exc}"]
            else:
                schema_errors = list(registry_validator.iter_errors(document))
                errors = [str(error) for error in schema_errors]
                if not schema_errors:
                    errors.extend(registry_semantic_errors(document))
        else:
            try:
                document = load_json(fixture)
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                DuplicateKeyError,
                NonFiniteNumberError,
                JSONDepthError,
                JSONNumberLimitError,
            ) as exc:
                errors = [f"invalid JSON: {exc}"]
            else:
                schema_errors = list(recipe_validator.iter_errors(document))
                errors = [str(error) for error in schema_errors]
                if not schema_errors:
                    errors.extend(recipe_semantic_errors(document, units))

        if case["expected"] == "valid" and errors:
            failures.append(f"{case['id']}: expected valid: {'; '.join(map(str, errors))}")
        if case["expected"] == "invalid" and not errors:
            failures.append(f"{case['id']}: expected invalid but passed")
        if case["expected"] == "invalid" and errors:
            markers = EXPECTED_CASE_MARKERS.get(case["id"]) or EXPECTED_ERROR_MARKERS.get(
                case["requirement_id"]
            )
            if markers is None:
                failures.append(
                    f"{case['id']}: no validator assertion for requirement "
                    f"{case['requirement_id']}"
                )
            else:
                rendered_errors = "\n".join(map(str, errors))
                if not all(marker in rendered_errors for marker in markers):
                    failures.append(
                        f"{case['id']}: failed for the wrong reason; expected "
                        f"{case['requirement_id']}: {rendered_errors}"
                    )
            failures.extend(category_failures(case, errors))

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(
        f"validated {len(manifest['cases'])} conformance cases and "
        f"{len(corpus['cases'])} ingredient-line cases and "
        f"{len(conversion_corpus['cases'])} unit-conversion cases and "
        f"{len(resolution_corpus['cases'])} unit-resolution cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
