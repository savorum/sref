#!/usr/bin/env python3
"""Audit round trips across independent implementations:

    source → SREF A → implementation B → SREF B → implementation C → SREF C

Every hop is compared against the original, so a loss cannot become the
baseline for the next. What has to survive is everything an implementation is
not required to understand: unknown extensions, opaque quantities, source text,
explicit uncertainty, recipe-local identity, and asset references.

    python3 conformance/roundtrip_audit.py \
        --adapter ../sref-reader/tools/adapter.py \
        --adapter ../savorum/bin/srefadapter
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import sys
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import semantics  # noqa: E402
from runner import Adapter, AdapterError, ROOT, _named  # noqa: E402


@dataclass
class Hop:
    implementation: str
    outcome: str
    detail: str = ""


@dataclass
class Audit:
    case_id: str
    fixture: str
    hops: list[Hop]

    @property
    def passed(self) -> bool:
        return all(hop.outcome == "pass" for hop in self.hops)


def fixtures(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Every fixture a round trip is defined over: the declared round-trip
    cases and the published examples.
    """
    chosen = []
    for case in manifest["cases"]:
        if case["expected"] != "valid":
            continue
        if not str(case["fixture"]).endswith(".recipe.json"):
            continue
        capabilities = set(case["capabilities"])
        if capabilities & {"round-trip", "json-writer"}:
            chosen.append(case)
    return chosen


def audit(adapters: list[Adapter], manifest: dict[str, Any]) -> list[Audit]:
    results: list[Audit] = []
    for case in fixtures(manifest):
        fixture = ROOT / case["fixture"]
        original = json.loads(fixture.read_text(encoding="utf-8"))
        results.append(_chain(adapters, case, fixture, original))
    return results


def _chain(adapters: list[Adapter], case: dict[str, Any], fixture: pathlib.Path, original: Any) -> Audit:
    hops: list[Hop] = []
    current = fixture
    temporary: pathlib.Path | None = None
    try:
        for adapter in adapters:
            name = adapter.declaration.get("implementation", "?")
            try:
                answer = adapter.rewrite(current)
            except AdapterError as exc:
                hops.append(Hop(name, "adapter-error", str(exc)))
                break
            if answer.get("outcome") != "accepted":
                hops.append(Hop(name, "rejected", _named(answer)))
                break
            written = answer.get("document")
            if not isinstance(written, dict):
                hops.append(Hop(name, "adapter-error", "rewrite returned no document"))
                break
            if not semantics.equivalent(original, written):
                hops.append(Hop(name, "lossy", semantics.difference(original, written)))
                break
            hops.append(Hop(name, "pass"))
            temporary = _handoff(written, case["id"], len(hops))
            current = temporary
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return Audit(case_id=case["id"], fixture=case["fixture"], hops=hops)


def _handoff(document: Any, case_id: str, index: int) -> pathlib.Path:
    """Write one implementation's output as bytes for the next one to read."""
    import tempfile

    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=f".{case_id}.{index}.recipe.json", delete=False, encoding="utf-8"
    )
    with handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return pathlib.Path(handle.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", action="append", required=True,
                        help="an adapter command; repeat to chain implementations in order")
    parser.add_argument("--json", type=pathlib.Path)
    parser.add_argument("--timeout", type=float, default=60.0)
    arguments = parser.parse_args()

    adapters = []
    for command in arguments.adapter:
        adapter = Adapter(command=shlex.split(command), timeout=arguments.timeout)
        try:
            adapter.describe()
        except AdapterError as exc:
            print(f"adapter {command!r} failed to declare itself: {exc}", file=sys.stderr)
            return 2
        if "round-trip" not in adapter.capabilities:
            print(
                f"{adapter.declaration.get('implementation')!r} does not claim round-trip;"
                " it cannot take part in a chain",
                file=sys.stderr,
            )
            return 2
        adapters.append(adapter)

    manifest = json.loads((ROOT / "conformance" / "manifest.json").read_text(encoding="utf-8"))
    results = audit(adapters, manifest)

    chain = " → ".join(adapter.declaration.get("implementation", "?") for adapter in adapters)
    passed = sum(1 for result in results if result.passed)
    print(f"chain: source → {chain}")
    print(f"{passed}/{len(results)} fixtures survive the chain")

    for result in results:
        if result.passed:
            continue
        for hop in result.hops:
            if hop.outcome != "pass":
                print(f"  {result.case_id:40s} {hop.implementation:16s} {hop.outcome:14s} {hop.detail}")

    if arguments.json:
        arguments.json.write_text(
            json.dumps(
                {
                    "chain": [adapter.declaration for adapter in adapters],
                    "fixtures": [
                        {"case_id": r.case_id, "fixture": r.fixture,
                         "hops": [vars(hop) for hop in r.hops], "passed": r.passed}
                        for r in results
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
