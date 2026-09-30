# Conformance guide

Conformance is claimed per capability. An implementation MUST enforce every rule
assigned to each capability it declares.

## Capabilities

### JSON reader

A conforming JSON reader:

- accepts every supported structurally and semantically valid recipe fixture;
- rejects invalid fixtures with an actionable reason;
- checks version support before interpreting normalized data;
- does not use binary floating point as the authoritative normalized quantity;
- preserves original and opaque text;
- preserves author order and structured credit metadata without inference; and
- preserves unknown extensions if it later writes the document.

### JSON writer

A conforming JSON writer:

- emits JSON Schema-valid documents;
- emits canonical rational strings;
- creates unique recipe-local IDs and sound references;
- emits only registered unit IDs for standard units;
- emits author kinds and URLs only when supported by source evidence; and
- does not replace source semantics with display conversions.

### Package reader

A conforming package reader also:

- parses `manifest.json` as strict UTF-8 JSON, rejecting duplicate object
  members, nonfinite numbers, and trailing values or non-whitespace data;
- enforces every package-safety rule before extraction;
- verifies size and SHA-256 metadata;
- rejects undeclared, missing, duplicate, linked, or unsafe entries; and
- validates agreement between manifest and recipe assets.

### Package writer

A conforming package writer also:

- creates exactly one `recipe.json` and `manifest.json` at archive root;
- writes all and only the declared assets;
- computes digest and size values from uncompressed bytes; and
- creates no encrypted, linked, or unsafe entry.

### Bundle reader

A conforming bundle reader also:

- applies the same strict JSON boundary to the bundle `manifest.json`;
- applies package-reader rules to the outer archive and to every member;
- enforces a finite implementation or deployment member-count limit without
  treating that policy as a format-level schema maximum;
- verifies each member's declared size and SHA-256 digest before opening it;
- rejects undeclared, missing, duplicate, or misnamed members;
- confirms that each member carries the recipe ID the manifest declares while
  allowing the same recipe-local ID in multiple members; and
- preserves the declared order.

### Bundle writer

A conforming bundle writer also:

- creates exactly one root `manifest.json` and one member per declared recipe;
- assigns every member a unique bundle-local ID and names it
  `recipes/<member-id>.sref`;
- writes members that are complete, independently valid packages;
- computes member digests and sizes from the exact member bytes; and
- records no timestamp and no application state in the manifest.

### Registry implementation

A conforming registry implementation:

- validates the registry snapshot;
- treats unit IDs as immutable semantic identities;
- enforces exactly one base unit for every physical dimension;
- verifies conversion references, dimensions, acyclicity, and positive
  multipliers;
- restricts affine definitions to temperature units;
- applies RFC 4647-style alias-locale lookup from the exact source tag through
  the primary language, stops at the first matching level, and does not search
  unrelated locales or an unscoped fallback;
- applies alias case policies without collapsing candidates that remain
  ambiguous at the winning locale level;
- rejects incompatible physical dimensions;
- does not invent physical conversions for count or container units; and
- distinguishes physical conversion from display formatting.

### Ingredient-line parser

A conforming ingredient-line parser MUST satisfy every case in
[`tests/amounts/ingredient-lines.json`](../tests/amounts/ingredient-lines.json)
according to [`docs/ingredient-line-corpus.md`](ingredient-line-corpus.md).

### Unit conversion

A conforming unit-conversion implementation MUST satisfy every vector in
[`tests/units/conversions.json`](../tests/units/conversions.json). It MUST use
exact rational arithmetic, propagate approximation, apply affine offsets,
preserve range order, and reject nonphysical or incompatible conversions.

### Unit resolution

