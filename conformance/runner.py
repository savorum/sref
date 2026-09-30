#!/usr/bin/env python3
"""Test an implementation against the normative SREF conformance corpus.

The runner drives an implementation through the adapter protocol in
`docs/conformance-runner.md`, a small command-line contract any language can
satisfy.

    python3 conformance/runner.py --adapter ../sref-reader/tools/adapter.py
    python3 conformance/runner.py --adapter ./adapter --json results.json

An implementation declares which capabilities it claims. It is not required to
implement every optional capability in order to make a meaningful claim, so a
case exercising a capability the adapter does not declare is reported as
unsupported rather than failed — and a capability that is claimed is tested in
full.

Accepting a document that must be rejected, and rejecting it for the wrong
reason, are reported apart. A rejection carries two identifiers (section
22.1): a wrong `error_category` is `wrong-category`; a different
`requirement_id` is `wrong-requirement`, while an omitted one passes
unconfirmed. The declaration counts confirmed rejections separately, since
most fixtures share `invalid-artifact`.

Writer results are checked here rather than taken on the adapter's word: a
returned artifact is validated against this repository's schemas and compared
with the fixture it was asked to produce. A writer case expecting `invalid` is
a request the writer must decline.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import artifact as artifact_module  # noqa: E402
import semantics  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Capabilities the corpus exercises. An adapter declares a subset.
CAPABILITIES = (
    "json-reader",
    "json-writer",
    "package-reader",
    "package-writer",
    "bundle-reader",
    "bundle-writer",
    "registry",
    "unit-conversion",
    "unit-resolution",
    "ingredient-parser",
    "round-trip",
)

#: Adapter responses the runner understands. Anything else is an adapter
#: failure, not a result about the implementation.
OUTCOMES = ("accepted", "rejected", "unsupported")

#: The normative failure categories of specification section 22.1. Anything
#: else is an adapter defect.
CATEGORIES = (
    "invalid-artifact",
    "unsupported-format-version",
    "unsupported-registry-version",
    "unknown-unit",
    "integrity-failure",
    "unsafe-archive",
    "resource-limit",
)

#: Capabilities whose result is an artifact the implementation produced, and so
#: can be checked here rather than believed.
PRODUCING = ("json-writer", "package-writer", "bundle-writer", "round-trip")

class AdapterError(RuntimeError):
    pass


@dataclass
class Adapter:
    """One implementation under test, driven as a subprocess."""

    command: list[str]
    timeout: float = 60.0
    declaration: dict[str, Any] = field(default_factory=dict)

    @property
    def capabilities(self) -> set[str]:
        return set(self.declaration.get("capabilities") or ())

    def describe(self) -> None:
        self.declaration = self._invoke(["capabilities"])
        for member in ("implementation", "version", "sref_version", "unit_registry_version"):
            if not self.declaration.get(member):
                raise AdapterError(f"the adapter's declaration has no {member!r}")
        unknown = self.capabilities - set(CAPABILITIES)
        if unknown:
            raise AdapterError(f"the adapter declares unknown capabilities {sorted(unknown)}")

    def check(self, capability: str, fixture: pathlib.Path) -> dict[str, Any]:
        return self._invoke(["check", capability, str(fixture)])

    def rewrite(self, fixture: pathlib.Path) -> dict[str, Any]:
        return self._invoke(["rewrite", str(fixture)])

    def resolve(self, fixture: pathlib.Path) -> dict[str, Any]:
        return self._invoke(["resolve", str(fixture)])

    def _invoke(self, arguments: list[str]) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                [*self.command, *arguments],
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"the adapter did not answer within {self.timeout}s") from exc
        except OSError as exc:
            raise AdapterError(f"the adapter could not be run: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()[:200]
            raise AdapterError(f"the adapter exited {completed.returncode}: {detail}")
        try:
            answer = json.loads(completed.stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AdapterError(f"the adapter did not print one JSON object: {exc}") from exc
        if not isinstance(answer, dict):
            raise AdapterError("the adapter did not print a JSON object")
        return answer


@dataclass
class Result:
    case_id: str
    capability: str
    outcome: str
    detail: str = ""
    #: What the case required: the normative category, and the corpus
    #: requirement the fixture exercises. Carried on failures so a report can
    #: say what was expected without re-reading the manifest.
    expected: str = ""
    requirement: str = ""
    witnessed: bool = True
    #: True when a rejection named the case's `requirement_id`. False means the
    #: refusal matched the category without identifying the specific rule.
    confirmed: bool = True


def run(adapter: Adapter, manifest: dict[str, Any], *, only: set[str] | None = None) -> list[Result]:
    results: list[Result] = []
    for case in manifest["cases"]:
        capabilities = set(case["capabilities"])
        selected = capabilities & only if only is not None else capabilities
        if not selected:
            continue
        exercised = selected & adapter.capabilities
        if not exercised:
            results.append(
                Result(case["id"], ",".join(sorted(selected)), "unsupported",
                       "the implementation does not claim this capability")
            )
            continue
        # Once per claimed capability the case declares, so each capability is
        # exercised on its own.
        for capability in sorted(exercised):
            results.append(_run_case(adapter, case, capability))
    return results


def _run_case(adapter: Adapter, case: dict[str, Any], capability: str) -> Result:
    fixture = ROOT / case["fixture"]
    category = case.get("error_category", "")
    requirement = case.get("requirement_id", "")
    if not fixture.exists():
        return Result(case["id"], capability, "error", f"missing fixture {case['fixture']}")

    try:
        if capability == "round-trip":
            return _run_round_trip(adapter, case, fixture)
        if capability == "unit-resolution":
            return _run_resolution(adapter, case, fixture)
        answer = adapter.check(capability, fixture)
    except AdapterError as exc:
        return Result(case["id"], capability, "adapter-error", str(exc), category, requirement)

    outcome = answer.get("outcome")
    if outcome not in OUTCOMES:
        return Result(
            case["id"], capability, "adapter-error",
            f"unknown outcome {outcome!r}", category, requirement,
        )
    if outcome == "unsupported":
        return Result(
            case["id"], capability, "unsupported",
            answer.get("detail", ""), category, requirement,
        )

    if case["expected"] == "valid":
        if outcome == "accepted":
            return _check_artifact(answer, capability, case)
        return Result(
            case["id"], capability, "wrong-verdict",
            f"rejected a valid fixture as {_named(answer)}",
        )

    if outcome == "accepted":
        return Result(
            case["id"], capability, "wrong-verdict",
            "accepted an invalid fixture", category, requirement,
        )
    return _check_rejection(answer, capability, case, category, requirement)


def _check_rejection(
    answer: dict[str, Any],
    capability: str,
    case: dict[str, Any],
    category: str,
    requirement: str,
) -> Result:
    """Judge a refusal against the category and requirement the case declares.

    A missing or non-normative category is an adapter defect. The requirement
    is not a required public API (section 22.1): omitting it leaves the
    refusal unconfirmed, while naming a different one fails, since each
    fixture carries one isolated defect.
    """
    reported = answer.get("error_category")
    if reported is None:
        return Result(
            case["id"], capability, "adapter-error",
            "the rejection carried no error_category", category, requirement,
        )
    if reported not in CATEGORIES:
        return Result(
            case["id"], capability, "adapter-error",
            f"unknown error_category {reported!r}", category, requirement,
        )
    if category and reported != category:
        return Result(
            case["id"], capability, "wrong-category",
            f"rejected as {_named(answer)}", category, requirement,
        )
    named = answer.get("requirement_id")
    if requirement and named is not None and named != requirement:
        return Result(
            case["id"], capability, "wrong-requirement",
            f"rejected as {_named(answer)}", category, requirement,
        )
    return Result(
        case["id"], capability, "pass",
        expected=category, requirement=requirement,
        confirmed=bool(requirement) and named == requirement,
    )


def _named(answer: dict[str, Any]) -> str:
    """How the adapter described a refusal, for a failure message."""
    category = answer.get("error_category")
    requirement = answer.get("requirement_id")
    if requirement:
        return f"{category!r} [{requirement}]"
    return repr(category)


def _check_artifact(answer: dict[str, Any], capability: str, case: dict[str, Any]) -> Result:
    """Validate what the adapter produced, and compare it with its request.

    A missing artifact still passes, but the result records that it rested on
    the adapter's own account. That is kept on the result rather than in
    process-global state.
    """
    if capability not in PRODUCING:
        return Result(case["id"], capability, "pass")
    try:
        data = artifact_module.decode(answer)
    except artifact_module.Malformed as exc:
        return Result(case["id"], capability, "adapter-error", str(exc))
    if data is None:
        return Result(case["id"], capability, "pass", witnessed=False)
    problems = artifact_module.problems(data, capability)
    if problems:
        # The adapter said `accepted`; this repository's own validator
        # disagrees.
        return Result(
            case["id"], capability, "wrote-invalid",
            f"the implementation accepted what this corpus rejects: {'; '.join(problems[:2])}",
            "the emitted artifact validates against the published schemas",
        )
    changed = artifact_module.divergence(data, capability, ROOT / case["fixture"])
    if changed:
        return Result(
            case["id"], capability, "lossy", changed,
            "the emitted artifact says what the request said",
        )
    return Result(case["id"], capability, "pass")


def _run_round_trip(adapter: Adapter, case: dict[str, Any], fixture: pathlib.Path) -> Result:
    """Read and write the fixture, then compare what came back using the
    specification's equivalence, not the implementation's.
    """
    original = json.loads(fixture.read_text(encoding="utf-8"))
    answer = adapter.rewrite(fixture)
    if answer.get("outcome") != "accepted":
        return Result(
            case["id"], "round-trip", "wrong-verdict",
            f"could not rewrite a valid fixture: {_named(answer)}",
        )
    written = answer.get("document")
    if not isinstance(written, dict):
        return Result(case["id"], "round-trip", "adapter-error", "rewrite returned no document")
    artifact_result = _check_artifact(answer, "round-trip", case)
    if artifact_result.outcome != "pass":
        return artifact_result
    if not semantics.equivalent(original, written):
        return Result(
            case["id"], "round-trip", "lossy",
            semantics.difference(original, written), "round-trip preservation",
        )
    return Result(case["id"], "round-trip", "pass", witnessed=artifact_result.witnessed)


def _run_resolution(adapter: Adapter, case: dict[str, Any], fixture: pathlib.Path) -> Result:
    """Submit each vector's resolution context and inspect what came back.

    The adapter returns one answer per case: the identity reached for each
    occurrence, `null` where the measure must stay unresolved, or a reported
    conflict. A single disagreeing case fails the capability.
    """
    corpus = json.loads(fixture.read_text(encoding="utf-8"))
    answer = adapter.resolve(fixture)
    outcome = answer.get("outcome")
    if outcome == "unsupported":
        return Result(case["id"], "unit-resolution", "unsupported", answer.get("detail", ""))
    if outcome != "accepted":
        return Result(
            case["id"], "unit-resolution", "wrong-verdict",
            f"declined a valid resolution corpus as {_named(answer)}",
        )
    reported = answer.get("resolutions")
    if not isinstance(reported, dict):
        return Result(
            case["id"], "unit-resolution", "adapter-error",
            "the answer carried no resolutions object",
        )

    differences: list[str] = []
    for vector in corpus["cases"]:
        expected = vector["expected"]
        actual = reported.get(vector["id"])
        if actual is None:
            differences.append(f"{vector['id']}: no answer")
        elif actual != expected:
            differences.append(f"{vector['id']}: expected {expected}, answered {actual}")
    if differences:
        return Result(
            case["id"], "unit-resolution", "wrong-resolution",
            "; ".join(differences[:3]) + (
                f" (and {len(differences) - 3} more)" if len(differences) > 3 else ""
            ),
            "the resolution vectors of specification section 9.5",
        )
    return Result(case["id"], "unit-resolution", "pass")


def declaration(adapter: Adapter, manifest: dict[str, Any], results: list[Result]) -> dict[str, Any]:
    """The conformance claim these results support, for the corpus's own SREF
    version.
    """
    failures = collections.Counter(result.capability for result in results if result.outcome not in ("pass", "unsupported"))
    executed = collections.Counter(result.capability for result in results if result.outcome == "pass")
    refusals = [result for result in results if result.outcome == "pass" and result.requirement]
    # Demonstrated means the corpus exercised it and every case passed.
    achieved = sorted(
        capability
        for capability in adapter.capabilities
        if executed[capability] and not failures[capability]
    )
    return {
        "implementation": adapter.declaration.get("implementation"),
        "version": adapter.declaration.get("version"),
        "sref_version": manifest["sref_version"],
        "unit_registry_version": manifest["unit_registry_version"],
        "capabilities_claimed": sorted(adapter.capabilities),
        "capabilities_demonstrated": achieved,
        #: Claimed, and no case in the corpus exercises it (not a failure, but
        #: not demonstrated either).
        "capabilities_unexercised": sorted(adapter.capabilities - set(achieved) - {r.capability for r in results if r.outcome not in ("pass", "unsupported")}),
        # Writer capabilities demonstrated without returning any artifact.
        "capabilities_unwitnessed": sorted(
            {
                result.capability
                for result in results
                if result.outcome == "pass" and not result.witnessed
            }
            & set(achieved)
        ),
        "cases": {
            "passed": sum(1 for r in results if r.outcome == "pass"),
            "failed": sum(1 for r in results if r.outcome not in ("pass", "unsupported")),
            "unsupported": sum(1 for r in results if r.outcome == "unsupported"),
        },
        # Of the refusals that passed, how many named the rule they were
        # refusing under.
        "requirements": {
            "confirmed": sum(1 for result in refusals if result.confirmed),
            "unconfirmed": sum(1 for result in refusals if not result.confirmed),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", required=True, help="command implementing the adapter protocol")
    parser.add_argument("--capability", action="append", help="limit the run to one or more capabilities")
    parser.add_argument("--json", type=pathlib.Path, help="write machine-readable results to this path")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()

    manifest = json.loads((ROOT / "conformance" / "manifest.json").read_text(encoding="utf-8"))
    adapter = Adapter(command=shlex.split(arguments.adapter), timeout=arguments.timeout)
    try:
        adapter.describe()
    except AdapterError as exc:
        print(f"adapter declaration failed: {exc}", file=sys.stderr)
        return 2

    only = set(arguments.capability) if arguments.capability else None
    results = run(adapter, manifest, only=only)
    claim = declaration(adapter, manifest, results)

    if arguments.json:
        arguments.json.write_text(
            json.dumps(
                {
                    "declaration": claim,
                    # `witnessed` and `confirmed` are internal evidence used
                    # to build the declaration, not per-result protocol
                    # members.
                    "results": [
                        {
                            key: value
                            for key, value in vars(result).items()
                            if key not in ("witnessed", "confirmed")
                        }
                        for result in results
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if not arguments.quiet:
        _report(claim, results)
    return 0 if claim["cases"]["failed"] == 0 else 1


def _report(claim: dict[str, Any], results: list[Result]) -> None:
    print(f"{claim['implementation']} {claim['version']}")
    print(f"tested against SREF {claim['sref_version']} / unit registry {claim['unit_registry_version']}")
    print(f"claimed:      {', '.join(claim['capabilities_claimed']) or '(none)'}")
    print(f"demonstrated: {', '.join(claim['capabilities_demonstrated']) or '(none)'}")
    counts = claim["cases"]
    print(f"{counts['passed']} passed, {counts['failed']} failed, {counts['unsupported']} unsupported")
    requirements = claim["requirements"]
    if requirements["confirmed"] or requirements["unconfirmed"]:
        print(
            f"refusals: {requirements['confirmed']} named the requirement, "
            f"{requirements['unconfirmed']} reported only the category"
        )

    failures = [result for result in results if result.outcome not in ("pass", "unsupported")]
    if not failures:
        return
    print()
    for result in failures:
        expected = ""
        if result.expected:
            expected = f" [{result.expected}"
            expected += f"/{result.requirement}]" if result.requirement else "]"
        print(f"  {result.case_id:44s} {result.outcome:16s}{expected} {result.detail}")


if __name__ == "__main__":
    raise SystemExit(main())
