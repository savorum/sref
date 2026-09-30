# Contributing to SREF

SREF accepts focused changes that improve durable recipe interchange. Start by
reading [the specification](spec.md),
[the design rationale](docs/design-rationale.md), and
[the change process](docs/change-process.md).

## Contribution terms

Contributions are licensed according to the artifact map in
[`LICENSE.md`](LICENSE.md). By contributing, you agree that specification data
and documentation may be released under CC0 1.0 Universal and reference code
under the MIT License.

Every commit MUST include a Developer Certificate of Origin sign-off:

```text
Signed-off-by: Your Name <your-email@example.com>
```

Create it with `git commit -s`. The sign-off certifies the statement in
[`DCO.txt`](DCO.txt). CI rejects a commit whose sign-off does not name its
author.

## Set up the repository

Use Python 3.10 or later and Node.js with `npx`, then install the development
dependencies, which include the `just` command runner:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
just check
```

`just check` checks Markdown formatting, validates schemas and fixtures,
executes semantic and conversion checks, compiles the Python programs, and
verifies deterministic package fixtures. `just format` formats Markdown with
Prettier at an 80-column prose width. These checks use only this repository's
contents and installed development dependencies.

Maintainers with access to the private recipe corpus can additionally run
`just corpus-check /path/to/pinned/recipe-corpus`. The checkout must match the
commit in [`conformance/recipe-corpus.json`](conformance/recipe-corpus.json).
The optional check reads `SREF_RECIPE_CORPUS_ROOT` or `../recipe-corpus` when no
path is supplied, and fails on a missing checkout or a different commit.
`just check /path/to/pinned/recipe-corpus` includes this optional check in a
full run. Public CI runs `just check` without it. Keep private checkouts and
generated application exports outside this repository or in ignored
`local-private/` storage.

## Choose the smallest correct change

- Editorial corrections MUST preserve normative meaning.
- New recipe semantics MUST update the specification and schema together.
- New rejection rules MUST include an invalid fixture with a distinct error
  category.
- New ordinary recipe structures MUST appear in a complete example.
- Unit changes MUST include an official or primary standards reference and
  parsing-ambiguity analysis.
- Package changes MUST include hostile as well as valid fixtures.

Do not add application accounts, ratings, favorites, collections, storage IDs,
or synchronization state to the recipe model.

## Write fixtures

Every fixture MUST be indexed in `conformance/manifest.json`. The validator
rejects unindexed files under the fixture directories.

Ingredient-line cases MUST test a distinct semantic condition. Do not add a line
solely to increase the corpus size. State prohibited inferences whenever a naive
parser could fabricate meaning.

Rebuild package archives after changing their readable staging files:

```sh
just fixtures
just check
```

## Style

- Keep each behavior in one authoritative document; route readers there from the
  README.
- State prerequisites and working directories, and run examples before changing
  them.
- Distinguish format and registry versions, implementation releases, and corpus
  pins.
- Use concise, specific terms without em dashes.
- Use direct, prescriptive language for requirements.
- Use `MUST`, `MUST NOT`, `SHOULD`, and `MAY` only with their meanings in the
  specification.
- Keep examples plausible and internally consistent.
- Preserve Unicode source text rather than transliterating it for convenience.
- Prefer explicit semantic checks over comments that merely describe a risk.
- Keep Python reference code dependency-light and safe on untrusted input.

## Proposing a change

Describe the interoperability problem, compatibility effect, and fixtures that
demonstrate the result. A normative change MUST satisfy
[`docs/change-process.md`](docs/change-process.md).

Maintainers may ask for a proposal to be narrowed or moved to an extension when
the semantics are application-specific or insufficiently established. A proposal
that adds a new core semantic MUST address the core-admission criteria in
[`docs/change-process.md`](docs/change-process.md#core-admission), including the
evidence for recurrence, the core gap, and why an extension is inadequate.
