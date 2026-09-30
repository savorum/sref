# SREF

SREF (Structured Recipe Exchange Format) is an application-independent exchange
format for recipes and their assets. It is designed so an exported recipe
remains complete, intelligible, and implementable without the application that
created it.

This repository contains the specification, JSON Schemas, culinary unit
registry, examples, and executable conformance corpus. It is not a runtime
parsing library or an application database schema.

## Start here

- [Author and validate a recipe](docs/authoring-recipes.md).
- [Implement a reader or writer](docs/implementation-guide.md).
- [Find normative reference and explanatory guides](docs/README.md).
- [Contribute and validate the repository](CONTRIBUTING.md).

## Representations

SREF defines two representations of one recipe model:

- a standalone UTF-8 JSON document, conventionally named `name.recipe.json`; and
- a ZIP package, conventionally named `name.sref`, containing exactly one
  `recipe.json`, one `manifest.json`, and any declared files below `assets/`.

The standalone form is self-contained only when it declares no assets. The
package form adds integrity, completeness, and archive-safety requirements.

Many recipes travel together as a bundle, conventionally named
`name.srefbundle`: a ZIP archive of complete packages in a stated order. A
bundle is a container rather than a third recipe representation, so extracting
one member gives an ordinary `.sref` that needs nothing else. A bundle is not an
application backup.

## Versions and evidence

The working specification and fixtures describe this checkout. Released schemas
and registries live in [immutable snapshots](snapshots/README.md). The format
and unit registry are versioned independently; neither is a Savorum application
release or a Python package version. [Versioning](docs/versioning.md) owns
compatibility rules, release artifacts, and snapshot retrieval.

A conformance result names an implementation and the exact specification
revision used. The [corpus declaration](conformance/recipe-corpus.json)
separately pins optional private regression evidence and its evaluated target
revision. Public conformance tests use this repository's own fixtures and do not
require the private corpus. Moving a pin changes the evidence and requires
review.

## Reference implementations

Two Python implementations exist, each claiming one half of the conformance
capabilities. They have one author and share one reading of the specification,
so a point the specification leaves open is settled the same way in both. An
implementation by someone else is what tests those points.

- [**SREF Reader**](https://github.com/savorum/sref-reader) (`sref-reader`)
  reads recipe documents, packages and bundles, and implements the registry and
  unit conversion.
- [**SREF Writer**](https://github.com/savorum/sref-writer) (`sref-writer`)
  emits recipe documents, packages and bundles.

Each claims its own capabilities; neither claims round-trip conformance alone.
The repository validator checks SREF artifacts. The conformance runner exercises
an implementation's public interface. Passing the validator is not an
implementation conformance claim, and JSON Schema alone does not establish
semantic or archive safety. See [conformance](docs/conformance.md).

## License and contributions

Specification data and documentation are dedicated under CC0 1.0 Universal.
Reference code is licensed under the MIT License. See [`LICENSE.md`](LICENSE.md)
for the artifact map.

Contributions require a Developer Certificate of Origin sign-off and the
evidence described in [`CONTRIBUTING.md`](CONTRIBUTING.md).
