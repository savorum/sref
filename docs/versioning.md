# Versioning and compatibility

## Version syntax

SREF specification and registry versions use three dot-separated nonnegative
decimal integers:

```text
MAJOR.MINOR.PATCH
```

Each component MUST contain no leading zero unless the component is exactly `0`.
Prerelease labels and build metadata are not valid document or registry version
identifiers. Work on an unreleased change does not create a new format
identifier until an immutable snapshot is published.

Readers MUST compare all three components. Writers MUST emit the exact version
whose rules they follow.

Versions with the same `MAJOR` component belong to one compatibility line,
including before 1.0: `0.4.0` and `0.5.0` are in the same compatibility line.
Within a compatibility line, a newer version may add information but MUST NOT
change the interpretation of information valid in an earlier version. A reader
for an earlier version therefore MUST read the subset it understands from a
newer version in the same compatibility line, subject to the preservation rules
below. It MUST NOT claim full support for that newer version.

Schema `$id` values and released registry versions are immutable identifiers.
Once published, an identifier MUST NOT be reused for different bytes or
different semantic requirements.

## Change classification

- A patch release MUST preserve document meaning and validation outcomes. It MAY
  clarify prose, add nonnormative examples, or correct tooling defects.
- A minor release MAY add optional fields, extension points, registry entries,
  or conformance cases. Existing valid documents MUST retain their meaning.
- A major release MAY make incompatible structural or semantic changes.

Recipe durability takes priority over schema tidiness, including before the
first stable release. A breaking change MUST start a new compatibility line by
incrementing the major version and MUST include migration guidance and
conformance fixtures.

Every new standardized core field requires at least a minor version increment.
Adding an optional field with independent, additive semantics is compatible.
Making a field required, changing a default, changing the interpretation of
existing data, or adding a field whose presence changes the meaning of an
existing field is incompatible and requires a new major version. Editorial
changes do not require a document-version increment.

Released closed vocabularies and discriminator values are frozen within a
compatibility line. Authors MUST use the compatibility value intended for
unrecognized concepts, such as `other` plus a label, where one is defined.
Adding a new value to a closed vocabulary requires a new compatibility line.

## Forward-compatible reading

A reader encountering a newer recipe version in the same compatibility line:

1. MUST validate and interpret every standard member it understands according to
   its supported version;
2. MUST ignore unknown members when interpreting known semantics;
3. MUST preserve every unknown member and its JSON value semantically at the
   same object scope when rewriting;
4. MUST NOT infer meaning for an unknown member or reject the document merely
   because that member exists; and
5. MUST treat the document as read-only, or require an explicitly lossy
   operation, if it cannot preserve the unknown data safely.

The schema for an earlier version validates the standardized subset understood
by that version. It permits unknown object members so a newer compatible
document is not mechanically rejected. Passing an older schema does not
establish complete conformance to the newer declared version.

A reader MUST reject a document from a different compatibility line unless it
implements that line explicitly. It MUST also reject an older version for which
it has no supported schema; forward compatibility is not permission to guess at
historical rules.

## Specification and registry versions

Recipe documents identify both versions separately. They MAY evolve
independently.

A registry release MUST never assign an existing unit ID a different meaning. If
a definition is wrong, a later release MUST deprecate or replace the ID and
document migration rather than mutate the old meaning silently.

Released registry IDs are permanent. They MUST NOT be removed or reused. A
deprecated ID remains valid for reading historical recipes, although current
writers MAY be prohibited from introducing it in new semantic data.

Aliases MAY be added or deprecated. Under the same language, locale, and case
matching conditions, a released alias MUST NOT be silently reassigned to a
different unit ID. If later registry growth creates additional legitimate
candidates, parsing MUST surface the ambiguity rather than silently changing a
previous result.

Every released registry snapshot MUST remain available so archived recipes do
not depend on a mutable online registry.

Readers SHOULD bundle every snapshot they support. Importing a recipe MUST NOT
require network access to resolve its schema or unit meanings. An unversioned
file on a development branch is not a released snapshot.

A reader encountering a newer registry version in the same compatibility line
MUST use its supported older snapshot for IDs that snapshot defines, because
released ID meanings are immutable. It MUST preserve syntactically valid unknown
IDs without guessing their semantics. Operations that depend on an unknown ID,
including conversion, normalization, and dimension checks, MUST be unavailable
for the affected value; the rest of the recipe remains usable where possible.

An ID absent from the exact registry snapshot named by a document is invalid.
Unknown-ID preservation applies only when the document names a newer compatible
registry that may legitimately contain additions.

