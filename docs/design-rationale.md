# Design rationale

This page explains the main design decisions in SREF. The
[specification](../spec.md) defines the rules.

## Exchange format, not storage format

SREF describes recipe meaning and portable assets. It does not describe tables,
accounts, synchronization state, or interface preferences. Applications can
store recipes however they like; an export conforms when it reproduces the
complete portable recipe without depending on that storage.

## Source text and structured data side by side

Replacing an ingredient line with parsed values loses words such as `scant`,
`divided`, `for serving`, and `preferably`, even when the amount is parsed
correctly. SREF keeps the source text next to the structured values.
Normalization method and review state are separate fields, because a person can
confirm an inferred value without making it any less inferred.

## Variants are text, not instructions

A variant such as "For a richer version, add 100 ml cream with the stock" is
authored content, and keeping it as a generic note means an application cannot
show it as a variant. Representing variants as machine-applicable changes would
require a general change language: some variants insert an ingredient, others
remove and replace several, change yield and timing, or refer to other variants.

SREF therefore stores a variant as an optional title and authored text.
Preserving both is full conformance.

A variant describes a change to the current recipe. A source that presents a
separate, fully structured recipe is a separate recipe, even when it is similar.

## Optional ingredients

`1 tbsp chopped parsley, optional` means the recipe works without the parsley.
Left in prose, a shopping list, a scaled batch, or a printed card cannot tell it
from a required ingredient. The corpus finds optional ingredients in every
source family.

`optional` is a boolean because it answers one question: is the ingredient
needed to make the recipe as written? Other phrases answer different questions
and are not optionality: `salt to taste` is about quantity,
`lemon wedges, for serving` about purpose, and `preferably fresh parsley` about
preference.

The flag belongs to the ingredient occurrence, so parsley can be optional in a
garnish and required elsewhere in the method. An absent flag means `false`.
Keeping `(optional)` in `source_text` while dropping the flag is a lossy
conversion.

## Ambiguity is representable

An opaque quantity is the correct representation when a source says `a splash`,
names an unregistered vessel, or uses an unresolved regional measure. An
importer can then improve later by reparsing the source text, without undoing an
earlier guess.

## Equipment is a requirement, not inventory

A stand mixer or a particular pan can be necessary to make a recipe, whether or
not a given cook owns one. SREF keeps an ordered equipment list with a name, an
optional quantity, and a note. Ownership, availability, and purchasing are left
to applications. Equipment has no IDs, step references, or taxonomy, and its
quantities do not scale with yield.

## Temperature purpose

A temperature alone does not say whether it is an oven setting, a target inside
the food, or a frying medium. An optional `purpose` records this. The vocabulary
covers common cases, and a labeled `other` carries unusual wording. Purpose is
never inferred, does not imply equipment, and does not define when cooking is
done; the instruction text stays authoritative.

## Opaque temperatures

`moderate oven` states a temperature condition without a number. Assigning a
number would add knowledge the author did not give, so SREF stores the wording
as opaque temperature text, as it does for opaque quantities and durations.
There is no qualitative heat scale, and `cook over high heat` is not a
temperature unless the source makes it one.

## Authors and provenance

A displayed author name does not say whether the author is a person or an
organization, or whether two equal names are the same party. An author therefore
needs only a name; kind and URL are recorded only when the source supports them.
Authorship is separate from the source, the importing application, library
ownership, and asset credits.

Source provenance needs a name, URL, application or format identity, or
attribution; a retrieval time alone describes an event, not a source. A
`source_id` must name its `application`, because an identifier from an unnamed
system is ambiguous.

## Authored classifications versus library organization

A source's category, course, cuisine, or cooking-method label is recipe content.
A user's tag, favorites, or saved search is application state. SREF keeps the
source's classifications in separate ordered fields, with no fixed taxonomy and
no inference; an unlabeled source classification is kept as a category.
`published` and `modified` describe the source work, as a date or date-time at
the precision the source gave.

## Units are identities, not spellings

`cup`, `tbsp`, and `oz` mean different amounts in different regions. Registry
IDs fix the meaning; labels and aliases only affect display and parsing.
Converting a cup of flour to grams needs the ingredient's density, so the
registry converts only within a physical dimension.

An ID must not appear to settle a question the registry has not settled. UCUM
defines a metric cup as 240 mL, while ordinary culinary use means 250 mL, so the
bare ID `volume.cup.metric` is unassigned. The 250 mL cup is
`volume.cup.metric.culinary`. The 240 mL cup is `volume.cup.us.legal`, named for
the US nutrition-labeling definition; UCUM's `[cup_m]` is another name for it.
Likewise, UCUM's 5 mL `[tsp_m]` and 15 mL `[tbs_m]` are the US labeling teaspoon
and tablespoon. The ordinary 5 mL culinary teaspoon is
`volume.teaspoon.metric.culinary`.

