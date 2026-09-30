# Culinary unit registry

[`units.json`](units.json) is the normative unit snapshot identified by SREF
recipe documents.

## Unit identity

Every `id` denotes one immutable semantic unit. A registry release MUST NOT
assign an existing ID a different physical definition, dimension, regional
meaning, or unit kind.

Once released, an ID is permanent. It MAY be deprecated and name a replacement,
but it MUST remain reserved and valid for reading older recipes. A corrected or
different meaning requires a new ID.

An ID whose unqualified form has more than one reasonable meaning is left
unassigned. `cup` is not an ID at all, and `volume.cup.metric` is permanently
unassigned because UCUM calls 240 mL a metric cup while ordinary culinary
practice calls 250 mL one.

An ID states what a unit is, not who published it. The 240 mL cup is
`volume.cup.us.legal`, because that is the quantity United States nutrition
labeling defines; UCUM encodes it as `[cup_m]` among US volumes. The 250 mL cup
is `volume.cup.metric.culinary`.

The same rule applies to UCUM's 5 mL `[tsp_m]` and 15 mL `[tbs_m]`, which are
also filed among US volumes and match the exact household measures defined for
United States nutrition labeling. They are `volume.teaspoon.us.legal` and
`volume.tablespoon.us.legal`. The bare IDs `volume.teaspoon.metric` and
`volume.tablespoon.metric` remain permanently unassigned, as the bare metric cup
ID does. The ordinary 5 mL culinary measure is instead
`volume.teaspoon.metric.culinary`. The 15 mL tablespoon of ordinary metric
culinary practice is `volume.tablespoon.metric.culinary`. Its only English
aliases are the qualified `metric tablespoon` and `metric tablespoons`, because
Australia uses a sourced 20 mL tablespoon, registered separately as
`volume.tablespoon.au`, and the bare English word does not settle which is
meant. The tablespoon words of languages whose kitchens use the 15 mL spoon
select it.

Units have one of three kinds:

- `physical` units define a mass, volume, temperature, or length relationship;
- `count` units scale but have no universal physical size; and
- `container` units count packages whose contents require a separate
  `package_size`.

Count and container units MUST NOT contain physical conversion definitions.

## Physical definitions

A physical unit uses one of these definitions:

- `base` establishes the registry base for a dimension;
- `linear` converts with `base = value × multiplier`; and
- `affine` converts with `base = value × multiplier + offset`.

Multipliers and offsets use canonical rational strings. A multiplier MUST be
positive. Affine definitions are limited to temperature units. The referenced
base unit MUST exist, MUST be physical, and MUST have the same dimension. Each
physical dimension MUST have exactly one base unit. Definition chains MUST
terminate at that base and MUST NOT contain cycles.

`exact: true` means the definition is exact under its cited standard.
`exact: false` marks a conventional or kitchen-friendly equivalence. It MUST
remain distinguishable from an exact unit during conversion and display.

The registry defines mass, volume, temperature, and length independently. Length
supports physical item sizes such as a piece of ginger or a tortilla diameter;
it does not turn two-dimensional pan measurements into one quantity.

## Labels and aliases

`labels` are localized display forms. `symbols` are display symbols; they are
not globally unique parser tokens.

`aliases` are parser candidates scoped by a BCP 47 language or locale tag. An
alias set declares whether matching is case-sensitive.