A reader MUST NOT interpret a recipe under an incompatible or older registry
merely because the named snapshot is unavailable. It MAY offer an explicit
migration only when the replacement registry preserves every referenced unit
identity.

## Release artifacts

A specification release MUST include, in one immutable source archive:

- the prose specification and incorporated normative references;
- every schema identified by that release;
- the unit-registry snapshot used by its examples;
- complete examples and conformance fixtures;
- the conformance manifest; and
- migration guidance for any incompatible change, in that version's
  **Migrating** section of `CHANGELOG.md`.

The release check MUST pass from a clean checkout before the release is tagged.

### Release naming and publication

Release tags are exactly `vMAJOR.MINOR.PATCH`, for example `v0.4.0`. The
corresponding release is named `SREF vMAJOR.MINOR.PATCH` and publishes:

- `sref-vMAJOR.MINOR.PATCH.tar.gz`, the complete source release; and
- `sref-vMAJOR.MINOR.PATCH.tar.gz.sha256`, its SHA-256 checksum.

The archive is generated from the tagged Git tree with deterministic TAR and
gzip metadata. Tag CI unpacks it into a temporary directory outside the source
checkout and reruns schema, registry, conformance, archive-fixture, and snapshot
validation before publishing either file as a release asset.

To prepare a release candidate from a clean checkout:

```sh
python3 -m pip install -r requirements-dev.txt
just release 0.4.0
(cd dist && shasum -a 256 -c sref-v0.4.0.tar.gz.sha256)
```

`just release` fails if the working tree is dirty, the requested version does
not match the current SREF release and committed snapshot, any conformance check
fails, or the unpacked archive cannot validate independently.

After reviewing the resulting archive, promote the snapshot and create the tag:

```sh
just snapshots-promote 0.4.0
git push origin main v0.4.0
```

Promotion and tagging are one command. A snapshot's `manifest.json` records
whether it is a candidate or released, and `just snapshots-check` compares that
with whether the tag exists, so a commit that changed the state without the tag
would fail its own build. `snapshots-promote` writes the state, commits it, and
tags that commit, so the tagged tree already says what the tag makes true. It
refuses a dirty checkout, an existing tag, and a snapshot already marked
released.

Tag CI repeats the build from that exact commit and publishes the release; it
refuses to replace an already published file.

### Historical snapshot retrieval

Every release retains its exact schemas and registry under
`snapshots/MAJOR.MINOR.PATCH/`. The directory is available from the matching tag
even after the default branch advances. Implementers can download the complete
release archive or vendor only the files under, for example, `snapshots/0.4.0/`
at tag `v0.4.0`. They SHOULD verify those files against that snapshot's
`manifest.json`.

`just snapshots-check` verifies every snapshot inventory and digest, rejects a
snapshot changed after its matching tag, rejects schema `$id` reuse with
different bytes, and rejects removal, reassignment, or semantic mutation of a
released unit ID. It also prevents a released alias from being reassigned under
the same language and case-matching conditions. A release candidate must commit
the exact snapshot for its current version before it can pass.

### Release candidates and publication

A snapshot directory becomes immutable when its `vVERSION` tag exists. That tag
is the publication event: it is what implementers vendor against, and what the
release archive is built from. Until the tag exists, the directory is a release
candidate that MUST track the working tree it will be cut from, so that one
identifier never acquires two meanings.

While a version is an untagged candidate, a core addition extends that version
in place and its snapshot is refreshed:

```sh
just snapshots-refresh 0.4.0
```

The command refuses to touch a snapshot whose tag exists. After publication, a
new standardized core field requires a new version, and the immutability rules
above apply without exception. Either way, record the change under the candidate
version's heading in `CHANGELOG.md`, which says `Unreleased` until the tag
exists.

## Extensions

Extensions are not part of SREF version compatibility. A round-trip reader MUST
preserve an unknown extension without understanding it.

An extension cannot make a document conform to a standard field requirement or
change the meaning of a standard field. An application that requires an
extension MUST identify that additional requirement separately from its SREF
conformance claim.

Extension namespace ownership is established when the extension is first
published and does not track later DNS ownership automatically. Transfers and
subnamespace delegations must be explicit and publicly documented. See
[spec.md section 13](../spec.md#13-extensions) for the normative naming and
ownership rules.

Moving extension semantics into the core is a versioned specification change,
not an implicit change in how the extension is read. A migration must name the
new standard field and define how extension-bearing documents are converted;
readers must not silently treat the old extension member as that field.
