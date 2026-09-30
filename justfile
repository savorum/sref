prettier := "npx --yes prettier@3.9.6"

[private]
default:
    @just --list

# The canonical verification; CI runs this recipe rather than restating it.
#
# When `corpus_root` is provided, also validates against the pinned recipe-corpus
# checkout (see conformance/README.md).
[doc('Run every check CI runs')]
check corpus_root="": format-check
    python3 -m py_compile conformance/validate.py conformance/test_security.py conformance/validate_recipe_corpus.py conformance/test_validate_recipe_corpus.py conformance/build_archive_fixtures.py conformance/runner.py conformance/roundtrip_audit.py conformance/semantics.py conformance/test_runner.py tools/check_snapshots.py tools/release.py tools/release_notes.py
    python3 conformance/validate.py
    python3 conformance/test_security.py
    python3 conformance/test_validate_recipe_corpus.py
    python3 conformance/test_runner.py
    {{ if corpus_root != "" { "just corpus-check " + quote(corpus_root) } else { "" } }}
    python3 conformance/build_archive_fixtures.py --check
    python3 tools/check_snapshots.py

[doc('Format Markdown')]
format:
    {{ prettier }} --write "**/*.md"

[doc('Check Markdown formatting')]
format-check:
    {{ prettier }} --check "**/*.md"

[doc('Validate schemas and fixtures')]
validate:
    python3 conformance/validate.py

[doc('Validate against the pinned recipe corpus')]
corpus-check corpus_root="":
    python3 conformance/validate_recipe_corpus.py {{ if corpus_root != "" { "--corpus-root " + quote(corpus_root) } else { "" } }}

[doc('Rebuild the deterministic archive fixtures')]
fixtures:
    python3 conformance/build_archive_fixtures.py

[doc('Build release artifacts for a version')]
release version:
    python3 tools/release.py --version {{ quote(version) }}

[doc('Verify every snapshot')]
snapshots-check:
    python3 tools/check_snapshots.py

# Writes the released state, commits it, and tags that commit in one step,
# because the state and the tag must not be committed separately (see
# docs/versioning.md).
[doc('Promote a candidate snapshot to released and tag it')]
snapshots-promote version:
    python3 tools/promote_snapshot.py --version {{ quote(version) }}

[doc('Refresh a candidate snapshot from the working tree')]
snapshots-refresh version:
    python3 tools/refresh_snapshot.py --version {{ quote(version) }}
