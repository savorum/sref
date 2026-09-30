# Conformance runner and adapter protocol

`conformance/runner.py` runs the conformance corpus against an implementation
and reports which of its claimed capabilities pass. It talks to the
implementation through an adapter: a small executable, in any language, that
answers the commands below.

```sh
python3 conformance/runner.py --adapter ../sref-reader/tools/adapter.py
python3 conformance/runner.py --adapter ./my-adapter --json results.json
```

## The adapter

The runner calls the adapter with arguments and reads one JSON object from its
standard output. The adapter MUST exit `0` whenever it answers, including when
the answer is a rejection. A nonzero exit is reported as an adapter failure.

### `capabilities`

```sh
$ my-adapter capabilities
{
  "implementation": "sref-reader",
  "version": "0.4.0",
  "sref_version": "0.4.0",
  "unit_registry_version": "0.2.0",
  "capabilities": ["json-reader", "package-reader", "bundle-reader",
                   "registry", "unit-conversion"]
}
```

The capability names are those in
[specification section 22](../spec.md#22-conformance): `json-reader`,
`json-writer`, `package-reader`, `package-writer`, `bundle-reader`,
`bundle-writer`, `registry`, `unit-conversion`, `unit-resolution`,
`ingredient-parser`, and `round-trip`.

Every case for a declared capability is run. A case for an undeclared capability
is reported as `unsupported`, not as a failure.

### `check <capability> <fixture>`

```sh
$ my-adapter check json-reader tests/invalid/duplicate-step-id.recipe.json
{"outcome": "rejected", "error_category": "invalid-artifact",
 "requirement_id": "duplicate-step-id"}

$ my-adapter check json-reader examples/sourdough.recipe.json
{"outcome": "accepted"}
```

`outcome` is `accepted`, `rejected`, or `unsupported`. Any outcome MAY include a
`detail` string.

A rejection carries the identifiers from
[specification section 22.1](../spec.md#221-processor-failure-categories):

- `error_category` is REQUIRED and is one of `invalid-artifact`,
  `unsupported-format-version`, `unsupported-registry-version`, `unknown-unit`,
  `integrity-failure`, `unsafe-archive`, or `resource-limit`. A missing or
  unknown category is reported as `adapter-error`.
- `requirement_id` is OPTIONAL and names the rule the fixture tests. These IDs
  belong to the corpus and are not a required API. A rejection without one still
  passes but counts as **unconfirmed**. A rejection naming a different rule is
  `wrong-requirement`.

Most invalid fixtures share the `invalid-artifact` category, so the declaration
reports how many rejections named their rule.

### Writer artifacts

For a writer capability, an `accepted` answer SHOULD include what the
implementation wrote:

```sh
$ my-adapter check package-writer tests/valid/minimal-with-asset.sref
{"outcome": "accepted", "artifact": "UEsDBBQ...", "artifact_encoding": "base64"}
```

`artifact_encoding` is `utf-8` (the default) for a recipe document and `base64`
for a package or bundle. The runner validates the artifact and compares it with
the fixture:

- recipes are compared with
  [`conformance/semantics.py`](../conformance/semantics.py);
- package assets are compared by ID and content;
- bundle members are compared by recipe ID, in order, and each member as a
  package.

Byte-identical output is not required. Without an artifact the case can still
pass, but the capability is reported as **unwitnessed**.

### Writer cases that must be refused

A case with a writer capability and `"expected": "invalid"` is input the writer
must refuse, such as an unregistered unit, a duplicate ID, a dangling reference,
or a path outside the archive. The adapter answers `rejected` with the case's
`error_category`:

```sh
$ my-adapter check json-writer tests/invalid/unknown-unit.recipe.json
{"outcome": "rejected", "error_category": "unknown-unit",
 "requirement_id": "unknown-unit"}
```

The adapter MUST pass the input to the writer. It must not reject a case because
a reader rejected the fixture, since every such fixture is one a reader rejects.
If the adapter cannot build the request without a reader, or the writer's model
cannot represent the input, it answers `unsupported`.

### `resolve <fixture>`

Required only for `unit-resolution`.

```sh
$ my-adapter resolve tests/resolution/unit-resolution.json
{"outcome": "accepted", "resolutions": {
  "compound-sum-ingredient-convention": {
    "outcome": "resolved",
    "units": {"spoon-large": "volume.tablespoon.us.customary",
              "spoon-small": "volume.teaspoon.us.customary"}},
  "compound-sum-no-decision": {
    "outcome": "resolved", "units": {"spoon-large": null, "spoon-small": null}},
  "conflicting-ingredient-conventions": {
    "outcome": "conflict", "conflict": "convention"}}}
```

The adapter reads the vector file, applies
[section 9.5](../spec.md#95-resolution-decisions) to each vector using its unit
occurrences, `source_locale`, and `decisions`, and returns one answer per case
ID. Each answer has the shape of the vector's `expected`: `resolved` with a unit
ID for each occurrence (`null` where the occurrence must stay unresolved), or
`conflict` with the kind of conflict. Every vector must match.

The vectors use identified unit occurrences, not ingredient lines, so this
capability does not require ingredient parsing (`ingredient-parser`).

### `rewrite <fixture>`

Required only for `round-trip`.

```sh
$ my-adapter rewrite tests/roundtrip/extension-preservation.recipe.json
{"outcome": "accepted", "document": { ... }}
```

The adapter reads the fixture, writes it again, and returns the result as parsed
JSON in `document`. It SHOULD also return the written bytes as `artifact`. The
runner compares the result with the original.

## Equivalence

Two documents are equal when they match after these rules:

- object member order is ignored (section 4);
- a member set to its defined default, such as `approximate: false` or
  `optional: false`, equals an absent member (section 24);
- array order is compared;
- unknown standard members and extension members are compared exactly, including
  JSON type;
- numbers are compared as written, so an amount changed by floating-point
  conversion does not match.

## Outcomes

| Outcome             | Meaning                                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `pass`              | The implementation did what the case requires.                                                                    |
| `wrong-verdict`     | It accepted a document that must be rejected, or rejected one that must be accepted.                              |
| `wrong-category`    | It rejected the document under a different failure category.                                                      |
| `wrong-requirement` | It rejected the document under the right category but named a different rule.                                     |
| `lossy`             | A round trip changed the document, or a written artifact differs from the request. The detail names what changed. |
| `wrong-resolution`  | A resolution vector reached a different result.                                                                   |
| `wrote-invalid`     | The adapter accepted its own output, and the validator rejects it.                                                |
| `unsupported`       | The case tests a capability the implementation does not claim.                                                    |
| `adapter-error`     | The adapter did not answer correctly.                                                                             |

## Declaration

The runner ends with a declaration of what the results support:

```json
{
  "implementation": "sref-reader",
  "version": "0.4.0",
  "sref_version": "0.4.0",
  "unit_registry_version": "0.2.0",
  "capabilities_claimed": ["bundle-reader", "json-reader", "..."],
  "capabilities_demonstrated": ["bundle-reader", "json-reader", "..."],
  "capabilities_unwitnessed": [],
  "cases": { "passed": 173, "failed": 0, "unsupported": 43 },
  "requirements": { "confirmed": 147, "unconfirmed": 0 }
}
```

- A capability is demonstrated when every case for it passed.
- `capabilities_unwitnessed` lists demonstrated writer capabilities for which
  the adapter returned no artifact.
- `requirements` counts passing rejections with and without a named rule.
- The versions are the corpus's, not the adapter's. Reading the known part of a
  newer compatible document does not make an implementation conform to that
  version (section 5).

To chain several implementations, see
[round trips between implementations](conformance.md#round-trips-between-implementations).
