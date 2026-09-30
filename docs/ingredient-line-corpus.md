# Ingredient-line corpus requirements

[`tests/amounts/ingredient-lines.json`](../tests/amounts/ingredient-lines.json)
defines the minimum parser behavior for difficult ingredient lines.

## Required behavior

For each case, a parser MUST:

1. Preserve `source_text` exactly.
2. Produce the `expected` ingredient semantics or a representation that is
   semantically identical under the SREF specification.
3. Avoid every inference listed in `must_not_infer`.
4. Preserve a quantity as opaque when the format cannot express its meaning
   without unsupported assumptions.
5. Apply the supplied `source_locale` only as evidence; it MUST NOT override an
   explicit regional qualifier in the line.

Locale-based alias matching MUST use the exact-to-general lookup procedure in
[Quantity and unit processing](quantity-and-units.md#alias-locale-lookup). Cases
with BCP 47 extensions verify truncation, region-specific aliases verify that a
winning exact level outranks generic-language aliases, and unmatched regions
verify that lookup does not search sibling locales.

For ordinary `en-US` text, unqualified `cup`, `tablespoon`, and `teaspoon`
aliases identify the exact US customary units. A parser MUST select the rounded
240 mL, 15 mL, or 5 mL culinary identity only when the source explicitly defines
that convention.

The three are equally region-bound, so none of them resolves from a source that
states only a language. A bare `tsp` under `en`, under `en-CA`, or under no
locale at all stays opaque, exactly as a bare `cup` does; `metric teaspoon`
still identifies the 5 mL culinary spoon. Where a person supplies the missing
evidence, [specification section 9.5](../spec.md#95-resolution-decisions)
governs what their answer settles, and the vectors for it are separate from this
corpus.

Cases with a `source_locale` in another language check that a parser reads the
line by that language's alias sets and by the order that language writes a
quantity. Japanese writes a unit before its number (`大さじ2`), and Japanese,
Korean, Chinese, and Thai list the ingredient before its quantity
(`小麦粉 200g`). Decimal digits of any script are numbers, and a connective that
only joins a measure to what it measures (`de`, `d'`, `di`) belongs to neither.
A measure whose size differs between countries has no alias, so its quantity
stays opaque, and a source locale in one language does not reach the aliases of
another. The same holds for a spoon word whose capacity differs between
publishers, and for a cup the line describes as a paper cup or a rice-cooker
cup. A spoon followed by a stated equivalent that differs from the registry's
size by more than a tenth stays opaque. A broad word with no alias is read in
the sense its ingredient selects: `gousse d'ail` is a clove, and
`gousse de vanille` and `boîte de chocolats` are counts of the ingredient. A
measure word that contains the number one (`ひとつまみ`, `sejumput`) is an
amount of one. A counting classifier (`枚`, `切れ`, `片`) is read as a count of
the ingredient, and the classifier stays in the source text. Forms are matched
in canonical composition and no other normalization.

`classification` has these meanings:

- `structured`: the quantity and relevant note are represented structurally.
- `partial`: only the semantics that can be defended are structured; the
  remainder stays in the source text or note.
- `opaque`: the quantity expression remains opaque.

## Comparison

Conformance comparison MUST include:

- ingredient name;
- exact rational values and ranges;
- quantity-expression kind and term order;
- semantic unit IDs;
- note text;
- package size; and
- exact source text.

A parser MAY retain additional field-level provenance through extensions. When
the expected ingredient includes `normalization`, the parser MUST preserve its
method, review state, and warnings. Additional metadata MUST NOT replace
required source text or change the expected unit identity.

## Corpus changes

Every parser bug involving quantity, unit, packaging, ingredient-tail meaning,
or source preservation MUST add a distinct regression case.

A new case MUST test a semantic condition not already covered by another line.
Changing an expected result requires a specification change or a documented
correction to an objectively inconsistent fixture.
