# Quantity and unit processing

This document defines how implementations resolve, convert, scale, and display
SREF quantities. The requirements in this document are normative.

## Processing boundary

An implementation handles four distinct operations:

1. **Parsing** maps written text to a quantity and semantic unit when the
   evidence is sufficient.
2. **Conversion** maps a physical quantity between compatible semantic units.
3. **Scaling** changes scalable recipe amounts by a requested yield factor.
4. **Formatting** presents a quantity for a person and locale.

These operations MUST remain separate. In particular, a display conversion MUST
NOT mutate the imported quantity, its unit ID, its source text, or its
normalization metadata.

## Resolving written units

Aliases are candidates, not identities. A parser narrows candidates using
evidence in this order:

1. an explicit regional or standards qualifier in the ingredient line;
2. an explicit equivalence in the source, such as `250 mL (1 Australian cup)`;
3. a documented convention attached to the source application or publication;
4. an explicit resolution decision supplied for this normalization, as defined
   by [specification section 9.5](../spec.md#95-resolution-decisions);
5. a source locale, when that locale selects exactly one candidate.

Evidence later in the list MUST NOT override evidence earlier in the list.
Display locale is never source evidence, and a resolution decision is evidence
about this normalization only: it is not a stored property of the recipe and
does not carry to a later import.

### Alias locale lookup

When `source_locale` is used to match a written alias, a parser MUST treat that
tag as the sole language range in a language priority list and apply the
truncation rule from
[RFC 4647 section 3.4, Lookup](https://www.rfc-editor.org/rfc/rfc4647.html#section-3.4).
It MUST:

1. Start with the complete `source_locale` tag.
2. Compare that tag with alias-set `language` tags using ASCII case-insensitive
   comparison. Implementations MUST NOT make additional preferred-value or
   likely-subtag substitutions during matching.
3. Within that locale level, apply each alias set's declared case policy to the
   written form and collect every matching unit.
4. If the level produced one or more candidates, stop. Those candidates are the
   complete locale-derived candidate set.
5. Otherwise remove the rightmost subtag. If that leaves a single-character
   extension singleton at the end, remove the singleton too, then try the
   resulting tag. Continue until the primary language has been tried.

For example, `en-US-u-nu-latn` tries:

```text
en-US-u-nu-latn
en-US-u-nu
en-US
en
```

If `cup` matches an `en-US` alias, lookup stops there; an `en` alias for the
same form does not join or replace the candidate set. If `gram` has no `en-US`
alias, lookup may continue and match its `en` alias. Candidates that collide at
the same winning level remain ambiguous unless stronger source evidence selects
one.

The lookup chain has no wildcard or locale-unspecified terminal level. A parser
MUST NOT use alias sets from a sibling or otherwise unrelated locale. Thus an
`en-CA` source does not acquire plain `cup` aliases from `en-US`, `en-GB`, or
`en-AU`.

An explicit regional or standards qualifier, explicit source equivalence, or
documented source convention MAY identify a unit before locale lookup. That is
stronger source evidence, not permission to fall back to an unrelated locale.

A source locale can distinguish an Australian tablespoon from a United States
tablespoon. For ordinary `en-US` text, unqualified `cup`, `tablespoon`, and
`teaspoon` aliases identify the exact United States customary units. The rounded
240 mL, 15 mL, and 5 mL culinary equivalencies are not generic parser
candidates; NIST publishes them as approximate cooking conversions rather than
as the identities asserted by ordinary US recipe text.

An explicit equivalence in the source or a documented convention attached to the
source MAY directly identify one of those rounded culinary units even when the
written unit uses a generic label. The evidence MUST define the relevant volume,
not merely identify the source as American. When more than one candidate still
remains, the parser MUST retain an opaque quantity or mark the normalization as
unresolved. It MUST NOT choose the first registry match.

UCUM's 5 mL `[tsp_m]` and 15 mL `[tbs_m]` are registered as
`volume.teaspoon.us.legal` and `volume.tablespoon.us.legal`, matching the exact
household measures defined for United States nutrition labeling. They are not
generic parser candidates. Ordinary `en-US` `tsp` and `tbsp` still identify the
exact US customary units; a source must explicitly identify the legal measure or
carry a documented nutrition-labeling convention to select the legal identity.

`volume.teaspoon.metric` and `volume.tablespoon.metric` are permanently
unassigned, as the bare metric cup ID is. `volume.teaspoon.metric.culinary` is
the 5 mL spoon of ordinary metric culinary practice. The qualified English forms
`metric teaspoon` and `metric teaspoons` select it; bare English teaspoon forms
do not. A bare teaspoon is as region-bound as a bare cup: it resolves from a
regional alias set, from stronger source evidence, or from a resolution
decision, and otherwise stays ambiguous.

A bare English `tablespoon` does not establish a single magnitude: Australian
culinary usage defines 20 mL, while current Canadian and New Zealand
food-composition sources use 15 mL. New Zealand law does not define a
tablespoon, and older joint FSANZ material also uses 20 mL. The registry
therefore keeps the sourced 20 mL `volume.tablespoon.au` identity and gives
`volume.tablespoon.metric.culinary` no bare English alias. The phrases
`metric tablespoon` and `metric tablespoons` select the 15 mL identity, and
`Australian cup`, `Australian tablespoon`, and `Australian teaspoon` select the
Australian identities, from any English source locale. Ambiguous English source
text remains opaque.

### Spoon words in other languages

Three questions stay separate: whether a word names a spoon, which unit identity
the word selects, and how that identity converts. A language tag is evidence
about the language of the source. It does not establish the capacity of a
household utensil.

A word selects an identity where recipes in that language conventionally use
that measuring spoon and the registry cites a source for it. The metric
measuring spoons are distinct from ordinary household utensils, whose capacity
varies. The tablespoon words of the languages listed in the
[registry README](../registry/README.md#aliases-in-other-languages) select
`volume.tablespoon.metric.culinary` under a source locale of that language, and
their teaspoon words select `volume.teaspoon.metric.culinary`. These are
language-scoped aliases like any other: they apply only when the source locale
selects that language, and a source locale of another language does not reach
them.

A spoon word whose capacity differs between publishers has no alias, and a line
that uses it stays opaque. Portuguese `cc` is a 5 mL tea measure in one
publisher's legend, a 2.5 mL coffee measure in another, and a cubic centimetre
elsewhere. Turkish sources give the tea spoon as 2.5 mL or 5 mL and the
tablespoon as 10 mL or 15 mL. A source that states its own measure identifies it
by that statement, and the original text is kept: a spoon followed by an
equivalent in millilitres that differs from the registry's size by more than a
tenth stays unresolved. A resolution decision made for the ingredient is not
overridden.

Explicit source wording and documented conventions outrank a locale-derived
candidate. An alias identifies a word; it does not interpret a line. A parser
MAY read a bare word that has no alias in the sense the ingredient establishes,
as `gousse d'ail` is a clove and `gousse de vanille` is not. Without that
context the line keeps its wording and an unresolved quantity, and an unrelated
dictionary sense alone does not forbid the contextual reading.

A nutrition-labeling convention that defines household measures is a different
convention from culinary practice. Brazilian nutrition labeling specifies a 10
mL tablespoon and a 200 mL cup for label declarations. `colher de sopa` selects
the 15 mL culinary tablespoon, and a source that declares the labeling
convention identifies its measure by that declaration. The
[registry README](../registry/README.md#sources-and-alias-policy) records the
sources.

## Matching a written form

An implementation compares a written unit form with registered forms as follows:

1. Both are put in Unicode NFC, so a composed and a decomposed spelling of one
   form match.
2. A case-sensitive alias set compares the composed forms exactly. Any other set
   compares under Unicode case folding.
3. No other transformation is applied. Compatibility normalization (NFKC or
   NFKD), accent stripping, script conversion, and lookalike mapping are not
   part of matching, so a fullwidth `ｍｌ`, the single character `℃`, or a
   Cyrillic `м` written beside a Latin `c` matches only a form registered that
   way.

The case-insensitive set for `ml` also matches `ML` and `Ml`, and `mL` is
registered separately as a case-sensitive symbol. This tolerance is not strict
SI or UCUM parsing.

An importer MAY apply its own documented preprocessing to a line before
matching. It MUST keep the original text as `source_text`. Registered forms are
NFC and carry no surrounding whitespace.

The same rule governs the larger liquid measures. `fl oz`, `pint`, `quart`, and
`gallon` resolve to the United States family under `en-US` and to the imperial
family under `en-GB`; `imperial pint` and `US pint` resolve by explicit
qualifier regardless of which of those locales supplies the text. A line that
carries neither remains opaque, because the two readings differ by about twenty
percent and no default is defensible.

`metric cup` identifies the 250 mL culinary cup. The 240 mL cup that United
States nutrition labeling defines, which UCUM encodes as `[cup_m]`, is
registered as `volume.cup.us.legal` and is never selected by a generic `cup` or
`metric cup` alias; a source asserting it MUST name it or state the volume. The
reverse also holds: `volume.cup.metric.culinary` is not a rounding of the US
customary cup, and an `en-US` `cup` MUST NOT resolve to it.

## Exact representation

Normalized quantity components are nonnegative rational numbers. Temperature
components MAY have a leading minus sign; negative zero is invalid.
Implementations MUST perform authoritative arithmetic with integers or rational
numbers, not binary floating point.

The exchange representation's unsigned 64-bit interoperability bound applies to
each serialized numerator and denominator. An internal calculation MAY use wider
values. Before writing a result, the writer MUST reduce it and verify the bound.

## Physical conversion

Every physical dimension has one registry base unit. Treat a base definition as
having multiplier `1` and offset `0`.

For a source value `x`, source multiplier `mₛ`, and source offset `oₛ`, compute
the base value:

```text
b = x × mₛ + oₛ
```

For target multiplier `mₜ` and target offset `oₜ`, compute:

```text
y = (b - oₜ) / mₜ
```

All four registry values and both calculations MUST use exact rational
arithmetic. A conversion is permitted only when source and target are physical
units with the same dimension. Mass, volume, temperature, and length are
distinct dimensions.

If the source amount is approximate, or any source or target definition used by
the conversion has `exact: false`, the result MUST be presented as approximate.
An implementation MUST NOT remove an existing approximation marker merely
because the arithmetic is exact.

### Ranges

Convert both endpoints independently. Registry multipliers are positive, so the
converted minimum remains the minimum. Reduce each result separately.

### Sums

A display projection MAY convert compatible terms to one unit and add them. The
stored sum and term order remain unchanged unless the caller requests a semantic
edit. A term without a unit cannot be combined with a physical term.

### Alternatives

Alternative quantities record equivalences asserted by the source. They are not
additive and do not assert mathematical equality. An option may be a simple
quantity or a sum of simple quantities. A renderer MAY choose an option suited
to the viewer and MAY project a selected sum for display, but a round trip MUST
preserve every option, its structure, and its order.

## Scaling

Scale each exact value and each range endpoint in ingredient quantities and step
ingredient-use quantities by the requested rational factor. Scale every term of
a sum and every simple quantity within each alternative option. For a sum
option, scale each of its simple terms. Preserve the `approximate` flag. Scale
each quantity independently; do not reconcile step uses with an ingredient's
declared total.

The following values MUST NOT be scaled:

- ingredient temperatures;
- step temperatures;
- timing assertions and step timing references;
- recipe preparation, cooking, additional, and total duration expressions; and
- package size.

Package size describes one selected item or container. Scaling `2 (400 g) cans`
by `3/2` produces three cans whose package size remains 400 g.

Opaque quantities cannot be scaled mechanically. An implementation MUST retain
the opaque text and report that it was not scaled. It MAY offer a person an
explicit editing workflow.

## Count and container units

Count and container values MAY be scaled arithmetically. They have no physical
conversion relationship. An implementation MUST NOT convert a clove, bunch,
pinch, can, tin, packet, or other nonphysical unit to mass or volume without a
separate, sourced knowledge model outside SREF.

`package_size` supplies the physical size of one counted item when the source
provides it. It does not establish a universal definition for that count or
container unit.

## Temperature

Ingredient and step temperatures may be numeric or opaque. Numeric temperatures
use the same amount representation as other physical quantities, MAY be exact or
ranges, and MAY be converted only between registered temperature units. Opaque
temperatures carry authored text and have no numeric conversion.

An optional structured purpose records what the authored temperature applies to.
Conversion changes only the amount and unit presentation; it MUST preserve the
purpose kind, label, note, and source text unchanged. Purpose is not a unit
dimension and does not affect affine conversion.

Temperature is an affine quantity, not a scalable recipe amount. Implementations
MUST apply offsets during conversion and MUST NOT multiply a temperature when
the recipe yield changes.

No conversion or normalization may infer a numeric amount, range, or unit from
an opaque temperature expression. Any application guidance based on a named heat
level is derived information and must not replace the authored SREF value.

## Formatting

Formatting is application policy, but it MUST preserve the distinction between
source truth and presentation. A formatter:

- SHOULD offer the authored representation when source text exists;
- MUST identify an approximate converted value as approximate;
- MUST avoid a precision display that implies more certainty than the source;
- MUST keep subjective modifiers such as `scant`, `heaping`, and `generous`; and
- MUST NOT write a rounded display value back as an exact normalized amount.

Kitchen-friendly rounding is allowed only in a display projection. The
implementation SHOULD retain enough information to explain the source unit,
target unit, conversion relationship, and rounding it applied.

## Density and ingredient equivalences

Mass-to-volume and volume-to-mass transformations depend on the ingredient,
preparation, packing, moisture, and data source. They are not unit conversions.

An application MAY provide an ingredient-equivalence feature outside SREF. It
MUST keep that feature separate from the unit registry, attach provenance to
each equivalence, and avoid changing the stored source quantity without an
explicit user action.
