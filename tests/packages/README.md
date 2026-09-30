# Package fixtures

The `.sref` files in this directory are deterministic conformance fixtures. Run
`python3 conformance/build_archive_fixtures.py` from the repository root after
changing the readable source directory.

Run `python3 conformance/build_archive_fixtures.py --check` to rebuild in an
isolated directory and compare the result with committed archives.

- `valid-with-asset.sref` is a complete package with text and image assets; its
  recipe-local and asset IDs exercise the digit-leading portable-ID grammar.
- `missing-asset.sref` declares an asset but omits its archive entry.
- `undeclared-file.sref` contains an archive entry that neither the recipe nor
  manifest declares.
- `asset-digest-mismatch.sref` changes asset bytes without changing their size.
- `asset-size-mismatch.sref` changes an asset's size.
- `recipe-digest-mismatch.sref` changes valid recipe bytes after the manifest
  digest was calculated.
- `manifest-disagreement.sref` gives an asset a different media type in the
  recipe and manifest.
- `duplicate-manifest-asset.sref` repeats an asset declaration in the manifest.
- `manifest-duplicate-version.sref` repeats the package version member.
- `manifest-duplicate-recipe-digest.sref` repeats an integrity-bearing recipe
  digest member.
- `manifest-trailing-value.sref` appends a second JSON value after the complete
  manifest.
- `unsafe-traversal.sref`, `backslash-path.sref`, and `absolute-path.sref`
  exercise unsafe archive names.
- `drive-letter-path.sref` and `control-character-path.sref` exercise two
  additional path forms that must never reach extraction.
- `empty-path-segment.sref` places an empty segment in an archive name.
- `duplicate-entry.sref` repeats a required root entry.
- `symlink-entry.sref` contains a non-regular archive member.
- `missing-manifest.sref` and `missing-recipe.sref` omit required root entries.
- `malformed-recipe-json.sref` contains malformed JSON encoded as UTF-8.
- `excessive-compression-ratio.sref` exceeds the reference validator's finite
  compression-ratio limit.
- `not-a-zip.sref` verifies that malformed archive bytes fail safely.

The `valid-with-asset/` directory contains the readable source material used to
produce the archives. The source directory also contains `extra.txt`, which is
included only in the undeclared-file fixture.

The builder fixes member timestamps, ordering, mode bits, and compression.
Conformance still depends on package meaning, not byte identity.
