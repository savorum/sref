# Conformance tooling

`validate.py` checks the repository's schemas, registry, fixture index, recipes,
ingredient-line expectations, unit-conversion vectors, and package archives. It
also performs semantic checks that JSON Schema cannot express.

`build_archive_fixtures.py` creates deterministic valid and hostile `.sref`
archives from readable staging material under `tests/packages/`, and the
`.srefbundle` archives under `tests/bundles/` from the packages it just built.

## Commands

From the repository root:

```sh
python3 -m pip install -r requirements-dev.txt
python3 conformance/validate.py
python3 conformance/build_archive_fixtures.py --check
```

### Pinned recipe-corpus loss audit

`recipe-corpus.json` pins a commit of the private recipe-corpus repository and
its full SREF loss audit. `validate_recipe_corpus.py` reads only the corpus's
generated coverage report and derived SREF targets, never source recipes, scans,
reference-only observations, or application exports. The rules it enforces are
described in
[the conformance guide](../docs/conformance.md#external-corpus-loss-audit).

`just check` runs all public validation without external checkouts. This
includes the loss-audit validator's unit tests, which create synthetic reports
and Git repositories in temporary directories. Maintainers run the additional
private audit by passing its path or setting `SREF_RECIPE_CORPUS_ROOT`:

```sh
just corpus-check /path/to/recipe-corpus
```

Use `python3 conformance/build_archive_fixtures.py` only when intentionally
rebuilding committed package and bundle fixtures.

## Scope

The bundled validator verifies this repository and serves as readable reference
code. It does not grant conformance to another implementation. External readers
and writers MUST run applicable fixtures through their own public interfaces as
described in [`../docs/conformance.md`](../docs/conformance.md).