When a parser uses `source_locale` as evidence for a written alias, it MUST
apply the lookup procedure in
[Quantity and unit processing](../docs/quantity-and-units.md#alias-locale-lookup).
In summary, it tries the complete source tag first, then progressively truncates
it according to
[RFC 4647 lookup](https://www.rfc-editor.org/rfc/rfc4647.html#section-3.4). At
each level it considers only alias sets whose `language` tag equals that level
under ASCII case-insensitive comparison. The first level with any matching forms
supplies the complete candidate set, so a regional alias outranks a
less-specific language alias. Lookup ends at the primary language and MUST NOT
fall back to an unscoped alias set, a wildcard, or an unrelated locale.

Aliases MAY collide across units when their language or regional contexts
differ. A parser MUST resolve a collision using explicit source text and locale
evidence. It MUST leave the quantity opaque or unresolved when the evidence does
not select one semantic unit.

For `en-US`, the ordinary `cup`, `tbsp`, and `tsp` aliases belong to the exact
customary units. The approximate 240 mL, 15 mL, and 5 mL culinary units expose
only explicitly qualified aliases. A source equivalence or documented source
convention MAY still identify them directly; locale alone MUST NOT.

The exact US labeling spoon identities likewise expose only explicit `US legal`
or `legal` aliases. They MUST NOT claim generic-English `tablespoon`,
`teaspoon`, `tbsp`, or `tsp`. A documented nutrition-labeling convention MAY
identify them directly.

`fl oz`, `pint`, `quart`, and `gallon` name different physical quantities in the
United States and in the imperial system (an imperial pint is 568.26125 mL, a US
liquid pint 473.176473 mL). Each family exposes its plain aliases only under its
own locale, `en-US` or `en-GB`, alongside explicitly qualified forms such as
`US pint` and `imperial pint`. Text carrying neither an explicit qualifier nor a
locale that selects one family MUST stay opaque.

The 240 mL cup exposes no plain `cup` or `metric cup` alias. `metric cup`
belongs to the 250 mL culinary identity; a source that means the US labeling cup
MUST name it or state the volume.

## Aliases in other languages

Alias sets exist for these language tags besides English: `ar`, `cs`, `da`,
`de`, `el`, `es`, `fi`, `fr`, `he`, `hu`, `id`, `it`, `ja`, `ko`, `nb`, `nl`,
`pl`, `pt`, `ro`, `ru`, `sv`, `th`, `tr`, `uk`, `vi`, and `zh`. A set is scoped
to its primary language, so `pt` serves `pt-BR` and `pt-PT`, and `zh` serves
both Chinese scripts. Lookup never crosses languages: a German source does not
acquire an English alias, and an English source does not acquire a German one.

These sets name only the measures a language fixes:

- metric masses, volumes, and lengths, as words and symbols;
- the international symbols `oz` and `lb`, and the inch and ounce words that
  name only the international inch and the avoirdupois ounce;
- teaspoon and tablespoon words that name the spoon of that language's kitchens,
  which select the 5 mL `volume.teaspoon.metric.culinary` and the 15 mL
  `volume.tablespoon.metric.culinary`;
- the counts and containers the English sets name, where the word names that
  count or container and not something broader; and
- the national measuring cups `volume.cup.jp` and `volume.cup.kr`, each 200 mL,
  which the Japanese `カップ` and the Korean `컵` select.

A form that names different quantities in different countries has no alias, so a
quantity written with it stays opaque. That covers the cup and mug words of
every other language, the pound and ounce words that name a different mass in
another country (`Pfund`, `livre`, `libra`, the Dutch and Indonesian `ons`), and
dessert-spoon words. It also covers spoon words whose capacity differs between
publishers (Portuguese `cc`, Turkish `çay kaşığı` and `yemek kaşığı`), and a
bare word whose competing meanings remain plausible in a food context: French
`gousse`, Swedish `klyfta`, Italian `spicchio` and `scatola`, Korean `쪽`,
Chinese `瓣`, French `boîte`, and Finnish `mm`.

An alias identifies a word. It does not interpret a line. An importer may read
the whole line and select the sense the ingredient establishes: `gousse d'ail`
is a clove and `gousse de vanille` is not, `scatola di pomodori pelati` is a can
and `scatola di cioccolatini` is not. A bare token can be insufficient when its
complete phrase is clear.

An alias MUST NOT override an explicit regional qualifier. Changing a viewer's
display locale MUST NOT reinterpret the source unit.

Aliases MAY be added or deprecated, but a released alias MUST NOT be reassigned
to another unit under the same locale and matching conditions. If registry
growth introduces another valid candidate, parsers MUST report ambiguity rather
than silently changing the former result.

Forms are compared in NFC, and a set that is not case-sensitive compares under
Unicode case folding; see
[matching a written form](../docs/quantity-and-units.md#matching-a-written-form).

Case sensitivity belongs to an alias set, not an entire unit. A unit MAY define
case-insensitive word aliases and case-sensitive symbols in separate sets for
the same language. Parsers MUST apply the declared policy exactly; for example,
single-letter `T` and `t` aliases cannot be case-folded safely.

## Sources and alias policy

Every physical definition MUST cite at least one primary standards or official
guidance URL in `references`. A new or corrected definition requires source
review and a conformance fixture.

References establish particular claims: a physical definition, an attested word
form, or a documented culinary convention. An entry's references do not certify
every alias. Metric measuring spoons are distinct from ordinary household
utensils. Explicit source wording and documented conventions take precedence
over locale-derived candidates. An alias may identify a unit when the
measurement context selects that meaning; otherwise the original text and an
unresolved quantity are retained. Language forms are checked against a pinned
CLDR release and native-language sources where needed. Unrelated dictionary
senses alone do not forbid a valid contextual interpretation.

The registry bases (gram, millilitre, millimetre) are a design choice, not the
SI base units.
[BIPM's prefix table](https://www.bipm.org/en/measurement-units/si-prefixes)
supports the decimal relationships between them and their multiples.

The metric spoon references name the convention each source documents: German
(Dr. Oetker), Danish (Den Danske Ordbog), Norwegian (MatPrat), Swedish (Arla),
Finnish (Martat), Canadian French (Health Canada), Brazilian Portuguese
(Receitas Nestlé), Polish (Moje Wypieki, a blog's own stated convention),
Japanese (Osaka City), Korean (Rural Development Administration), and Hong Kong
Traditional Chinese (Department of Health). Each documents its own page or
language, and a publisher's other pages may use another convention.

These decisions are not obvious from the aliases, and each has a regression case
in the ingredient-line corpus:

| Form                                 | Decision                                                                                                                   | Source                                                                         | Cases                                                                                                                                                             |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Portuguese `cc`                      | No alias. One publisher's legend gives `Cc` as 5 mL and `cc` as 2.5 mL, and `cc` is also the cubic centimetre.             | Veganizadores recipe page, "Ingredients" and "Medidas"; Infopédia, C.C.        | `portuguese-cc-has-no-single-size`, `portuguese-cc-legend-case-is-kept`                                                                                           |
| Turkish `çay kaşığı`, `yemek kaşığı` | No alias. One page gives the tea spoon as 2.5 mL and the tablespoon as 10 mL in its legend and 15 mL in its section.       | Lezzet, Mutfak ölçüleri                                                        | `turkish-tea-spoon-has-no-single-size`, `turkish-tablespoon-has-no-single-size`                                                                                   |
| Dutch `theelepel`, `eetlepel`        | Kept as the measuring spoons. A household tableware table gives 2 mL and 12 mL, so a stated equivalent outranks the alias. | Voedingscentrum, cooking help                                                  | `dutch-stated-equivalent-outranks-the-spoon-word`                                                                                                                 |
| Italian and Hungarian tablespoon     | Kept. Two cookbooks state about 10 mL for their own text, so a stated equivalent outranks the alias.                       | Miele cookbooks, Italian p. 10 and Hungarian p. 15                             | `italian-stated-equivalent-outranks-the-spoon-word`, `hungarian-stated-equivalent-outranks-the-spoon-word`                                                        |
| Portuguese `colher de sopa`          | 15 mL culinary. Nutrition labeling specifies a 10 mL tablespoon and a 200 mL cup, which is a different convention.         | ANVISA IN 75/2020, Annex VII                                                   | `portuguese-culinary-tablespoon-is-not-the-label-measure`                                                                                                         |
| Finnish `mm`                         | No alias. It abbreviates `maustemitta`, a 1 mL spice measure. Length words and `cm` stay lengths.                          | Martat, Ruoka-aineiden mitat ja painot                                         | `finnish-mm-may-be-the-spice-measure`, `finnish-centimetre-stays-a-length`                                                                                        |
| French `gousse`                      | No alias. The ingredient selects the sense.                                                                                | Académie française, gousse and ail                                             | `french-garlic-clove-with-its-ingredient`, `french-vanilla-pod-is-not-a-clove`                                                                                    |
| Swedish `klyfta`                     | No alias. A wedge or a segment of fruit.                                                                                   | Svenska Akademiens ordböcker, klyfta                                           | `swedish-garlic-clove-with-its-ingredient`, `swedish-fruit-segment-is-not-a-clove`                                                                                |
| Italian `spicchio`, `scatola`        | No alias. A fruit wedge; a box of any material.                                                                            | Treccani, spicchio and scatola                                                 | `italian-garlic-clove-with-its-ingredient`, `italian-fruit-segment-is-not-a-clove`, `italian-canned-tomatoes-are-a-can`, `italian-box-of-chocolates-is-not-a-can` |
| Korean `쪽`, Chinese `瓣`            | No alias. A divided piece of any food; a garlic or fruit segment.                                                          | National Institute of Korean Language; Taiwan Ministry of Education dictionary | `korean-garlic-clove-with-its-ingredient`, `chinese-garlic-clove-with-its-ingredient`                                                                             |
| French `boîte`                       | Only `boîte de conserve` is an alias.                                                                                      | Larousse, boîte                                                                | `french-box-is-not-a-can`, `french-preserve-tin-is-a-can`                                                                                                         |

No source certifies every alias in every language. The Arabic, Czech, Hebrew,
Indonesian, Romanian, Russian, Thai, Ukrainian, and Vietnamese sets rest on the
CLDR release for physical units and on the English sets for counts and
containers.

## Registry validation

A registry implementation MUST enforce:

- unique unit IDs;
- canonical rational definitions;
- valid base-unit references and dimensions;
- acyclic conversion chains;
- valid replacement IDs for deprecated units;
- exactly one base unit per physical dimension;
- positive conversion multipliers and temperature-only affine definitions;
- unique aliases within each alias set; and
- immutable meaning across released snapshots.
