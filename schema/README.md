# Schemas

All schemas use JSON Schema Draft 2020-12.

- `recipe.schema.json` defines standalone and packaged recipe documents.
- `manifest.schema.json` defines package integrity metadata.
- `bundle-manifest.schema.json` defines bundle member identity and integrity.
- `unit-registry.schema.json` defines registry snapshots.
- `ingredient-line-corpus.schema.json` defines parser expectations.
- `unit-conversion-corpus.schema.json` defines conversion vectors.
- `conformance-manifest.schema.json` defines the fixture index.

## Validation requirements

Implementations MUST enable format checking for schema keywords such as `uri`,
`date-time`, and `duration`. A validator that treats formats as annotations only
does not perform complete structural validation.

Schema validation is necessary but not sufficient. Cross-document references,
canonical fractions, ordered ranges, recipe-wide uniqueness, unit dimensions,
and package safety require the semantic checks in [`../spec.md`](../spec.md).

## Identifiers and snapshots

The `$id` of a released schema is immutable. A local filename is a repository
convenience and does not replace the identifier embedded in the schema.

Readers SHOULD bundle the exact schemas and registry snapshots they support.
They MUST NOT fetch an untrusted schema identifier over the network during
recipe import.

## Forward-compatible object members

Recipe objects allow unknown members so that an older schema can validate the
part of a newer compatible document it understands. JSON Schema cannot make
`additionalProperties` depend on the declared version, so the schema is open at
every version.

This does not allow unknown non-extension members in a document of the version
it declares. Specification section 13 limits them to newer compatible versions,
and section 23 makes the declared version's member list a semantic validation
rule.

Readers MUST preserve unknown members admitted that way at their original scopes
and MUST NOT infer their meaning. This permissiveness does not allow an unknown
member to satisfy a required standard field, and validation against an older
schema is not a claim of full support for the newer declared version.

Members beginning with `x-` remain explicitly namespaced extensions. An
extension cannot satisfy a required standard field or change standard semantics.