A conforming unit-resolution implementation MUST satisfy every vector in
[`tests/resolution/unit-resolution.json`](../tests/resolution/unit-resolution.json)
under [specification section 9.5](../spec.md#95-resolution-decisions). Each
vector supplies identified unit occurrences, the source evidence available, and
the explicit decisions a person made; the implementation MUST reach the stated
identity for each occurrence, leave unresolved the occurrences the corpus states
as `null`, and report a conflicting context rather than settling it.

The capability is tested by submitting a resolution context, not a document. It
does not require ingredient parsing.

### Round-trip implementation

A conforming round-trip implementation preserves all semantics listed in
[spec.md](../spec.md), including unknown scoped extensions.

JSON key order, insignificant whitespace, and ZIP byte layout need not be
preserved.

## Test manifest

[`conformance/manifest.json`](../conformance/manifest.json) indexes every
fixture. Each case has:

- a stable case ID;
- one or more capabilities;
- a fixture path;
- the expected validity;
- for an invalid case, an `error_category` and a `requirement_id`.

A case applies separately to each capability it lists; an implementation does
not have to claim the others. A recipe example, for instance, tests that a JSON
reader accepts it and that a JSON writer can produce an equivalent document.
Dependencies between capabilities, such as a converter needing a registry, do
not make an unrelated fixture a test of the dependency.

### Failure identifiers

- `error_category` is one of the seven categories in
  [specification section 22.1](../spec.md#221-processor-failure-categories). It
  is part of SREF: a conforming processor makes it available to its caller.
- `requirement_id` names the rule the fixture tests. It is the corpus's own
  identifier, stable within the conformance snapshot that defines it, and not
  part of SREF's error vocabulary. An implementation MAY report it.

The two are independent. `invalid-bundle-member-package`, for example, can occur
under `integrity-failure` (a member declares a missing asset) or `unknown-unit`
(a member names an unregistered unit). The unknown-unit bundle fixture has
separate reader and writer cases: the reader reports
`invalid-bundle-member-package`, and the writer, given the member's recipe,
reports `unknown-unit`.

The bundled validator checks that each invalid fixture fails for its declared
requirement and category and has no defect in any other category. Neither
identifier fixes the wording of error messages.

## Testing an implementation

[`conformance/runner.py`](../conformance/runner.py) runs the corpus against an
implementation through the adapter protocol in
[conformance-runner.md](conformance-runner.md). Rejecting an invalid fixture
under the wrong category is `wrong-category`; under the right category but for a
different rule, `wrong-requirement`.

### Round trips between implementations

[`conformance/roundtrip_audit.py`](../conformance/roundtrip_audit.py) passes
every valid round-trip fixture and example through several implementations in
turn, using their adapters, and compares each result with the original file:

```sh
python3 conformance/roundtrip_audit.py \
    --adapter "python3 ../sref-writer/tools/adapter.py --reader ../sref-reader" \
    --adapter ../savorum/bin/srefadapter
```

Every adapter must claim `round-trip`. The command prints how many fixtures
survived and, for each failure, the implementation and the difference.
`--json results.json` writes the full result.

## Reference implementations

[SREF Reader](https://github.com/savorum/sref-reader) (`sref-reader`) claims the
JSON reader, package reader, bundle reader, registry, and unit-conversion
capabilities. [SREF Writer](https://github.com/savorum/sref-writer)
(`sref-writer`) claims the JSON, package, and bundle writer capabilities. Both
implement SREF 0.4.0 with unit registry 0.2.0 and run this manifest directly.

Neither claims unit resolution, because neither accepts a resolution context.
Neither claims round trip alone; the writer's conformance run uses the reader to
check its output.

## Round-trip fixtures

For a round-trip case:

1. Read the input.
2. Write it without changes.
3. Read the output.
4. Compare the two recipes semantically.

The comparison MUST cover every known and unknown standard field, array order,
rational value, ID, reference, source string, step title, ingredient
optionality, variant title and text, normalization method and review state,
warning, package size, temperature, duration, timing assertion, asset
declaration, recipe and step image order, primary image, unknown registry ID,
and extension value, subject to the equivalences the specification defines. An
omitted `approximate` equals `"approximate": false`, and a writer MAY write
either. Other differences in field presence remain significant where omission
means something different. Unknown values MUST stay attached to the same object.

Unsupported extension values are opaque JSON. A round-trip implementation must
not interpret them, use them to change core data, or require support for them in
order to preserve them.

## Structural and semantic validation

The strict JSON rules apply to recipe documents, package and bundle manifests,
registries, and conformance data: exactly one complete JSON value, and no
duplicate object members at any depth.

JSON Schema checks structure, simple patterns, and required fields. It cannot
fully check:

- reduced fractions;
- range ordering;
- recipe-wide ID uniqueness;
- timing-assertion ID uniqueness and references;
- BCP 47 validity;
- version compatibility, and whether a unit belongs to the declared registry or
  is an unknown ID from a newer compatible registry;
- normalization provenance requirements;
- where physical and temperature units may appear;
- registry base units, conversion graphs, replacements, and aliases;
- package agreement and archive safety.

Conformance requires both schema and semantic validation.

## Adversarial tests

[`conformance/test_security.py`](../conformance/test_security.py) generates
hostile JSON, packages, and bundles when it runs, with resource limits lowered
to small values and fixed random seeds. It covers deep JSON nesting and large
numbers, malformed UTF-8, random JSON and ZIP bytes, path collisions and
traversal, nonregular archive entries, compressed and expanded size limits,
entry and member counts, packages nested in bundles, collection size limits,
cyclic unit conversions, and untrusted asset media types. `just check` runs it.

## External corpus loss audit

[`conformance/recipe-corpus.json`](../conformance/recipe-corpus.json) pins a
commit of the private recipe-corpus repository and the SREF loss audit generated
from it. This optional maintainer check is separate from public conformance and
is excluded from default checks and public CI. It reads only the corpus's
generated coverage report and derived SREF documents. Maintainers run it against
a local checkout of the pinned commit with
`just corpus-check /path/to/recipe-corpus`.

Every representation in the corpus must have exactly one disposition:
`evaluated`, with a derived target, or `reference_only`, with a metadata
evaluation. Both need a classification for every concept. A missing, unknown, or
`non_executable` disposition fails the check.

Each concept has one verdict:

| Verdict                | Meaning                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| `exact`                | The target carries the construct this SREF version defines, and a reviewed semantic check passes. |
| `semantics_unverified` | The target carries the construct, and no reviewed semantic check covers it.                       |
| `misrepresented`       | The target carries the construct, and it contradicts the source.                                  |
| `sref_unsupported`     | SREF has no representation for it: a format gap.                                                  |
| `mapping_unverified`   | SREF can represent it, but the audit has no detector or no target to inspect: an audit gap.       |
| `accidentally_lost`    | SREF can represent it and the target does not.                                                    |
| `upstream_lost`        | The concept was already gone before conversion to SREF.                                           |

The check pins a digest of every verdict with its boundary, capability, and
basis, so changing the reasoning behind a verdict changes the digest. Every
accidental loss and misrepresentation must link a defect the manifest already
names. Losses caused by a source application are `upstream_lost`, and data the
project bridge never supplied is recorded at the `bridge_input` boundary;
neither counts against the format.

## Conformance declaration

A conformance declaration MUST list:

- the exact SREF format version;
- the exact unit-registry version;
- every implemented capability;
- any failed or skipped mandatory fixture for those capabilities.

Reading the known part of a newer compatible document does not make that newer
version an implemented one.
