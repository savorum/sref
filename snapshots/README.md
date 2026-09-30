# Version snapshots

Each directory is named for a SREF version and holds the exact schemas and unit
registry that version consists of. `manifest.json` records the file inventory,
the SHA-256 digests, and whether the snapshot is a **candidate** or
**released**.

A snapshot is released when its `vVERSION` tag exists; implementations vendor
the tagged snapshot, and the release archive is built from it. Before that, the
snapshot is a candidate that follows the working tree and can still change. See
[versioning](../docs/versioning.md#release-candidates-and-publication).

Current work continues in the top-level `schema/` and `registry/` directories.
An implementation should bundle the snapshot for the version it supports rather
than reading those, and should know which of the two states it bundled.

Run `just snapshots-check` to verify snapshot digests, schema identifiers,
released unit semantics, the correspondence between each `vVERSION` tag and its
committed snapshot, and that no snapshot's declared state disagrees with whether
that tag exists.
