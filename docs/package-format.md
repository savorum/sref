# Package format reference

## Overview

A SREF package is a ZIP archive containing one recipe and all assets declared by
that recipe. Its file suffix is `.sref`.

Minimum layout:

```text
manifest.json
recipe.json
```

Layout with assets:

```text
manifest.json
recipe.json
assets/
  hero.jpg
  step-01.png
```

## Required entries

The archive MUST contain exactly one regular-file entry named `manifest.json`
and one named `recipe.json` at the archive root.

Every declared asset MUST appear once at the exact relative path declared by the
recipe and manifest.

No other archive entries are allowed. Readers MAY ignore explicit directory
entries. Writers MUST omit them.

## Manifest

`manifest.json` validates against
[`schema/manifest.schema.json`](../schema/manifest.schema.json).

It identifies the package version and records the uncompressed byte size and
lowercase SHA-256 digest of `recipe.json` and each asset.

The manifest does not list itself because a self-digest would be recursive.

## Agreement rules

Recipe and manifest asset declarations MUST agree exactly on:

- ID;
- path;
- media type;
- byte size; and
- SHA-256 digest.

An asset present in only one declaration is invalid.

## Paths

All paths use `/` separators and are relative to archive root.

Asset paths MUST begin with `assets/`. Empty segments, `.` segments, `..`
segments, leading `/`, backslashes, drive letters, NUL, and control characters
are invalid.

Readers MUST compare paths after Unicode NFC normalization and Unicode case
folding. They MUST use that form only to detect duplicates: validation and
diagnostics retain the original name, and an unsafe path is never normalized
into an accepted path.

## Entry types

Only regular files are permitted. Readers MUST reject symbolic links, hard
links, devices, FIFOs, sockets, and implementation-specific link encodings.

Encrypted entries are invalid.

## Resource limits

Every reader MUST set finite limits before processing untrusted packages. The
exact limits are implementation policy and SHOULD be configurable, but MUST
cover:

- archive bytes;
- total expanded bytes;
- bytes per entry;
- entry count;
- path length;
- JSON nesting and string sizes; and
- JSON numeric allocation; and
- compression ratio.

Implementations MUST fail safely when a limit is exceeded.

A limit's value is implementation policy, but it MUST be a value this format can
actually reach, or it is not a limit. A single DEFLATE stream cannot exceed
roughly 1032:1 (258 bytes of match per couple of bits), and in practice tops out
near 1029:1 whatever the entry's size. A per-entry compression-ratio ceiling set
above that can never be crossed by a conforming archive, so an implementation
carrying one has not imposed the limit this section requires, however
configurable the value is.

## Extraction algorithm

A package reader MUST:

1. Read the central directory without extracting.
2. Reject unsafe names, types, duplicates, encryption, and limit violations.
3. Read and validate `manifest.json` under a strict size limit.
4. Stream `recipe.json`, verifying size and digest.
5. Validate the recipe structurally and semantically.
6. Compare recipe and manifest asset declarations.
7. Stream each asset while verifying size and digest.
8. Write only to memory or an isolated temporary destination.
9. Commit accepted data to application storage only after complete validation.

Never join an unvalidated archive path to a destination path.

## Compression and reproducibility

SREF does not require a specific ZIP compression method or byte-for-byte
reproducible archive.

Writers MUST use broadly supported ZIP features and MUST avoid platform-specific
metadata. Readers MUST NOT rely on timestamps, entry order, or archive CRC as
recipe semantics.

## Media types

Asset media types are declared metadata and MUST be checked against actual
content before unsafe decoding or rendering. File extensions and declared media
types are not trustworthy on their own.

SREF does not assign a registered media type.
