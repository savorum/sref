# Bundle format reference

## Overview

A SREF bundle is a ZIP archive carrying an ordered collection of complete SREF
packages. Its file suffix is `.srefbundle`.

A bundle carries many recipes in one file. It is not another recipe
representation and not an application backup. Each member contains everything
needed to read its recipe.

Layout:

```text
manifest.json
recipes/
  r000001.sref
  r000002.sref
  r000003.sref
```

## Required entries

The archive MUST contain exactly one regular-file entry named `manifest.json` at
the archive root, and exactly one entry for each recipe the manifest declares.

No other archive entries are allowed. Readers MAY ignore explicit directory
entries. Writers MUST omit them.

A bundle declares at least one recipe.

## Members

Every member below `recipes/` is a complete SREF package as defined by
[the package format reference](package-format.md). A member carries its own
`manifest.json`, its own `recipe.json`, and the bytes of every asset its recipe
declares.

Any single member, extracted on its own, is a usable recipe. A member MUST NOT
reference a file in another member, in the bundle root, or in a shared asset
area; version 1 has no shared asset area. An asset used by two recipes is
therefore stored twice.

## Member paths

A member path is:

```text
recipes/<member-id>.sref
```

`<member-id>` is a bundle-local identity chosen independently of the recipe
document inside the member. It matches the portable identifier syntax, so the
resulting path can contain no separator, no `.` or `..` segment, no backslash,
and no control character.

Member IDs and member paths MUST each be unique within a bundle. Recipe IDs are
local to their own recipe documents and need not be unique across members. A
writer MUST NOT mutate a recipe ID or any recipe-local reference to make a
member unique.

A member ID is transport identity only. It has no meaning outside its bundle and
MUST NOT be copied into or substituted for recipe-local identity. Writers SHOULD
generate opaque IDs from bundle order, such as `r000001`, rather than reuse a
title, filename, or application database identifier.

## Manifest

`manifest.json` validates against
[`schema/bundle-manifest.schema.json`](../schema/bundle-manifest.schema.json).

```json
{
  "format": "sref-bundle",
  "version": 1,
  "recipes": [
    {
      "member_id": "r000001",
      "recipe_id": "apple-pie",
      "path": "recipes/r000001.sref",
      "sha256": "b32d…",
      "size": 12345
    },
    {
      "member_id": "r000002",
      "recipe_id": "sourdough",
      "path": "recipes/r000002.sref",
      "sha256": "9f01…",
      "size": 23456
    }
  ]
}
```

The bundle manifest does not list itself, for the same reason a package manifest
does not: a self-digest would be recursive.

`sha256` and `size` describe the exact uncompressed bytes of the member, which
are the bytes of the `.sref` file. They do not describe the recipe document
inside it; that document is covered by the member's own manifest.

### Order

`recipes` is ordered and the order carries meaning. It is the order the producer
intended, such as the order a person selected or the order a collection is
arranged in. A reader MUST preserve it when listing or importing the bundle.

### What the manifest does not carry

A bundle manifest records only what identifies and verifies its members. It MUST
NOT carry:

- local database identifiers;
- collection, book, or chapter identity;
- tags, categories, ratings, or favorites;
- cooking history or revision numbers;
- the name or version of the writing application; or
- a generation timestamp.

A timestamp in particular is excluded to avoid variation unrelated to recipe
content. Its absence does not make semantically equivalent bundles
byte-identical: JSON and ZIP serialization are noncanonical, and equivalent
recipe packages may have different member bytes and digests.

## Reading a bundle

A bundle reader MUST:

1. Apply the package-format archive rules to the outer archive: reject unsafe
   names, nonregular entries, duplicates, encryption, and limit violations.
2. Read and validate `manifest.json` under a strict size limit.
3. Reject any archive entry the manifest does not declare, and any declared
   entry the archive does not carry.
4. Reject duplicate member IDs and duplicate member paths, and reject a member
   path that is not `recipes/<member_id>.sref`.
5. Stream each member, verifying its declared size and SHA-256 digest.
6. Process each verified member as a package, applying the complete package
   reader algorithm to it.
7. Confirm that each member's recipe `id` equals the informational `recipe_id`
   the bundle manifest declares for it. Duplicate `recipe_id` values are valid.
8. Write only to memory or an isolated temporary destination, and commit only
   after complete validation.

A correct digest shows the bytes are intact, not that they form a valid package,
so step 6 is required.

## Resource limits

A bundle reader MUST set finite limits independently of the limits it applies
inside a member, covering at least:

- bundle archive bytes;
- total expanded bytes;
- member count;
- bytes per member; and
- compression ratio.

A member-count limit is an implementation or deployment resource policy, not a
format maximum. The bundle schema therefore accepts any nonempty member count. A
reader MAY reject a structurally valid bundle that exceeds its configured limit,
and SHOULD identify the resource limit rather than report the manifest as
schema-invalid. Producers cannot assume that every receiver has the same limits.

A member that exceeds a package limit fails; it does not cause the reader to
relax the limit for the next one.

As in a package, a limit's value is implementation policy but MUST be reachable.
A compression-ratio ceiling above roughly 1032:1 is above what DEFLATE can
produce, and so imposes nothing; see the resource-limit section of
[package-format.md](package-format.md).

## Compression and reproducibility

SREF does not require canonical recipe, package, or bundle bytes, and a reader
MUST NOT depend on them. A digest identifies exact bytes rather than semantic
equivalence.

A writer SHOULD nevertheless avoid unnecessary nondeterminism and produce
identical bundle bytes when given the same exact member bytes in the same order:
normalize archive member metadata rather than recording local filesystem
timestamps, and store rather than deflate members, which are already compressed
archives. Recompressing a ZIP inside a ZIP costs time and saves little.

## Media type

SREF does not assign a registered media type. Until one exists, serving a
`.srefbundle` as `application/zip` is reasonable. Applications MUST NOT invent
an unregistered `application/vnd.…` type for it.
