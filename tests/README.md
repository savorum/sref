# Conformance fixtures

This directory contains machine-oriented fixtures indexed by
[`../conformance/manifest.json`](../conformance/manifest.json).

- `valid/` contains documents that must pass structural and semantic checks.
- `invalid/` contains documents that must be rejected for the listed reason.
- `roundtrip/` contains documents whose semantics and extensions must survive a
  read/write cycle.
- `amounts/` contains difficult ingredient-line parsing expectations.
- `units/` contains exact conversion and rejection vectors.
- `registry/` contains invalid registry snapshots, each targeting one semantic
  invariant.
- `packages/` contains package staging material and generated `.sref` archives.
- `bundles/` contains generated `.srefbundle` archives, valid and hostile.

Some invalid fixtures pass JSON Schema on purpose, to test rules that only
semantic validation can check.