Aliases follow the same rule. A bare `cup`, `tablespoon`, or `teaspoon` under
`en` selects no unit, because without regional evidence the answer is not known;
qualified forms such as `metric teaspoon` do select one.

No English word selects the 15 mL metric culinary tablespoon: Australian sources
use 20 mL, while Canadian and New Zealand sources use 15 mL, so the Australian
unit is explicit and the metric culinary one is reached by the qualified name
`metric tablespoon`, by another language's tablespoon word, or by a metric
convention decision. Units cooks actually write, such as both the imperial and
US pint, are registered rather than left for a parser to guess.

## Ingredient sections and instruction sections are separate

A pastry recipe may list dough, filling, and glaze while its method is organized
as prepare, chill, assemble, and bake. One shared hierarchy would force false
relationships, so the two structures are independent. Steps can reference
ingredients, but references are optional.

A step title is different from a section title. Turning each titled step into a
one-step section changes the source's structure, and dropping the title loses
it, so steps have an optional title. The step text remains required.

## Packages carry their assets

A recipe that points to remote images is not a complete export. A package holds
the declared assets with their digests and sizes, so a reader can check that it
is complete and unaltered. The manifest is not a signature and says nothing
about authorship.

Recipe-level `image_refs` record which images belong to the recipe and in what
order; step `image_refs` attach images to steps; `primary_image` picks the
preferred recipe image. One image can be used in several places without being
declared twice. Asset roles classify files and never place images, so placement
cannot contradict itself.

## Timings

The `times` summary fields (preparation, cooking, additional, total) cannot say
what a wait is for. An eight-hour dry-brine and a fifteen-minute rest added
together into `additional` cannot be told apart, so a reader cannot answer "do I
need to start this the day before?"

`times.assertions` records each timing once, with a recipe-local ID, a duration
(exact, approximate, ranged, or opaque), and optional kind and attention. Steps
refer to assertions by ID, so one step can refer to several timings and one
timing can span several steps without duplicate values.

SREF has no default for `attention`, and it does not decide which timings become
timers or how working time is calculated; those are choices for readers. The
summary fields remain valid on their own, and there is no rule that assertions
must add up to the summary, because authored totals can include overlap or
rounding.

## Translations are separate recipes

A translated recipe is its own document with its own language, not a set of
language maps on one document. Published translations differ in more than
wording: sources render quantities from different readings, split or merge
steps, and add notes the original lacks. Parallel fields would force those
renditions into one structure and would leave a partial translation with no
clear meaning.

`translations` records only the relationship. `original` and `translation` carry
a direction where the source states one; `alternate` covers publishers that list
language versions of a page without naming the original. A counterpart is
identified by title, bundle-local recipe ID, or URL, because a historical
translation cites a work by title while a publisher links pages by URL.

## Yields are independent assertions

A recipe often states what it makes in more than one way: `12 cookies`,
`about 600 g`, and `6 servings`. These are separate facts, not spellings of one
value, and the relationship between them is usually unknown. A single yield
forces a writer to choose one, and two writers choose differently. `yields` is
therefore an ordered array with no primary member. Which yield an application
shows first or scales by is its own state.

## Nutrition is authored, not calculated

`nutrition` preserves what a source states, with the basis the source
establishes. The basis matters most: per-serving values stay the same when a
batch is doubled, while whole-recipe values double. Schema.org's
`NutritionInformation` often omits the serving size, so a parsed panel does not
establish its own denominator; `unspecified` records that case without a guess.
Values reuse the amount forms of section 8, so `about 400` stays approximate and
`trace` stays text. A nutrition statement does not point at a yield, because the
relationship between a serving and a stated yield is often unknown.

## Claims keep their strength

`Contains peanuts`, `May contain peanuts`, and `Peanut-free` name the same
substance and say opposite things. A list of allergen names cannot hold that
difference, and neither can a tag. Dietary claims and allergen declarations are
separate collections of authored statements that keep their wording, their
presence or suitability, and any condition or variant scope. Because a claim can
be relied on for safety, SREF never lets a writer infer one, and a filter for an
explicit claim never matches on the absence of a contrary one.

## Asset provenance belongs to the asset

A recipe's author, its publisher, and the photographer of its image are often
three different parties. Asset provenance is kept on the asset, as a credit
line, a rights statement, a creator, a license, and a source URL. These overlap,
so SREF keeps each as the source wrote it rather than deriving one from another.
An absent license means unknown. SREF preserves the statements and does not
decide what they permit.

## Recipe references identify, they do not include

`1 batch pastry cream (see Pastry Cream)` is an ingredient made by another
recipe. The ingredient keeps its own name and quantity and adds a reference with
the same identity members as a translation: title, bundle-local recipe ID, or
URL. A reference does not copy the other recipe's content, and an unresolved
reference is valid. Expanding dependencies for cooking or shopping is
application behavior.
