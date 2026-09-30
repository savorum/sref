# Implementing SREF

This guide describes the minimum safe processing pipeline for SREF readers and
writers. It complements the normative requirements in
[the specification](../spec.md).

## Reader pipeline

Process a standalone recipe in this order:

1. Apply a byte limit before reading the document.
2. Decode UTF-8 without accepting a byte-order mark.
3. Parse strict JSON, rejecting duplicate members and nonfinite numbers.
4. Read the `sref` header without interpreting normalized recipe fields.
5. Classify both the recipe and unit-registry versions as exact, newer within
   the supported compatibility line, or unsupported. The two classifications are
   independent: a newer registry widens the unit vocabulary and says nothing
   about which members exist, and a newer recipe version widens the member
   vocabulary and says nothing about which unit IDs exist.

   The recipe classification decides which member vocabulary applies:

   ```text
   exact or known older version
       -> validate against that declared version's complete member vocabulary
       -> reject unknown non-extension members
   newer same-line version
       -> validate the supported standardized subset
       -> preserve unrecognized non-extension members opaquely
       -> do not claim complete validation of the newer version
   ```

6. Validate the known standardized subset against the reader's schema. Preserve
   unknown members in the original document rather than validating a projected
   copy and then discarding the source.
7. Load the exact registry snapshot when supported. For a newer compatible
   registry, use known immutable IDs from the supported snapshot and retain
   syntactically valid unknown IDs as opaque.
8. Enforce semantic rules: canonical rationals, range order, unique IDs,
   references, unit existence and dimensions, normalization provenance, and
   asset relationships. Treat recipe and step image references as authoritative;
   do not infer image placement from asset roles. Skip only those unit-dependent
   operations made unsafe by an opaque future registry ID.
9. Preserve author array order and every author field. Do not infer author kind
   or identity from a name, source, importer, or application-local user.
10. Preserve unknown standard members and extensions at their original scopes.
    When reading a known older version into a current model, map its members as
    that version's specification defines. The singular `yield` of a document
    that declares a version before 0.4.0 is the one element of `yields`.
11. Expose the accepted recipe to the caller only after every required check
    succeeds.

A reader MUST NOT partially import a document that fails validation unless the
calling application presents an explicit recovery workflow. Recovered data is
not conforming input and MUST retain the original bytes for diagnosis.

## Writer pipeline

Before writing a recipe:

1. Validate the in-memory model without relying on UI constraints.
2. Reduce every rational and enforce the interoperability bound.
3. Verify that standard units exist in the selected registry snapshot.
4. Verify recipe-wide IDs and references.
5. Preserve source text, normalization metadata, and opaque values.
6. Preserve unknown standard members, extension values, and their object scopes.
   If an edit makes safe reattachment impossible, require an explicit lossy
   conversion rather than silently dropping them.
7. Emit strict UTF-8 JSON without a byte-order mark.
8. Validate the emitted bytes by reading them through the normal reader path.

Reading the output back catches serializer mistakes that in-memory checks miss.

A newly authored document uses the writer's current version. When rewriting a
newer compatible document, preserve its declared newer version while carrying
unknown members unchanged, because the version identifies the rules those
members belong to. If an explicit lossy conversion removes every unsupported
member safely, the result MAY use the writer's current version. An application
MUST NOT claim to have interpreted future members merely because it retained
them.

## Package pipeline

Follow the extraction algorithm in [the package reference](package-format.md).
Do not extract first and validate later. Hashes and sizes apply to uncompressed
bytes and MUST be checked while streaming.

Package import is transactional: no recipe or asset becomes visible in
application storage until the manifest, recipe, and every declared asset have
passed validation.

## Bundle pipeline

A bundle is read outside-in: apply the archive rules to the container, verify
each member against the manifest, then hand each verified member to the ordinary
package pipeline. A correct digest only shows the bytes are intact, not that
they form a valid package.

A bundle is written the same way in reverse, and can be streamed. Write each
member under a unique bundle-local member ID while computing its digest and
size, record what was written, and write the manifest last. Do not derive that
identity from `recipe.id`; recipe-local IDs can repeat across members. ZIP
readers find entries through the central directory, so the manifest does not
need to be the first entry, and a writer does not need to hold the whole archive
in memory to produce one.

Members are already compressed. Store them rather than deflating them.

## Data ownership

The accepted recipe is source truth. Unit conversions, scaled quantities,
localized formatting, API objects, and rendered documents are projections. Cache
them if useful, but do not make a cache the only copy of authored data.

Application annotations (ownership, favorites, ratings, permissions,
collections, and history) belong in an application model outside the SREF
recipe.

## Error reporting

Every rejection MUST carry exactly one of the seven failure categories from
specification section 22.1 in machine-readable form: `invalid-artifact`,
`unsupported-format-version`, `unsupported-registry-version`, `unknown-unit`,
`integrity-failure`, `unsafe-archive`, or `resource-limit`. How you expose it is
up to you (an exception property, a result field, an enum, a JSON member). Use
`invalid-artifact` unless a more specific category clearly applies.

For the person fixing the document, include:

- a JSON location or archive path when available;
- the violated requirement;
- enough context to correct the input without exposing unrelated recipe data;
- a message in your own words.

Messages, exception classes, path formats, and your own detail codes are
implementation-defined; callers must not depend on them, or on the bundled
validator's wording. The corpus's `requirement_id` values are optional detail:
reporting them lets a conformance run confirm which rule you enforced, but they
are not part of SREF's error vocabulary.

Report every independent failure you can identify safely, each with its own
category (section 22.1). No validation order is prescribed, so finding a
different defect first is not a conformance failure (section 22.2).

## Verification

Run the bundled checks from the repository root:

```sh
python3 -m pip install -r requirements-dev.txt
python3 conformance/validate.py
python3 conformance/build_archive_fixtures.py --check
```

An implementation claiming a capability MUST also run the fixtures for that
capability through its own public reader or writer interface.
