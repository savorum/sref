# Security assessment

This assessment covers the specification, schemas, unit registry, conformance
corpus, and the reference validator in this repository. The repository contains
no service and handles no credentials. Its security effect is on
implementations: every consumer of SREF parses input from an untrusted source.

[`SECURITY.md`](../SECURITY.md) lists the risk areas and how to report a
vulnerability.

## Method

Each risk area was reviewed against the specification for a requirement that
prevents it, and against the corpus for a test that fails an implementation that
lacks it. A risk without both is a gap.

## Findings

| Risk                                         | Requirement                         | Evidence                                                                                                                                  |
| -------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Path traversal, absolute paths, drive paths  | Specification section 15, items 1-3 | `unsafe-traversal`, `absolute-path`, `backslash-path`, `drive-letter-path`, `empty-path-segment` in [`tests/packages`](../tests/packages) |
| Control characters in names                  | Section 15                          | `control-character-path`                                                                                                                  |
| Links, devices, and other nonregular entries | Section 15, item 4                  | `symlink-entry`                                                                                                                           |
| Duplicate and colliding paths                | Section 15, item 5                  | `duplicate-entry`, and path collisions in [`conformance/test_security.py`](../conformance/test_security.py)                               |
| Compression bombs and oversized archives     | Section 15, item 7                  | `excessive-compression-ratio`, and the size, entry, and member limits in `conformance/test_security.py`                                   |
| Files the manifest does not account for      | Sections 15 and 16                  | `undeclared-file`, `missing-asset`, `asset-digest-mismatch`, `asset-size-mismatch`, `recipe-digest-mismatch`                              |
| Encrypted entries                            | Section 15                          | Invalid by definition                                                                                                                     |
| Hostile bundles and packages nested in them  | Section 19                          | Bundle cases in `conformance/test_security.py`, and the bundle fixtures in [`tests/bundles`](../tests/bundles)                            |
| Deep nesting, huge numbers, malformed UTF-8  | Sections 4 and 22                   | `conformance/test_security.py`                                                                                                            |
| Unsafe rendering of imported text and media  | Out of scope for the format         | The specification excludes rendering. An application that renders SREF content owns that risk.                                            |

## Repository controls

- CI installs its dependencies by hash and pins every action to a commit.
- Every commit needs a Developer Certificate of Origin sign-off.
- The default branch requires a reviewed pull request and passing checks.
- CodeQL analyzes the Python tools, and Dependabot proposes dependency updates.
- Release archives are signed and published with a checksum.

## Residual risk

The specification states requirements, and an implementation can still fail to
meet them. The [conformance runner](conformance-runner.md) tests an
implementation against the corpus, and both reference libraries pass it. A
report of a requirement that fails to prevent a described attack is a
vulnerability in this repository.
