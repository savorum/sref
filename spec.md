# SREF specification

## 1. Conformance language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**,
and **MAY** describe conformance requirements. Their meanings are defined by
this document:

- **MUST**, **MUST NOT**, and **REQUIRED** are absolute requirements.
- **SHOULD** and **SHOULD NOT** are strong defaults. An implementation MAY
  depart from them only when it understands and documents the consequences.
- **MAY** describes optional behavior.

The JSON Schemas define structural requirements. This document defines both
structural and semantic requirements. When the schema cannot express a rule,
conforming implementations MUST enforce the prose rule.

## 2. Purpose

SREF, the Structured Recipe Exchange Format, exchanges recipes between
independent applications and preserves them outside the lifetime of any one
application.

SREF has two representations of one recipe model:

1. A standalone UTF-8 JSON document.
2. A self-contained ZIP package containing the JSON document and its assets.

It also defines one container for many recipes: a bundle, which is an ordered
ZIP archive of complete packages. A bundle adds no third recipe representation,
because every member of it is an ordinary package.

SREF is not:

- an application's database schema;
- a backup format for accounts, permissions, favorites, or private notes;
- an ingredient ontology;
- a nutrition or food-density database;
- a user-interface model;
- a general document-rendering format; or
- a claim that every part of an ingredient line can be normalized safely.

## 3. Design invariants

A conforming implementation MUST preserve these invariants:

1. **Original information survives normalization.** Imported source text is not
   discarded merely because structured fields were derived from it.
2. **Quantities are exact when declared exact.** Binary floating-point values
   are not used in the exchange representation.
3. **Unit identity is semantic.** A written label such as `cup` is not a unit
   identity without a defined culinary convention.
4. **Recipe content is separate from library state.** Personal ratings,
   favorites, permissions, and application audit data are not recipe fields.
5. **Ingredient and instruction structures are independent.** Their sections
   need not have matching names or shapes.
6. **References are optional but sound.** A recipe need not link steps to
   ingredients, but every reference it does contain MUST resolve.
7. **Required package assets are local.** A packaged recipe does not depend on a
   remote server to recover its declared assets.
8. **Unknown meaning is preserved as unknown.** A writer does not invent
   structured semantics to make a document look complete.

## 4. Character encoding and JSON rules

Recipe documents, manifests, and registries MUST be JSON encoded as UTF-8.

Writers MUST NOT emit:

- a byte-order mark;
- duplicate object member names;
- nonfinite numbers;
- comments; or
- trailing commas.

Readers MUST reject duplicate object member names. Silently accepting the last
duplicate changes identifiers, checksums, or quantities.

Property order has no semantic meaning. Array order is significant unless a
field explicitly says otherwise.

SREF does not define canonical JSON bytes. Two documents can be semantically
equivalent without being byte-identical.

The published schemas also set structural ceilings: maximum array and string
lengths for the members they define. The ceilings are part of the format
version. A document that exceeds one is invalid, and every conforming reader
applies the same ceilings. The schemas are the normative source for their
values.

Structural ceilings differ from the resource limits that sections 15 and 19
require of a reader. A resource limit is an implementation policy. It may be
configurable, and conforming readers may choose different limits.

## 5. Version identification

Every recipe document MUST contain:

```json
{
  "sref": {
    "version": "<format-version>",
    "unit_registry": "<registry-version>"
  }
}
```

The `version` member identifies the recipe specification. The `unit_registry`
member identifies the registry against which standard unit IDs are interpreted.

SREF versions use `MAJOR.MINOR.PATCH`. Versions with the same `MAJOR` component
belong to the same **compatibility line**, including before 1.0: `0.4.0` and
`0.5.0` are in the same compatibility line. Among syntactically valid versions,
"newer" means that the `(MAJOR, MINOR, PATCH)` tuple compares greater at the
first component where the versions differ.

A reader MUST check both versions before interpreting normalized data. A reader
that does not support either version MUST report the unsupported version and
MUST NOT silently reinterpret the document under another version.

A reader MUST open a newer version in the same compatibility line and interpret
the standardized subset it understands. It MUST preserve unknown standard
members and syntactically valid unknown registry IDs, MUST NOT guess their
semantics, and MUST disable operations that require unknown unit semantics. A
reader that cannot preserve unknown data safely MUST keep the document read-only
or require an explicitly lossy operation before rewriting it.

A different compatibility line is unsupported unless the reader implements it
explicitly. Accepting a compatible newer version does not constitute a claim of
full support for that version.

Expanded versioning and release requirements are specified in
[docs/versioning.md](docs/versioning.md).

## 6. Recipe document

A recipe document contains these required members:

- `sref`: specification and registry versions;
- `id`: a recipe-local identifier;
- `title`: the recipe title.

A recipe MUST contain at least one of `ingredient_sections` or
`instruction_sections`. These collections are independently optional; when
present, each MUST be nonempty and satisfy its existing section and member
requirements. A recipe containing neither collection is invalid, even if it
contains descriptive metadata or notes. Empty arrays are invalid placeholders.

Absence says only that this representation contains no such authored collection.
It does not assert source incompleteness or account for importer loss. SREF does
not define a partial, incomplete, draft, or completeness status. Importers MUST
NOT fabricate content to satisfy this minimum; loss of source content belongs in
import diagnostics, separately from legitimately absent source data.

It MAY also contain:

- `description`;
- `language`;
- `source_locale`;
- `authors`;
- `source`;
- `yields`;
- `nutrition`;
- `times`;
- `categories`;
- `courses`;
- `keywords`;
- `cuisines`;
- `cooking_methods`;
- `published`;
- `modified`;
- `notes`;
- `variants`;
- `equipment`;
- `dietary_claims`;
- `allergen_declarations`;
- `translations`;
- `assets`;
- `image_refs`;
- `primary_image`;
- `extensions`; and
- extension members beginning with `x-`.

### 6.1 Recipe ID

`id` identifies a recipe within a document or package. It is not a global ID,
proof of authorship, or revision identity.

It MUST match the schema's portable identifier syntax. A copied or independently
imported recipe MAY retain or replace the ID. Cross-library identity is outside
this specification.

A portable identifier contains 1–128 ASCII characters. Its first character MUST
be an ASCII letter or digit. Every subsequent character MUST be an ASCII letter,
digit, period, underscore, or hyphen. A leading digit is valid, so ordinary
UUIDs do not require rewriting. These constraints exclude path separators,
control characters, and `.` or `..` as complete identifiers.

### 6.2 Text

Human-readable strings MUST be valid Unicode and MUST NOT contain C0 control
characters other than horizontal tab, line feed, and carriage return where the
schema permits them.

Writers SHOULD use Unicode normalization form NFC. Readers MUST NOT change text
in a way that loses distinctions in the source.

Empty strings are invalid unless a field explicitly permits them.

### 6.3 Language and source locale

`language`, when present, identifies the primary language of the recipe.
`source_locale`, when present, records locale evidence relevant to the source.

Both values MUST be well-formed BCP 47 language tags. JSON Schema does not fully
validate BCP 47; semantic validators MUST do so.

Source locale is evidence, not permission to assign every ambiguous unit to a
regional convention. A reader MUST preserve an unresolved unit rather than make
an unsupported physical claim. Locale-scoped unit aliases MUST be matched by the
deterministic lookup procedure in
[Quantity and unit processing](docs/quantity-and-units.md#alias-locale-lookup).

### 6.4 Authors and source

`authors` is an ordered list of credited author objects. Every author object
MUST contain a nonempty `name`. It MAY also contain:

- `kind`: `person`, `organization`, or `other`;
- `kind_label`: the source's human-readable classification when `kind` is
  `other`; and
- `url`: an absolute, source-provided or otherwise authoritative URL for the
  credited author.

`kind_label` MUST NOT occur unless `kind` is `other`. `kind` MAY be omitted when
the source does not distinguish the author type. A writer MUST NOT infer a kind,
identity, or URL merely from the spelling of `name`, from an apparent match
between credited names, or from recipe source provenance. Author order MUST be
preserved because it records the source's credit order.

Recipe authorship is independent of library ownership, the application or
location from which the recipe was retrieved, and asset attribution. An author
MUST NOT identify a library owner unless that person is actually credited as a
recipe author. A recipe `source` or importing application MUST NOT become an
author merely because it supplied the recipe. Asset creator, credit, and
licensing metadata MUST NOT be represented as recipe authorship unless the same
party is also credited as a recipe author.

`source` MAY record these source-identity members:

- a human-readable source name;
- an absolute source URL;
- an application or format name;
- freeform attribution text.

It MAY additionally record an identifier in the source system and a retrieval
timestamp. These supplementary members do not identify a source by themselves.

When present, `source` MUST contain at least one standard source-identity
member: `name`, `url`, `application`, or meaningful `attribution`. An extension,
`source_id`, or `retrieved_at` alone does not assert a source. Attribution used
as the identity member MUST identify or credit the source rather than describe
only the act of retrieval.

`source_id` is meaningful only within an identifier namespace. `application`
names that namespace and therefore MUST accompany `source_id`. Writers MUST NOT
emit an application-local identifier without its application or format identity.

Retrieval timestamps MUST use an RFC 3339 date-time representation. A source URL
is provenance; it MUST NOT be the sole location of an asset required by a
package.

### 6.5 Yields

`yields` is an ordered, nonempty array of yield assertions. Each assertion is
one independent statement of what the recipe makes, such as `12 cookies`,
`about 600 g`, or `6 servings`. A recipe with one authored yield has a
one-element array.

A yield assertion MAY contain:

- `text`: the complete human-readable yield;
- `quantity`: a normalized quantity expression; and
- `label`: a human concept such as `servings`, `cookies`, or `loaf` when no
  registry unit is appropriate.

At least `text` or `quantity` is REQUIRED. A writer MUST preserve yield text
when normalization would discard useful meaning. An approximate or ranged yield
uses the amount forms of section 8, and a yield that cannot be normalized
without unsupported assumptions uses `text` alone or an opaque quantity.

Array order records the source's order and MUST be preserved. No assertion is
primary, and array position does not rank them. Assertions need not convert into
one another. A reader MUST NOT derive a relationship between assertions, such as
`2 cookies per serving` from `12 cookies` and `6 servings`, MUST NOT merge
assertions that appear equivalent, and MUST NOT discard an assertion because
another one seems to imply it. A writer MUST NOT add an assertion that the
source did not state, including a conversion of another assertion.

One authored phrase that states two quantities, such as
`Makes 12 cookies (6 servings)`, MAY be recorded as two assertions. A phrase
that describes one yield, such as `12 large cookies`, is one assertion. A
serving suggestion that is not a statement of what the recipe makes is not a
yield.

Scaling a recipe by a factor applies that factor to each assertion whose
quantity has a numeric amount and leaves opaque assertions unchanged.
Approximation and range form survive scaling. Which assertion an application
shows first or uses to choose a scaling factor is application state and MUST NOT
be written by reordering the array.

Yield normalization does not require a universal ontology for cookies, loaves,
pans, or batches.

### 6.6 Times

`times` MAY contain `prep`, `cook`, `additional`, and `total` summary duration
expressions. A duration expression has exactly one of these shapes:

```json
{ "value": "PT20M" }
{ "value": "PT30M", "approximate": true, "source_text": "about 30 minutes" }
{ "min": "PT1H", "max": "PT2H" }
{ "min": "PT1H", "max": "PT2H", "approximate": true,
  "source_text": "about 1–2 hours" }
{ "text": "overnight" }
```

`value`, `min`, and `max` MUST be ISO 8601 duration strings. `approximate` MAY
qualify an exact value or a range and defaults to `false` when omitted. An
opaque expression uses `text` and MUST NOT also carry numeric duration members
or `approximate`. `source_text` MAY retain the authored wording of a normalized
exact value or range.

When present, `times` MUST contain at least one summary duration expression or
one timing assertion. An extension alone does not assert a recipe clock.

SREF does not require `total` to equal the sum of other fields. Recipes often
contain overlapping or approximate time concepts. Writers MUST NOT invent
missing times. `additional` remains a single undifferentiated summary and MUST
NOT be relabeled as resting, marinating, or another specific kind without source
evidence.

`times.assertions` is an ordered array of canonical timing assertions. Each
assertion has a recipe-local `id` and one `duration` expression. It MAY have a
semantic `kind`, a `label`, an `attention` value, and a `note`.

```json
{
  "times": {
    "total": { "min": "PT9H", "max": "PT10H", "approximate": true },
    "assertions": [
      {
        "id": "prep",
        "kind": "prep",
        "duration": { "value": "PT20M" },
        "attention": "active"
      },
      {
        "id": "marinate",
        "kind": "marinate",
        "duration": {
          "min": "PT7H",
          "max": "PT9H",
          "approximate": true,
          "source_text": "about 7–9 hours"
        },
        "attention": "passive"
      },
      {
        "id": "finish",
        "kind": "other",
        "label": "Slice and dress",
        "duration": { "value": "PT10M" }
      }
    ]
  }
}
```

Timing assertion IDs MUST be unique within `times.assertions`. Array order is
authored workflow or presentation order and MUST be preserved. It does not
assert that assertions are consecutive, complete, or non-overlapping.

`kind`, when present, MUST be one of `prep`, `soak`, `brine`, `marinate`,
`cure`, `proof`, `ferment`, `chill`, `freeze`, `drain`, `cook`, `rest`, `cool`,
or `other`. A kind of `other` MUST carry a `label`, because "other" is not
useful presentation text. Any assertion MAY carry a label that preserves the
recipe's own wording. Kind and label are optional when the source supports a
duration but not a defensible semantic classification.

`attention`, when present, MUST be `active` or `passive`. It is authored
semantics, not a default or a derived timer policy. Absence means attention is
unstated. A structured duration does not assert that an application should offer
or start a timer.

Steps associate themselves with canonical timing assertions through
`timing_refs`, as specified in section 11. An assertion is stored exactly once
even when several steps refer to it or one step refers to several assertions.
Readers MUST NOT duplicate one timing fact merely because it participates in
both recipe chronology and instruction presentation.

Summary fields and timing assertions MAY coexist. They are independent authored
assertions and MUST be preserved independently. A reader MUST NOT infer a
summary by adding detailed assertions, require arithmetic agreement, or discard
one representation because it can calculate another projection. An
assertion-only clock does not claim a complete elapsed time.

A duration whose length is not fixed, such as one expressed in months, is
preserved but cannot be added into an exact total without an application policy
and reference date. Timing expressions and assertions MUST NOT change during
recipe quantity scaling.

### 6.6.1 Microwave cooking conditions

A timing assertion MAY contain `microwave` when its duration is an authored
microwave heating interval. The annotation describes the source conditions for
that one assertion. It MUST NOT be applied to a recipe summary, standing or
cooling time, a nonmicrowave stage, or another assertion merely because they
occur in the same recipe or step.

`microwave.source_text` retains the complete wording that establishes the
annotation and is REQUIRED. The annotation MAY contain:

- `rated_output_watts`, the appliance's stated maximum cooking output;
- `power`, the selected operating power;
- `mode_text`, authored mode wording whose machine meaning is not standardized;
- `restrictions`, ordered authored statements limiting use or substitution; and
- `choices`, an ordered authored power-and-time schedule for one heating event.

Watts are positive integers. They always mean microwave cooking output, never
electrical input or consumption. `rated_output_watts` and selected `power.watts`
are different facts and MUST NOT be substituted for one another. `power` has
exactly one of these forms:

```json
{ "watts": 600 }
{ "percent": "50" }
{ "text": "medium" }
```

`percent` is an exact canonical rational greater than zero and at most 100.
`text` preserves an authored level such as `medium`, `P6`, or `defrost` without
assigning it a percentage. Absence of `power` means the setting is unstated; it
does not mean high. A writer MAY record an explicit high setting as
`{"percent":"100"}` only when the source establishes that meaning.

Each item of `choices` contains its own `duration`, `source_text`, and at least
one of `rated_output_watts` or `power`. Choice conditions MUST be distinct. A
choice schedule MUST NOT also put a shared `rated_output_watts` or `power` on
the containing annotation. The timing assertion's required `duration` MUST be an
opaque expression containing the complete alternative wording:

```json
{
  "id": "heat",
  "kind": "cook",
  "duration": { "text": "800 W: 3 minutes; 1000 W: 2 minutes 30 seconds" },
  "microwave": {
    "source_text": "800 W: 3 minutes; 1000 W: 2 minutes 30 seconds",
    "choices": [
      {
        "power": { "watts": 800 },
        "duration": { "value": "PT3M", "source_text": "3 minutes" },
        "source_text": "800 W: 3 minutes"
      },
      {
        "power": { "watts": 1000 },
        "duration": {
          "value": "PT2M30S",
          "source_text": "2 minutes 30 seconds"
        },
        "source_text": "1000 W: 2 minutes 30 seconds"
      }
    ]
  }
}
```

The opaque containing duration lets a reader that understands the assertion but
not the newer annotation present the complete authored schedule without
mistaking alternatives for consecutive phases or a range. A conforming older
reader opening a newer compatible document ignores `microwave` when interpreting
the known assertion and preserves it at the same scope under section 13.

Microwave conditions do not assert that different appliances, settings, modes,
or times produce interchangeable outcomes. SREF defines no power conversion,
doneness calculation, appliance inventory, sensor emulation, combination-mode
calculation, or personal appliance setting. A consumer MAY offer a clearly
identified estimate, but it MUST preserve the authored duration and conditions
as the portable recipe facts.

### 6.7 Authored classifications, chronology, notes, and variants

`categories`, `courses`, `keywords`, `cuisines`, and `cooking_methods` are
ordered arrays of unique, nonempty strings. They carry labels stated by the
recipe or its source, not application collection membership or user-specific
state. Array order MUST be preserved. SREF does not define controlled
vocabularies for these fields.

`categories` carries broad source classifications such as `Cake` or `Soup`.
`courses` carries meal-role classifications such as `Dessert`, `Main course`, or
`Side dish`. A source that distinguishes those concepts SHOULD retain the
distinction. A source with one undifferentiated classification field SHOULD
preserve its values in `categories` and MUST NOT duplicate or guess course
values merely to populate both fields.

`cuisines` carries authored cultural or regional cuisine labels.
`cooking_methods` carries authored method labels such as `Baking` or
`Pressure cooking`; it does not replace instruction text or declare required
equipment. `keywords` carries other source-authored discovery terms. Readers and
importers MUST NOT derive any of these arrays from ingredients, instructions,
equipment, or application organization merely because a label seems plausible.

`published` and `modified`, when present, are strings formatted as either an RFC
3339 full date or RFC 3339 date-time. A date preserves date-only source
precision; a date-time preserves its explicit offset or UTC designator. A reader
MUST preserve that distinction and MUST NOT invent a time or timezone for a
date-only value.

These chronology fields describe the publication and modification of the
authored recipe or source work. `modified` MAY be omitted when the source does
not distinguish it. Neither field describes SREF serialization, package or
bundle generation, retrieval, library import, synchronization, or application
revision time. Readers MUST NOT rewrite them when editing, importing, or
exporting the recipe. SREF does not require chronological comparison between the
fields because their source precision and offsets may differ.

`notes` is an ordered array of nonempty authored recipe notes. Like the other
fields in this section, it remains recipe content rather than application state.

#### Variants

`variants` is an ordered array describing authored modifications of this recipe,
such as `For a richer version, add 100 ml cream with the stock.` Each variant
has nonempty authored `text`, an optional `title`, and an optional recipe-local
`id`. Variant IDs MUST be unique within `variants`. An `id` lets a dietary claim
or allergen declaration (section 6.11) state that it applies to that variant.
Array order MUST be preserved.

A variant is authored content that describes a coherent modification of the
recipe. It is not a machine-applicable recipe delta. SREF does not define an
override or patch language for ingredients, instructions, yield, timing,
equipment, or any other recipe field, and a consumer is not required to
interpret or apply a variant.

A consumer MUST be able to identify authored variants as variants, preserve
their order, titles, and text, and present them as variants rather than as
generic notes. Preserving a variant without interpreting it is fully conformant,
because its title and text are its complete content.

Variants do not nest or compose. A variant MUST NOT contain `variants`, and it
MUST NOT restructure the recipe through `ingredient_sections`,
`instruction_sections`, `yields`, `nutrition`, or `times`. A variant that a
source expresses by reference to another variant, such as
`follow the chocolate variation above but replace the vanilla with orange zest`,
is preserved as authored text; SREF does not resolve the reference.

A variant is not an embedded recipe. The distinction depends on how the source
presents the content:

- content the source presents as a modification of the current recipe is a
  variant, regardless of how many fields the modification affects; and
- content the source presents as a separate recipe, with its own structured
  ingredient list and instructions, is a separate recipe, regardless of what the
  source calls it.

Variants, optional ingredients, and alternative quantities are distinct and MUST
NOT be conflated:

- an optional ingredient states that the base recipe permits an omission;
- an alternative quantity states that one ingredient occurrence admits
  interchangeable choices; and
- a variant states that the author described an alternate realization of the
  recipe.

When a source presents
`For a dairy-free version, use olive oil instead of butter` as a named version,
it is a variant, even though the same change could be written as a local
substitution.

### 6.8 Required equipment

`equipment` is an ordered, nonempty array of equipment the recipe identifies as
required or expected for execution. Every entry contains a nonempty authored
`name` and MAY contain an ordinary SREF `quantity` and an authored `note`.
Writers and readers MUST preserve entry order, names, quantities, and notes.

The name describes the equipment as the recipe states it. SREF defines no
equipment registry and does not normalize dimensions, materials, attachments,
vessel types, or similar qualifications. Names such as `8-inch cake pan`,
`heavy-bottomed saucepan`, and `stand mixer with dough hook` are valid authored
equipment names. A qualification such as `clean, dry bowl` or `greased pan` MAY
remain in the name or note.

Equipment quantities describe what the recipe states, such as `2 baking sheets`;
they do not scale automatically with recipe yield. A writer MUST NOT infer that
a larger batch needs proportionally more equipment. Temperature units are
invalid in an equipment quantity because a temperature describes a condition,
not a count or measure of equipment.

Equipment describes recipe requirements, not the state of a person's kitchen.
Ownership, possession, availability, cleanliness, maintenance, procurement, and
appliance state MUST NOT be represented as equipment facts merely because they
are true for a user. Procedural commands such as greasing, cleaning, assembling,
or preheating remain instruction text when the source expresses them
procedurally.

SREF defines neither equipment IDs nor equipment-to-step references. It also
defines no separate equipment-preparation graph or executable prerequisite
model. Consumable supplies are not equipment; importers SHOULD preserve a
source's explicit distinction and MUST NOT reclassify an item merely to fill
this collection.

### 6.9 Translation relationships

A recipe document is one rendition of a recipe in one primary language. A
translated recipe is a separate recipe document with its own `id`, `language`,
and content. SREF does not carry several languages of one field in one document.

`translations` is an ordered, nonempty array of relationships the source or
author declares between this recipe and other renditions of it. Every entry
contains:

- `relation`: how the counterpart relates to this recipe;
- `language`: the counterpart's primary language, a BCP 47 language tag.

It also identifies the counterpart with the recipe identity members of section
6.12: at least one of `title`, `recipe_id`, and `url`.

`relation` is one of:

- `original`: this recipe was translated from the counterpart;
- `translation`: the counterpart was translated from this recipe;
- `alternate`: the source presents the counterpart as the same recipe in another
  language without saying which rendition is the original.

A recipe that contains `translations` MUST contain `language`. It MUST NOT
declare more than one `original`, and no entry's `recipe_id` may equal the
recipe's own `id`.

A counterpart is resolved, or left unresolved, as section 6.12 specifies.
Writers that place linked renditions in one bundle SHOULD give them distinct
recipe IDs.

A relationship does not make content shared. Renditions MAY differ in title,
structure, quantities, units, notes, and recipe-local IDs, and each is complete
on its own. Readers and writers MUST NOT copy, merge, or synchronize content
between renditions because of a relationship, and MUST NOT resolve a
recipe-local reference in one rendition against another.

A relationship MUST come from the source or from an author's explicit statement.
Writers MUST NOT infer one from similar titles, shared images, matching
structure, or a common source URL. A declaration on one rendition is sufficient;
the counterpart need not repeat it. When two renditions disagree, such as each
naming the other as its original, readers MUST preserve both declarations and
MUST NOT choose between them.

The relationship describes the documents, not a reader's presentation. Which
rendition an application opens for a person, and in what order it lists them,
are application decisions outside this specification.

### 6.10 Nutrition

`nutrition` is an ordered, nonempty array of nutrition statements the recipe or
its source makes. A statement records authored values as the source gave them.
SREF does not calculate nutrition. A value an application derives from
ingredients, a food database, or another statement is not recipe content and
MUST NOT be written as a nutrition statement.

Every statement contains a `basis` and a nonempty ordered `nutrients` array. It
MAY contain a `note` that preserves authored qualification of the whole
statement, such as `Values are estimates calculated by the publisher.`

`basis.kind` says what the values describe:

- `recipe`: the whole recipe as written;
- `serving`: one serving;
- `quantity`: a stated amount of the food, such as 100 g; and
- `unspecified`: the source does not establish what the values describe.

`basis.text` MAY preserve the authored basis wording, such as `1 slice` or
`per 100 g`. `basis.quantity` states a serving size or reference amount as a
quantity expression. A `quantity` basis MUST contain `basis.quantity`. An
`unspecified` basis MUST NOT contain `basis.quantity`, and its `text`, when
present, preserves wording that does not establish a denominator.

A writer MUST NOT choose a basis the source does not establish. In particular, a
nutrient list without a serving size or other basis statement is `unspecified`,
even when the recipe states a serving count.

Every nutrient entry contains `nutrient` and exactly one value form. `nutrient`
is one of `energy`, `fat`, `saturated_fat`, `trans_fat`, `unsaturated_fat`,
`cholesterol`, `carbohydrate`, `sugars`, `fiber`, `protein`, `sodium`, `salt`,
or `other`. A nutrient of `other` MUST carry a `label`, and any nutrient MAY
carry a `label` that preserves the source's own name for it. `sodium` and `salt`
are distinct nutrients and MUST NOT be converted into one another.

The value forms are:

```json
{ "nutrient": "energy", "amount": { "value": "420" }, "unit": "kcal" }
{ "nutrient": "fat", "amount": { "value": "12", "approximate": true },
  "unit": "g", "source_text": "about 12 g" }
{ "nutrient": "sugars", "amount": { "min": "8", "max": "10" }, "unit": "g" }
{ "nutrient": "fiber", "text": "trace" }
```

`amount` uses the amount forms of section 8. `unit`, when present, is one of
`kcal`, `kJ`, `g`, `mg`, or `mcg`; `kcal` and `kJ` are valid only for `energy`,
and the mass units are invalid for `energy`. A value without `unit` preserves a
number whose unit the source did not state. `source_text` MAY preserve the
authored wording of a normalized value. `text` preserves a value that cannot be
normalized without unsupported assumptions, such as `trace` or `less than 1 g`,
and MUST NOT be accompanied by `amount` or `unit`.

A zero amount is an authored zero. A nutrient the source does not mention is
absent from the statement, and absence MUST NOT be read or written as zero. A
statement MUST NOT list the same nutrient and label more than once.

A recipe MAY contain several statements, such as one per serving and one per 100
g. They are independent assertions; a reader MUST NOT require them to agree or
derive one from another.

Nutrition values describe the recipe as written. When a consumer scales a
recipe, the authored statements remain unchanged. A consumer MAY present a
derived value only when the relationship is explicit:

- a `recipe` statement MAY be multiplied by the batch factor;
- a `serving` statement is unchanged when the recipe makes more or fewer
  servings of the same size, and it MUST NOT be multiplied by the batch factor;
- a `quantity` statement is unchanged by scaling; and
- an `unspecified` statement MUST NOT be scaled.

A derived value MUST be distinguishable from the authored statement, and the
authored statement MUST remain recoverable. Changing the size of a serving is
not recipe scaling, and SREF defines no conversion for it.

A nutrition statement does not reference a yield assertion. Its basis is
complete on its own, even when its relationship to a stated yield is unknown.
Nutrition, dietary claims, and allergen declarations are independent. None of
them MAY be inferred from another or from ingredients.

### 6.11 Dietary claims and allergen declarations

`dietary_claims` and `allergen_declarations` preserve statements the recipe or
its source makes about dietary suitability and about allergens. They are
separate collections with separate meaning. A dietary claim says whether the
recipe suits a diet. An allergen declaration says whether a substance is
present, may be present, or is absent.

These are authored claims, not facts SREF establishes. A writer MUST NOT create
a claim or declaration from parsed ingredients, instructions, nutrition, tags,
or any other inference. The absence of an ingredient does not establish that a
recipe is free from it, and the absence of a declaration does not establish
absence, suitability, or unsuitability. Unknown remains unknown.

Every dietary claim contains:

- `text`: the complete authored statement, such as `Vegan` or
  `Gluten-free when made with gluten-free oats`; and
- `suitability`: `suitable` or `unsuitable`.

It MAY contain `diet`, a normalized subject: `diabetic`, `gluten_free`, `halal`,
`hindu`, `kosher`, `low_calorie`, `low_fat`, `low_lactose`, `low_salt`, `vegan`,
or `vegetarian`. A claim whose subject has no normalized value omits `diet` and
keeps its subject in `text`.

Every allergen declaration contains:

- `text`: the complete authored statement, such as `Contains peanuts` or
  `Made in a kitchen that also handles tree nuts`;
- `substance`: the substance as the source names it, such as `peanuts`; and
- `presence`: `contains`, `may_contain`, or `free_from`.

`contains` states that the substance is present. `may_contain` states a
precautionary or cross-contact warning, including shared-facility and
shared-equipment statements. `free_from` states an explicit absence claim. A
reader MUST keep the three distinct and MUST NOT present `may_contain` as
`contains` or `free_from`, or a single list of substances as any one of them.
One authored statement that names several substances MAY be recorded as one
declaration per substance, each keeping the complete `text`.

Either kind of entry MAY contain:

- `condition`: authored wording that limits the claim, such as
  `when made with plant-based milk`; and
- `variant_ref`: the `id` of the variant (section 6.7) the claim describes.

A claim with `condition` is conditional. A reader MUST NOT present it, filter on
it, or export it as unconditional. A claim with `variant_ref` describes that
variant only and MUST NOT be applied to the recipe as written. A `variant_ref`
MUST resolve to a variant `id`.

Array order records the source's order and MUST be preserved. A reader MAY
filter on claims, but a filter for an explicit claim, such as
`explicitly marked peanut-free`, MUST NOT match a recipe merely because no
contrary declaration exists.

A claim describes the recipe as its source stated it. It is not a certification
by the writer, reader, or any application. Editing a recipe does not validate,
revise, or remove its claims, and a reader MUST NOT present an unchanged claim
as confirmed by the edit.

### 6.12 Recipe references

A recipe reference identifies another recipe. It is used by translation
relationships (section 6.9) and by ingredient dependencies (section 10.3). A
reference contains at least one of these identity members:

- `title`: the other recipe's title as authored;
- `recipe_id`: the other recipe's `id`; and
- `url`: an absolute URL where the other recipe is published.

A reference identifies what the source supplied and nothing more. A `url`
identifies a published resource that may change, not fixed recipe content. A
`title` alone is an authored name that a reader MAY present but MUST NOT treat
as a match for a recipe that happens to share it.

A `recipe_id` identifies a recipe only among the members of the same bundle, and
only when exactly one other member carries that `id`. Otherwise the reference is
unresolved. A reference MUST NOT carry the containing recipe's own `id` as its
`recipe_id`.

An unresolved reference is valid, and readers MUST preserve it. Resolving a
reference is optional. A reader that resolves one MUST NOT copy, merge, or
synchronize content between the recipes, and MUST NOT resolve a recipe-local
reference in one recipe against another.

## 7. Exact amounts

SREF serializes normalized numbers as canonical nonnegative rational strings.
Temperature amounts use the same canonical form with an optional leading minus
sign. Negative zero is never canonical.

The permitted forms are:

```text
0
positive-integer
positive-numerator/positive-denominator
```

Examples:

```text
0
2
1/3
9/4
```

The following are not canonical:

```text
00
+1
1.5
2/4
0/7
3/1
1/-2
```

For a fraction:

- numerator and denominator MUST be base-10 integers without leading zeros;
- numerator and denominator MUST be positive;
- denominator MUST be greater than one;
- numerator and denominator MUST be coprime; and
- the fraction MAY be improper.

JSON Schema enforces only part of canonicalization. Semantic validators MUST
enforce denominator, reduction, and size rules.

Implementations MUST support values whose numerator and denominator each fit in
an unsigned 64-bit integer. They MAY support larger values. They MUST impose
resource limits before allocating arbitrary-precision integers from untrusted
input.

The original spelling, such as `1.5` or `2¼`, belongs in `source_text` or an
appropriate human-readable field. The normalized rational does not replace it.

## 8. Amounts and quantity expressions

An `amount` is either an exact value or a range.

### 8.1 Exact amount

```json
{
  "value": "3/2",
  "approximate": false
}
```

`approximate` defaults to `false` when omitted.

### 8.2 Range amount

```json
{
  "min": "2",
  "max": "3",
  "approximate": true
}
```

`min` MUST be less than or equal to `max`. JSON Schema cannot enforce this
ordering; semantic validators MUST.

### 8.3 Simple quantity

A simple quantity contains an amount and MAY contain a semantic unit:

```json
{
  "kind": "simple",
  "amount": { "value": "2" },
  "unit": "volume.tablespoon.au"
}
```

Omitting `unit` is valid for a unitless amount.

Temperature units MUST NOT appear in an ordinary recipe, yield, nutrition basis,
or package-size quantity. Use the dedicated ingredient and step temperature
fields.

### 8.4 Sum quantity

A sum preserves additive expressions whose terms use different units:

```json
{
  "kind": "sum",
  "terms": [
    {
      "kind": "simple",
      "amount": { "value": "1/2" },
      "unit": "volume.cup.us.customary"
    },
    {
      "kind": "simple",
      "amount": { "value": "2" },
      "unit": "volume.tablespoon.us.customary"
    }
  ]
}
```

Writers MUST NOT collapse terms through a kitchen-friendly or density-based
conversion merely to avoid this structure.

### 8.5 Alternative quantity

Alternatives preserve authored equivalent presentations:

```json
{
  "kind": "alternatives",
  "options": [
    {
      "kind": "simple",
      "amount": { "value": "225" },
      "unit": "mass.gram"
    },
    {
      "kind": "simple",
      "amount": { "value": "8" },
      "unit": "mass.ounce.avoirdupois"
    }
  ]
}
```

Each option MUST be either a simple quantity or a sum quantity. A sum option's
terms remain simple quantities. An option MUST NOT be an alternative quantity or
an opaque quantity, so the quantity grammar remains shallow and cannot form
recursive alternative trees.

For example, this preserves two authored presentations of the same amount
without flattening the first presentation:

```json
{
  "kind": "alternatives",
  "options": [
    {
      "kind": "sum",
      "terms": [
        {
          "kind": "simple",
          "amount": { "value": "2" },
          "unit": "volume.tablespoon.us.customary"
        },
        {
          "kind": "simple",
          "amount": { "value": "2" },
          "unit": "volume.teaspoon.us.customary"
        }
      ]
    },
    {
      "kind": "simple",
      "amount": { "value": "40" },
      "unit": "volume.milliliter"
    }
  ]
}
```

The presence of alternatives records the source's assertion. It does not claim
that the options are mathematically exact equivalents.

### 8.6 Opaque quantity

When quantity text cannot be normalized without unsupported assumptions, use:

```json
{
  "kind": "opaque",
  "text": "a generous pinch"
}
```

Opaque is valid data. Readers MUST preserve it. Writers MUST prefer an opaque
quantity over fabricated numbers or units.

### 8.7 No amount

An ingredient such as `salt, to taste` MAY omit `quantity` entirely. It MUST NOT
use a zero amount to mean absent.

## 9. Units

The `unit` member contains a stable unit ID from the registry version named by
the document.

Examples include:

```text
mass.gram
mass.ounce.avoirdupois
volume.cup.us.customary
volume.cup.us.culinary
volume.tablespoon.us.legal
volume.teaspoon.us.legal
volume.teaspoon.metric.culinary
volume.cup.au
volume.tablespoon.au
volume.pint.us.liquid
volume.pint.imperial
volume.deciliter
count.clove
container.can
```

Written forms such as `cup`, `c.`, `tbsp`, `T`, or `cucharada` are aliases, not
unit identities.

### 9.1 Physical, count, and container units

Registry units have one of these kinds:

- `physical`: a unit with a defined physical dimension and conversion;
- `count`: a scalable culinary count without a universal physical size; or
- `container`: a package count whose physical contents require a separate
  package size.

Readers MUST NOT invent physical conversions for count or container units.

### 9.2 Regional ambiguity

A generic label does not select a regional unit. For example, Australian and
United States tablespoons differ. A parser MAY use explicit source evidence, but
it MUST preserve ambiguity when evidence is insufficient.

When `source_locale` supplies that evidence, parsers MUST try exact and
progressively less-specific alias locales in the order defined by
[alias locale lookup](docs/quantity-and-units.md#alias-locale-lookup). A match
at a more-specific level prevents less-specific alias sets from adding or
replacing candidates. Parsers MUST NOT search unrelated regional alias sets as a
default.

The registry distinguishes exact customary units from rounded culinary
equivalents where both are in use. In ordinary `en-US` recipe text, unqualified
cup and spoon aliases identify the customary units. Rounded 240 mL, 15 mL, and 5
mL culinary identities require explicit source evidence that defines that
convention. Display rounding is not a change to the stored semantic unit.

The cup, tablespoon, and teaspoon are region-bound: the same word names 236.6
mL, 14.8 mL, and 4.9 mL in the United States and 250 mL, 20 mL, and 5 mL in
Australia. Their bare, unqualified forms have no language-level aliases, so a
source written in English does not select a measuring convention for them.
Qualified forms such as `metric teaspoon`, `metric tablespoon`, `metric cup`,
and `Australian cup` have `en` alias sets, because the qualifier identifies the
measure. A parser resolves an unqualified spoon or cup from a regional alias
set, from stronger source evidence, or from a resolution decision under section
9.5. Without any of these, it MUST preserve the ambiguity.

Fluid ounces, pints, quarts, and gallons are registered separately for the
United States and for the imperial system, because the same written word names
quantities that differ by roughly twenty percent. A cup is registered separately
for the exact US customary volume, the rounded US culinary volume, the 240 mL
volume US nutrition labeling defines, the 250 mL volume of ordinary metric
culinary practice, and the Australian 250 mL cup. No unqualified identity is
registered for any of these words, so a parser with neither an explicit
qualifier nor a locale that selects one family MUST preserve the quantity as
opaque.

### 9.3 Cross-dimension conversion

Mass-to-volume and volume-to-mass transformations are not unit conversions. They
require ingredient-specific density knowledge and are outside SREF.

A conforming unit implementation MUST reject an ordinary conversion between
incompatible dimensions.

### 9.4 Conversion and display

Conversion determines the physical quantity represented by a semantic unit.
Formatting determines how an application presents that quantity. They are
separate operations.

A conversion MUST NOT alter the stored quantity, unit ID, source text, or
normalization metadata unless the caller explicitly requests a semantic edit.
Changing a display locale is never such a request.

For compatible physical units, implementations MUST apply the registry's linear
or affine definitions using exact rational arithmetic. If any traversed
definition has `exact: false`, the converted result MUST be identified as
approximate. Rounding for display MUST occur only after conversion and MUST NOT
be written back as an exact source quantity.

Ranges are converted endpoint by endpoint. Registry multipliers are positive, so
conversion MUST preserve endpoint order. Recipe scaling MUST NOT scale
temperatures.

The complete conversion procedure and display requirements are defined in
[docs/quantity-and-units.md](docs/quantity-and-units.md).

### 9.5 Resolution decisions

Section 9.2 specifies how a parser narrows an alias using evidence in the
document. This section specifies how a person's answer about a measure, such as
which cup a recipe means, affects normalization. Most application exports state
no locale, so these answers are common, and their effect is visible in the
stored document.

A **resolution decision** is an input to normalization. It is not a member of a
recipe document, and no member of this version records one. Two kinds are
defined:

- an **occurrence interpretation** selects one permitted canonical
  interpretation for one identified unit occurrence; and
- an **ingredient convention** supplies the measuring convention for the
  unqualified, convention-dependent measures of one identified authored
  ingredient statement.

An implementation that accepts resolution decisions MUST implement both kinds
and MUST keep them distinct. It MUST NOT infer the scope of an answer from the
unit identity that answer happened to produce.

#### Scope

An occurrence interpretation affects only the occurrence it addresses. Selecting
a US customary cup for one occurrence does not by itself assert that any other
measure in the ingredient is US customary.

An ingredient convention affects every applicable measure in that ingredient's
quantity expression: every term of a sum, every option of an alternative, every
applicable nested quantity component, and a package size the ingredient carries.
Here **ingredient** means the identified authored ingredient statement, not a
visual line produced by wrapping text. The decision MUST NOT reach other
ingredient statements, instruction text, the remainder of the recipe, or a later
import.

An occurrence MUST be addressed by an identity that distinguishes repeated
occurrences of one alias within a single ingredient. An alias string alone is
not an occurrence identity.

An implementation MAY offer a single action covering several ingredients or a
whole import. That action MUST expand to explicitly selected ingredient scopes;
it MUST NOT become an implicit recipe-level or library-level default. An
interaction MUST communicate the scope it submits, and an answer to a
per-occurrence question MUST NOT silently become an ingredient-wide convention.

#### What a convention means

A convention MUST be defined as a mapping, versioned by the registry it names,
from unit families to exact canonical unit identities. A display label such as
`United States` or `Metric` is not that definition.

A US customary cup, tablespoon, and spoon profile against registry 0.2.0
selects:

```text
volume.cup.us.customary
volume.tablespoon.us.customary
volume.teaspoon.us.customary
```

An implementation MUST NOT derive a convention from an already selected unit ID,
nor from unit definitions whose conversion factors happen to agree. One identity
is not sufficient evidence of the broader convention a person intended.

A convention answers for the **unit family** a measure belongs to, and the
identity it selects need not be one the registry associates with the authored
word. An occurrence interpretation selects among the meanings the registry
already gives the word. A convention names a measuring system, and the system
defines the unit. For example, a bare `cup` has no alias for the 250 mL
`volume.cup.metric.culinary`, but a metric convention selects it. An
implementation MUST NOT restrict a convention to the authored word's alias
candidates.

The family is the measure a unit is one interpretation of, not the identity:
`volume.cup.us.customary`, `volume.cup.au`, and `volume.cup.metric.culinary` are
three answers to one question. A convention MUST apply only to families its
mapping covers, and MUST NOT be applied to a measure of another family merely
because both are volumes.

A profile does not authorize inventing units or guessing an absent mapping. A
convention-dependent measure whose unit family the profile does not cover
remains unresolved unless the source gives it explicit meaning or an occurrence
interpretation addresses it. An implementation MUST NOT borrow a different
convention to complete the ingredient, and MUST NOT fall back to the
source-locale lookup of section 9.2 for it. Otherwise a metric decision on
`1 tablespoon plus 2 teaspoons` in an `en-US` source would yield a US customary
tablespoon beside a metric teaspoon.

This restriction applies to a contested family (one for which the registry holds
more than one identity) inside an explicit convention scope. A measure whose
word admits only one reading, such as a gram or a millilitre, resolves from its
own evidence whether or not the profile mentions it.

#### Precedence

For an unqualified measure undergoing normalization, an implementation MUST
apply, in this order:

1. an occurrence interpretation addressing that occurrence;
2. an ingredient convention covering that measure's unit family; then
3. the source-locale alias lookup of section 9.2.

An ingredient convention outranks locale-derived interpretation, including both
an exact-region match and a language-level match. A source locale is evidence
about the document; it is not an explicit definition of every unqualified
measuring unit in it.

A resolution decision MUST NOT override explicit source-defined unit meaning.
Recognized qualifiers such as `imperial pint` or `metric teaspoon`,
measuring-unit definitions the source states, and canonical unit IDs the source
supplies retain their meaning. Changing an explicit source meaning is an
intentional editing operation, never a side effect of answering an ambiguity
question.

Where a decision selects an interpretation other than the one a stated regional
locale suggests, an implementation MUST expose that difference in review rather
than presenting it as agreement with the source. `source_locale` MUST NOT be
changed to record a decision, and display preferences MUST NOT participate in
this procedure.

These rules apply only within the submitted scope. They do not authorize
reparsing stored normalized quantities during an ordinary read, export, display
change, or registry upgrade.

The authored amount structure and text are preserved throughout. A compound
amount MUST NOT be flattened into an approximate single value to avoid resolving
its terms.

Examples (informative):

- `¼ cup plus 1 tablespoon olive oil` with an ingredient-level US customary
  decision resolves both terms as US customary.
- `1 tablespoon plus 2 teaspoons neutral oil` with that same decision resolves
  both terms as US customary. A lower-priority language-level match must not
  determine the teaspoons.
- `1 tablespoon plus 2 metric teaspoons neutral oil` keeps the explicitly metric
  teaspoons, while the unqualified tablespoon follows the decision.
- `1.5 cups/187 grams all-purpose flour` with that decision resolves the cup and
  leaves the separately authored 187-gram alternative unchanged. Resolving a
  unit identity does not assert that authored alternatives are equal, and MUST
  NOT change their amounts, infer a density, or treat a material disagreement as
  corrected.
- An occurrence interpretation given for the cup does not resolve an otherwise
  ambiguous tablespoon elsewhere in the same expression.

#### Disagreement and conflict

An implementation MUST NOT infer an ingredient convention by collecting
occurrence interpretations and observing that their selected identities belong
to one region. Differing occurrence interpretations within one ingredient may be
deliberate; they remain local to their occurrences and neither establish nor
cancel an ingredient convention.

An occurrence interpretation takes precedence over an ingredient convention for
the occurrence it addresses, which is how a reviewed exception is expressed.

Two incompatible interpretations for the same occurrence, or two incompatible
ingredient conventions for the same scope, are a **conflicting resolution
context**. An implementation MUST report the conflict and require it to be
settled. It MUST NOT resolve a conflict by answer order, by first or last match,
or by discarding the supplied context and falling back to locale lookup.

#### What the result records

A measure resolved from a resolution decision is stored as its canonical unit
identity. The ingredient's `normalization.method` is `inferred` and its
`normalization.review` is `corrected`, with the authored text and the warnings
section 10 already requires preserved unchanged.

That explanation MUST describe the selected interpretation and its scope
accurately. It MUST NOT state that the source declared the convention, and it
MUST NOT state that the source supplied no regional evidence when the source
stated a locale.

This metadata distinguishes a reviewed inference from an authored assertion. It
is not an instruction to a subsequent reader to run normalization again.

Machine-readable decision detail (the decision kind, its scope, the selected
interpretation or profile mapping, the source identity or fingerprint it was
made against, and the parser and registry versions in use) belongs to an
application's import history rather than to the recipe. A reader MUST NOT
require that history in order to interpret exported quantities: it uses the
stored canonical identities, and MUST NOT reconstruct a replay policy from unit
IDs, warning prose, or `review = corrected`.

A refreshed import from the same foreign source is a new normalization
operation. Reusing earlier decisions requires an explicitly scoped application
policy and is not implied by reading the resulting SREF document.

#### Conformance boundary

The **unit resolution** capability of section 22 is claimed by an implementation
that accepts a resolution context and applies this section. Its conformance
vectors supply identified unit occurrences, source evidence, and explicit
decisions, and require the specified identity, an unresolved outcome, or a
reported conflict. Reading a document that already contains the expected
identities does not exercise this capability.

This capability does not make interactive review or natural-language ingredient
parsing mandatory for a SREF reader or writer. An implementation that does not
claim it is unaffected by this section, except that it MUST NOT introduce a
resolution behaviour this section forbids.

## 10. Ingredient sections and ingredients

`ingredient_sections` is an ordered, nonempty array. Every section has:

- a recipe-local `id`; and
- a nonempty ordered `ingredients` array.

A section MAY have a `title`. A section without one is untitled; readers SHOULD
NOT display an invented heading.

An ingredient entry is either an ordinary ingredient or a shallow authored
choice as defined below. Every ordinary ingredient has:

- a recipe-local `id` unique across all ingredient sections;
- a nonempty `name`; and
- optional normalized and original information.

An ingredient MAY contain:

- `quantity`;
- `optional`;
- `note`;
- `source_text`;
- `normalization`;
- `package_size`;
- `temperature`; and
- `recipe`.

`optional` indicates that the ingredient occurrence MAY be omitted while
remaining within the recipe as authored. It does not indicate an alternative
ingredient, a serving purpose, quantity flexibility, or a conditional
instruction. It defaults to `false` when omitted.

`optional` marks only an omission the author permits. A cook's own decision to
leave something out is not optionality.

Optionality belongs to the ingredient occurrence, not to an ingredient identity.
The same ingredient MAY be optional in one section and required in another, as
parsley often is when a garnish section repeats an ingredient the method already
requires. A reader MUST NOT propagate optionality from one occurrence to another
that names the same ingredient.

`optional` does not attach to a step's `ingredient_uses`, and SREF does not
model step-level optionality. A consumer MAY infer that a step's use of an
optional ingredient is contingent on that ingredient being included. SREF does
not define conditional steps or procedural logic. Instruction text remains
authoritative.

Optionality has no effect on yield or scaling. An included optional ingredient
scales exactly as any other quantified ingredient does, an omitted one
contributes nothing, and a recipe's declared yield does not change merely
because an optional ingredient is absent.

These are not optionality:

- quantity flexibility. `Salt to taste` may be entirely required by the author's
  intent despite carrying no exact amount. Omit `quantity` and retain the
  authored wording in `source_text`.
- purpose. `Lemon wedges, for serving` describes what the ingredient is for, not
  whether it may be left out. Use `note`.
- preference. `Preferably fresh parsley` ranks two acceptable forms of one
  ingredient. Use `note`.

An importer MUST NOT set `optional` from those phrasings alone. SREF does not
define an ingredient-role, preference, or recommendation vocabulary.

`optional` records what the source said. An importer that derived it from
ingredient prose rather than from a dedicated source field MUST record
`normalization` with method `extracted` or `inferred`, which in turn requires
`source_text`.

A writer MUST preserve an authored `optional` value. A writer whose model cannot
express optionality SHOULD retain the authored qualification in `source_text` or
`note`. A conversion that drops `optional: true` and keeps only the prose is
lossy and MUST NOT be reported as lossless.

`note` is general-purpose. It MAY contain preparation, division, brand
preference, serving guidance, or other human-authored information. Optionality
that the source stated belongs in `optional`; `note` MAY additionally carry the
authored wording. SREF does not define a `preparation` taxonomy.

`source_text`, when present, is the original or source-facing ingredient line. A
writer MUST NOT label generated text as original source text.

`normalization`, when present, records how structured ingredient semantics were
obtained. Its required `method` has one of these values:

- `authored`: a person authored the structured values directly;
- `extracted`: the values were normalized deterministically from explicit source
  text;
- `inferred`: at least one value depends on contextual inference;
- `unresolved`: ambiguity remains and the source representation is
  authoritative.

`review`, when present, is orthogonal to `method`:

- `confirmed`: a person reviewed and accepted the structured values; or
- `corrected`: a person reviewed and changed the structured values.

Omitting `review` means no affirmative review state is asserted. An `inferred`
or `unresolved` normalization MUST include one or more human-readable warnings.
The methods `extracted`, `inferred`, and `unresolved` require `source_text`.

Normalization applies to the ingredient as a whole; it does not assign a numeric
confidence score. Applications MAY retain more granular field provenance through
extensions.

A writer MUST NOT add or change `review` without an affirmative human review
action. A reader MUST preserve normalization method, review, and warnings during
a round trip.

### 10.1. Authored ingredient choices

An ingredient list entry MAY instead be a choice with `id`, `alternatives`, and
`relation`. `alternatives` MUST contain 2–100 ordered complete ordinary
ingredients. Each branch MUST have its own `id` and `name` and MAY carry any
ordinary ingredient member, including quantity alternatives, package size,
temperature, note, optionality, and normalization. A branch MUST NOT contain
`alternatives` or `relation`: choices are shallow, never recursive. Choice and
branch IDs share the recipe-wide ingredient ID namespace.

The choice MAY carry `optional`, `note`, `source_text`, and `normalization` with
their existing types and provenance requirements. It MUST NOT carry `name`,
`quantity`, `package_size`, or `temperature`. There is no inheritance: when an
authored quantity applies to either branch, writers MUST repeat it on both
branches. Branch quantities MAY differ.

`relation` MUST be one of:

- `or`: the author presents alternatives at this ingredient position. This
  records an authored choice, not formal exclusive Boolean logic.
- `and_or`: the author permits alternatives to be included together.
- `preferred`: the first branch is preferred; subsequent branches are
  source-authored substitutes. Their order alone asserts no further ranking.

Readers MUST distinguish these relationships. Substitution conditions and exact
connectors remain in `note` or `source_text` and remain authoritative;
`preferred` is not an executable fallback rule. Consumers MUST NOT infer
substitutability, general equivalence, or an ingredient ontology from a choice.
A writer MUST NOT turn quantity alternatives for one identity into branches.

A choice note applies to the whole requirement; branch notes apply only to that
branch. A shared preparation may be stated in the choice note or repeated
explicitly on each affected branch. Writers MUST NOT assign ambiguous modifier
scope as established fact: retain the wording and use unresolved normalization
when scope cannot be established. Branch normalization describes that branch;
choice normalization describes the authored relationship and shared scope.

Choice `optional: true` permits omission of the whole requirement. Branch
optionality is scoped only to that branch and MUST NOT be propagated to the
choice or siblings. Neither optionality nor `and_or` defines a Boolean
constraint solver or conditional procedure.

For `1 cup butter or margarine`, both complete branches carry one cup:

```json
{
  "id": "fat",
  "relation": "or",
  "source_text": "1 cup butter or margarine",
  "alternatives": [
    {
      "id": "butter",
      "name": "butter",
      "quantity": {
        "kind": "simple",
        "amount": { "value": "1" },
        "unit": "volume.cup.us.customary"
      }
    },
    {
      "id": "margarine",
      "name": "margarine",
      "quantity": {
        "kind": "simple",
        "amount": { "value": "1" },
        "unit": "volume.cup.us.customary"
      }
    }
  ]
}
```

A differing-quantity choice uses the same shape:
`1 cup butter or 3/4 cup shortening` gives the second branch quantity `3/4`.
Scaling MUST visit every branch quantity without choosing a branch; existing
package-size and temperature scaling rules continue. Authored text MUST remain
unchanged. Readers SHOULD render choices compactly and naturally, and MAY elide
repeated quantities for display when the full structured quantities are equal.

A step ingredient use MAY reference the choice or an individual branch. A
whole-choice reference MUST omit `quantity`; it associates the requirement with
the step without selecting a branch or asserting all branches are used. To
express differing use amounts, reference the corresponding branches with
independently authored quantities. A branch reference is contingent on that
branch being included and MUST NOT be interpreted as selecting it. Distinct
branch uses MAY coexist in a step; duplicate references remain forbidden.
Instruction text remains authoritative and no conditional step language is
introduced.

A semantic round trip MUST preserve the relationship, ordered branches, scoped
modifiers, optionality, and references. Retaining only the source line while
flattening or dropping branches is lossy.

### 10.2. Package size and ingredient temperature

`package_size` is a simple physical quantity describing each counted item or
container. For example, two 14-ounce cans use `container.can` for the ingredient
quantity and 14 ounces of mass for `package_size`. A whole chicken whose
authored weight is a range MAY use `count.item` with a mass range in
`package_size`. Its unit MUST be a registered physical mass, volume, or length
unit; temperature units are invalid.

`temperature`, when present, describes an authored ingredient temperature. It
uses either an amount with a registered temperature unit, or nonempty opaque
`text`; the two forms are mutually exclusive. Both forms MAY carry optional
`purpose` and `note`; only a numeric form MAY carry `source_text`. It is
independent of ingredient quantity and MUST NOT be scaled with recipe yield.
Temperature purpose has the same semantics as for step temperatures below; it
remains optional when the source establishes the temperature but not its
purpose.

### 10.3. Recipe dependencies

An ordinary ingredient MAY contain `recipe`, a recipe reference (section 6.12)
stating that the source makes this ingredient by another recipe, such as
`1 batch pastry cream (see Pastry Cream)`. The ingredient keeps its own `name`,
`quantity`, `note`, and `source_text`, which describe how much of the other
recipe's result this recipe uses.

A dependency records what the source authored. A writer MUST NOT add one because
an ingredient name matches another recipe's title, and MUST NOT record an
editorial suggestion, such as `you might also like our pastry cream`, as a
dependency. A component the source includes in this recipe with its own
ingredients and steps is a section, not a dependency.

A dependency does not import the other recipe's content. Readers and writers
MUST NOT copy the other recipe's ingredients or steps into this recipe, and an
unresolved dependency leaves this recipe complete and valid. Scaling this recipe
scales the ingredient's own quantity and does not change the other recipe. SREF
defines no expansion of dependencies for cooking, shopping, or nutrition.

## 11. Instruction sections and steps

### 11.1 Temperatures

An ingredient's `temperature` and a step's `temperatures` use the same two
authored value forms:

- a numeric form with `amount` and a registered temperature `unit`; or
- an opaque form with nonempty `text`.

The forms are mutually exclusive. An opaque temperature MUST NOT carry `amount`,
`unit`, or `source_text`; its `text` is the complete authoritative authored
expression. `purpose` and `note` remain optional and orthogonal to the value
form. For example, `moderate oven` is opaque text and may carry purpose `oven`;
that purpose does not encode the word `moderate`.

Readers MUST preserve opaque text exactly. Writers MUST use opaque temperature
text rather than manufacture a numeric amount, range, or registered unit.
Implementations MUST NOT derive a numeric temperature or range from opaque text
during normalization or interchange unless the source itself supplies the
numeric information. When a source says `moderate oven (350 °F)`, the authored
numeric value may use the numeric form and its complete wording may use
`source_text`.

Opaque temperature is limited to an authored temperature or thermal condition in
the semantic role of a temperature. A burner or appliance power instruction such
as `cook over high heat` is not automatically a temperature. SREF defines no
qualitative-temperature scale, historical-oven conversion table, burner power
vocabulary, or application-generated cooking advice.

`instruction_sections` is an ordered, nonempty array independent from
`ingredient_sections`.

Each instruction section has:

- a recipe-local `id`;
- an optional `title`; and
- a nonempty ordered `steps` array.

Every step has:

- a recipe-local `id` unique across all instruction sections;
- an optional authored `title`; and
- nonempty `text`.

A step title is a label or heading for that individual step. It does not create
an instruction section or grouping boundary. Writers MUST preserve an authored
step title independently from the step text, even when the values are partly or
fully redundant. Readers MAY suppress substantially redundant title display, but
MUST NOT discard the stored title merely as a presentation optimization.

Instruction text remains required and authoritative. An importer whose source
provides only a step heading or name MUST copy that authored wording into
`text`; it MAY also retain the same wording as `title`. Importers MUST NOT
synthesize titles from ordinary step prose. For Schema.org, `HowToSection.name`
maps to an instruction-section title, `HowToStep.name` maps to a step title, and
`HowToStep.text` maps to step text.

A step MAY contain `ingredient_uses`, an ordered set of objects that associate
ingredients with the step. Each ingredient use contains:

- `ingredient_ref`: an ingredient ID that MUST resolve in the same recipe; and
- optional `quantity`: the authored amount of that ingredient used by the step.

The quantity uses the same simple, sum, alternative, or opaque representation as
an ingredient quantity. Omitting it means only that the ingredient is involved;
it does not assert that the step uses the ingredient's entire declared quantity.
A step MUST NOT contain more than one use for the same ingredient.

Ingredient-use quantities are independent authored assertions. Validators MUST
NOT require the uses of an ingredient to equal or exhaust its declared quantity,
and writers MUST NOT infer a missing use quantity by subtraction. Exact, range,
sum, and alternative use quantities scale with recipe yield under the rules in
[Quantity and unit processing](docs/quantity-and-units.md#scaling). Opaque use
quantities follow the same non-mechanical scaling rule as other opaque
quantities.

A step MAY contain `image_refs`, an ordered set of asset IDs. Every reference
MUST resolve to an image asset in the same recipe. Duplicate references within
one step are invalid. `image_refs` associates supporting images with the step;
it does not replace the step's authoritative instruction text.

A step MAY contain `timing_refs`, an ordered set of timing assertion IDs. Every
reference MUST resolve to `times.assertions` in the same recipe. Duplicate
references within one step are invalid. A step can refer to several assertions,
and several steps can refer to one assertion. The timing assertion remains the
one canonical representation of that authored timing fact.

A step MAY also contain `temperatures`, an ordered list of authored temperatures
relevant to the step.

Each temperature uses one of the forms in section 11.1. Multiple entries may
preserve different assertions in one step, such as an oil temperature and an
internal food target.

`purpose`, when present, contains a required `kind`. The standardized kinds are:

- `oven`: an oven setpoint;
- `internal`: a temperature within food;
- `oil`: cooking oil or fat used as a heated medium;
- `water`: water or a water-based cooking medium;
- `surface`: a cooking or food surface; and
- `other`: another explicitly supported purpose.

`other` MUST carry a nonempty `label` preserving the source's terminology. Any
known kind MAY also carry a label that adds source-authored specificity, such as
`breast` for an internal target. A label refines presentation; it does not
change the standardized kind.

Purpose is optional. A writer or importer MUST NOT infer it from array position,
from a unit, or merely because the instruction text makes a guess seem
plausible. When a defensible purpose is not available, the temperature remains
valid without one. Unusual purposes use `other` and a label rather than
extending the closed vocabulary. Released kinds MUST NOT change meaning.

Purpose describes what the temperature applies to. It does not declare required
equipment, state a completion rule, or replace the authoritative instruction
text. For example, `oven` does not create an equipment entry, and `internal`
does not by itself instruct a reader when cooking is complete. Timing
assertions, timing references, and temperatures MUST NOT change during recipe
scaling.

Steps are valid without references. Writers MUST NOT force users or importers to
create references that the source does not support.

SREF does not define structured actions or nested steps. Instruction text
remains authoritative even when a title, timing references, or temperatures are
present.

## 12. Assets

The optional `assets` array describes files associated with the recipe. Every
asset has:

- a recipe-local `id` unique within `assets`;
- a relative `path` below `assets/`;
- an IANA-style media type string;
- a lowercase SHA-256 digest; and
- a nonnegative byte `size`.

It MAY have `role`, `alt`, `caption`, and the provenance members below.

`role`, when present, classifies the carried file as `image`, `source`, or
`other`. It does not establish how the recipe uses the asset. In particular,
writers and readers MUST NOT derive recipe-level, primary, or step image
relationships from an asset role.

The recipe-level `image_refs`, when present, is an ordered set of asset IDs.
Every reference MUST resolve to an asset whose media type begins with `image/`.
Duplicate references are invalid. The order records the authored recipe image or
gallery order. An image asset that is merely present in `assets` is not
implicitly a recipe-level image.

`primary_image`, when present, MUST resolve to an image asset and MUST also
occur in the recipe-level `image_refs`. It identifies the preferred primary
image without changing the order of `image_refs`; it need not be the first
reference.

An image MAY occur in both recipe-level `image_refs` and one or more step
`image_refs`. Those references reuse one asset declaration and express
independent authored relationships.

Asset paths MUST:

- begin with `assets/`;
- use `/` as separator;
- contain no empty, `.` or `..` segment;
- be relative;
- contain no backslash;
- contain no NUL or control character; and
- match an entry in a package when the recipe is packaged.

Asset IDs and paths MUST each be unique.

A standalone JSON document is self-contained only when it has no declared
assets. A document with assets MUST be transported as a package or through an
explicit external mechanism outside SREF conformance.

Remote source URLs MAY be retained as provenance, but they do not satisfy an
asset declaration.

### 12.1 Asset provenance

An asset MAY carry metadata about the file itself, supplied by the source:

- `creator`: the name of the person or organization the source credits with
  creating the file;
- `credit`: the authored credit line, such as
  `Photo: Jane Smith for Example Kitchen`;
- `rights`: the authored copyright or rights statement, such as
  `© 2024 Jane Smith`;
- `license`: the license the source applies to the file, with a `name`, a `url`,
  or both; and
- `source_url`: an absolute URL of the page or file the asset came from.

These members describe the asset, not the recipe. Recipe authors, the recipe
`source`, and asset provenance are independent, and a writer MUST NOT fill one
from another. A caption is not a credit, and a credit is not a creator: text
such as `Courtesy of Example Foods` is a credit and does not name a creator.

Asset provenance MUST come from metadata the source attaches to that asset. A
writer MUST NOT infer a license, creator, or rights statement from a page
footer, a site-wide notice, the recipe author, or the fact that a file could be
downloaded. An absent `license` means the license is unknown. It does not mean
the file is unrestricted or in the public domain.

SREF preserves these statements and does not determine whether a license
applies, whether it was granted with authority, or what it permits. A consumer
that converts a recipe to a format that cannot carry asset provenance SHOULD
report the loss.

## 13. Extensions

Every non-extension member in a conforming recipe document MUST be defined by
the document's declared SREF version.

When a reader encounters a newer recipe version in the same compatibility line
than it fully implements, objects defined by the recipe schema MAY contain
non-extension members absent from the reader's supported schema. The reader MUST
treat those members as opaque possible standard members of the declared newer
version, MUST ignore them when interpreting known semantics, and MUST preserve
their JSON values semantically at the same object scope when rewriting. This
does not establish complete conformance to the newer version.

This allowance does not apply to a document declaring an exactly supported
version, or an older supported version for which the reader has a schema. A
non-extension member not defined by that declared version makes such a document
invalid.

An unknown member MUST NOT satisfy a required standard field or change the
meaning of a known field.

The preservation rule does not permit a producer to add undefined members. A
producer with application data uses the extension mechanism below. A producer
that uses a later standard field declares the version that defines it.

Objects MAY also contain extension members. An extension name MUST have the form
`x-<reversed-domain>.<local-name>`, for example `x-org.example.nutrition`. The
portion after `x-` MUST:

- contain at least three dot-separated labels: at least two labels identifying
  the reversed domain followed by one or more extension-specific labels;
- contain only lowercase ASCII letters, digits, and interior hyphens in each
  label;
- begin and end every label with a letter or digit;
- contain at most 63 characters per label and 128 characters in total.

There is no upper bound on label count beyond the length limits above, so a
publisher MAY nest extension-specific labels: `x-org.example.import.paprika` and
`x-com.example.recipe.display.compact` are both valid. The minimum is three
labels because two labels name only a domain.

`x-sref.spec.*` is reserved for extension fixtures and other extensions defined
by this specification, at any depth the rule above allows, such as
`x-sref.spec.round-trip.ordinal`. Extension values MAY be any JSON value. The
extension name rule applies to members of SREF-defined objects, not to object
member names inside an opaque extension value. Publishing an extension MUST
identify its complete namespace prefix, the corresponding DNS domain, and its
owner so the boundary between domain and local labels is unambiguous.

Except for the reserved `x-sref.spec.*` namespace, the publisher of an extension
MUST control the corresponding DNS domain when the namespace is first published.
Namespace ownership remains with that publisher if the domain later changes
hands; a domain transfer MUST NOT silently transfer or authorize reuse of an
existing extension namespace. Ownership MAY be transferred, or a subnamespace
MAY be delegated, only through an explicit, publicly documented agreement.
Publishers SHOULD retain durable documentation of ownership and delegation
independently of current DNS records.

A conforming round-trip reader/writer MUST preserve unknown standard members
accepted under the compatible-newer rule above, and MUST preserve unknown `x-`
members at the same object scope, unless the caller explicitly requests a lossy
removal.

Extensions MUST NOT:

- redefine a standard member;
- weaken a conformance requirement;
- override core quantities, unit-registry IDs, ingredient references,
  instruction relationships, recipe-local identity, timing assertions, asset
  declarations, or integrity metadata;
- change the interpretation of any standard value; or
- be required to recover the standard recipe semantics claimed by the document.

A reader that does not support an extension MUST treat its value as opaque JSON.
It MUST NOT reject an otherwise conforming recipe because the extension is
unsupported, infer or guess extension semantics, or allow the extension to alter
its interpretation of core data. It MUST preserve the extension for a lossless
round trip as described above.

An implementation that cannot preserve an unsupported extension MAY read and
process the core document, but it MUST treat the document as read-only or
require an explicitly lossy operation before rewriting it. Merely lacking
extension support MUST NOT make an otherwise conforming core document invalid.

Promoting extension semantics into the SREF core requires an explicit standard
field, a format-version change when required by the compatibility rules, and
documented migration. Implementations MUST NOT silently reinterpret an existing
extension member as the promoted core field. The original extension namespace
and its ownership remain unchanged.

Whether to promote a concept is a governance decision, not a conformance
requirement. The criteria are in
[docs/change-process.md](docs/change-process.md#core-admission).

An implementation MUST NOT assume that an unknown member is an extension merely
because it does not understand it. Names beginning with `x-` are extensions;
other unknown names are reserved for compatible standardized evolution.

The optional top-level `extensions` object is available for namespaced extension
documents. Its keys follow the same naming rule. It does not replace scoped `x-`
members when the extension belongs to a particular ingredient or step.

## 14. Package representation

A SREF package is a ZIP archive conventionally using the `.sref` suffix.

It MUST contain exactly one root `recipe.json` and one root `manifest.json`.
Declared assets MUST appear at their exact paths below `assets/`.

The package manifest uses `schema/manifest.schema.json` and records the digest
and byte size of `recipe.json` and every asset.

The manifest itself is not included in its own file list because doing so would
create a recursive digest.

Package processing rules are specified in
[docs/package-format.md](docs/package-format.md).

## 15. Package safety

A conforming package reader MUST, before extraction:

1. reject absolute paths;
2. reject backslashes and drive-letter paths;
3. reject empty, `.` and `..` path segments;
4. reject symbolic links, hard links, devices, and other nonregular entries;
5. reject duplicate normalized paths;
6. reject undeclared files;
7. impose limits on compressed bytes, expanded bytes, individual files, entry
   count, path length, and compression ratio;
8. calculate digests while streaming rather than trusting archive metadata;
9. verify declared byte sizes and SHA-256 digests; and
10. avoid writing any file outside an isolated destination selected by the
    caller.

For duplicate detection, a normalized path is the original archive name
normalized to Unicode NFC and then Unicode case-folded. This comparison is only
a collision check: a reader MUST validate and report the original name, and MUST
NOT normalize an unsafe name into an accepted path.

A reader SHOULD validate in memory or a temporary isolated directory before
moving accepted data into an application data store.

SREF does not define encryption or digital signatures. Encrypted ZIP entries are
invalid.

## 16. Manifest and package completeness

The manifest declares:

- the SREF package version;
- the recipe entry; and
- zero or more asset entries.

The `recipe.json` digest and size MUST match the uncompressed file bytes.

For assets, the manifest and recipe MUST agree on ID, path, media type, digest,
and size. Every recipe asset MUST have exactly one manifest entry, and every
manifest asset MUST have exactly one recipe asset declaration.

Archive metadata such as CRC values does not replace the SHA-256 requirement.

## 17. Bundle representation

A SREF bundle carries an ordered collection of complete recipe packages in one
file. Its physical representation is a ZIP archive and its file suffix is
`.srefbundle`.

A bundle is a container, not a second recipe model. It introduces no recipe
document of its own, no shared asset store, and no collection semantics beyond
the order it states.

A bundle MUST contain exactly one root `manifest.json` and one member below
`recipes/` for every recipe the manifest declares. No other entry is allowed.

Each member below `recipes/` MUST be a complete package as defined in
section 14. A reader that extracts one member and discards the bundle MUST be
left with a package it can process by the ordinary package rules, without
knowledge of the bundle, the application that wrote it, or the other members. A
writer MUST NOT produce a member that depends on anything outside itself. A
translation relationship naming another member (section 6.9) is not such a
dependency: the member is complete without its counterpart.

Member paths MUST be `recipes/<member-id>.sref`, where `<member-id>` is a
bundle-local identity chosen independently of the recipe the member carries.
Because a member ID matches the portable identifier syntax, the resulting path
contains no separator, no dot segment, and no character a path rule rejects.
Member IDs and member paths MUST each be unique within a bundle. Recipe IDs are
local to their own recipe documents and need not be unique across members. A
writer MUST NOT mutate recipe-local identity or references to make a package
unique within a bundle.

A member ID is transport identity only. It has no meaning outside its bundle and
MUST NOT be copied into or substituted for recipe-local identity. Writers SHOULD
generate opaque member IDs from bundle order rather than expose titles,
filenames, or application database identifiers in member paths.

A bundle carries at least one recipe. An empty bundle is invalid.

The bundle format defines no maximum member count. Readers MUST impose a finite
member-count limit as part of their resource policy and MAY reject an otherwise
conforming bundle that exceeds it. Such a rejection is a local resource-limit
decision, not a claim that the bundle manifest is structurally invalid. Writers
MUST NOT assume that every reader can accept every representable bundle size.

Duplicated bytes between members are expected. Two recipes that declare the same
asset each carry it, so every member remains a complete package. Bundle version
1 defines no asset sharing between members.

Bundle processing rules are specified in
[docs/bundle-format.md](docs/bundle-format.md).

## 18. Bundle manifest

`manifest.json` validates against
[`schema/bundle-manifest.schema.json`](schema/bundle-manifest.schema.json).

```json
{
  "format": "sref-bundle",
  "version": 1,
  "recipes": [
    {
      "member_id": "r000001",
      "recipe_id": "apple-pie",
      "path": "recipes/r000001.sref",
      "sha256": "...",
      "size": 12345
    }
  ]
}
```

`format` identifies the container. `version` identifies the bundle layout and is
versioned independently of the recipe specification version, the package
version, and the unit registry: a bundle states nothing about which SREF
versions its members use, and its members state their own.

`recipes` is ordered, and the order is the bundle's own meaning. A writer that
was given an order MUST preserve it; a reader MUST NOT reorder members when
presenting the bundle.

Each entry declares its bundle-local `member_id`, the informational `recipe_id`
of the recipe it carries, the member `path`, and the SHA-256 digest and
uncompressed byte size of the exact member bytes. `member_id` MUST be unique in
the bundle, and `path` MUST be `recipes/<member_id>.sref`. `recipe_id` MUST
equal the `id` inside that member, but it need not be unique across members.

A bundle manifest MUST NOT record application state. In particular it does not
carry local identifiers, collection membership, tags, ratings, favorites,
cooking history, revision numbers, or the name or version of the writing
application. Section 21 applies to a bundle exactly as it applies to a recipe.

A bundle manifest MUST NOT record a generation timestamp. Excluding the clock
avoids unnecessary nondeterminism and makes exact-byte output easier for a
writer to reproduce. It does not guarantee artifact identity: JSON and ZIP
serialization are noncanonical, and semantically equivalent recipe packages can
have different bytes and therefore different bundle member digests.

## 19. Bundle safety

A conforming bundle reader MUST apply the archive rules of section 15 to the
outer archive before reading anything from it, and MUST apply them again to each
member package it opens.

It MUST additionally:

1. reject a member the manifest does not declare;
2. reject a declared member the archive does not carry;
3. reject a duplicate `member_id` or member path;
4. reject a member path that is not `recipes/<member_id>.sref`;
5. verify each member's declared size and SHA-256 digest against the bytes it
   reads, before opening the member as a package; and
6. bound the number of members, the total expanded size, and the work spent on
   any one member, independently of the limits it applies inside a member.

Verifying a member does not establish that the package inside it is valid. A
reader MUST validate each member as a package in its own right.

## 20. Reproducible bundle writing

Given the same exact member bytes in the same order, a writer SHOULD produce the
same bundle bytes. This is a writer reproducibility goal, not a canonicalization
guarantee. SREF does not require canonical JSON, package, or bundle ZIP bytes,
and a reader MUST NOT depend on them. A bundle digest identifies one exact
artifact; it does not establish that semantically equivalent bundles have the
same bytes or digest.

A writer that pursues determinism SHOULD normalize archive member metadata
rather than record local filesystem timestamps, and SHOULD store rather than
recompress members, which are already compressed archives.

## 21. Application state excluded from recipes

The following are outside the recipe document:

- application user or household ownership;
- permissions and sharing grants;
- favorites;
- personal ratings;
- private notes;
- collection membership;
- last-cooked timestamps and cooking history;
- database IDs and row versions; and
- synchronization or audit records.

Applications MAY back up this state separately. They MUST NOT claim that a SREF
recipe document is a complete application backup.

The same holds for a bundle. A bundle of every recipe an application holds is
still an ordered collection of portable recipes: it carries no revision history,
no trash, no collection structure, no local identifiers, and no configuration.
An application MUST NOT present a bundle as its backup or recovery artifact.

## 22. Conformance

SREF defines separate conformance capabilities:

- **JSON reader**: accepts valid recipe JSON and enforces structural and
  semantic requirements.
- **JSON writer**: emits valid recipe JSON with canonical normalized amounts.
- **Package reader**: satisfies JSON-reader and package-safety requirements.
- **Package writer**: satisfies JSON-writer and package-completeness
  requirements.
- **Bundle reader**: satisfies package-reader requirements and the bundle safety
  and completeness requirements.
- **Bundle writer**: satisfies package-writer requirements and produces bundles
  whose members are independently valid packages.
- **Registry implementation**: interprets the named unit registry without
  changing unit meaning.
- **Unit conversion**: performs exact and affine conversion, propagates
  approximation, and rejects incompatible or nonphysical units.
- **Ingredient-line parser**: satisfies the corpus expectations without
  inventing prohibited semantics.
- **Unit resolution**: applies source evidence and the resolution decisions of
  section 9.5 to unqualified unit occurrences, producing the specified identity,
  an unresolved outcome, or a reported conflict.
- **Round-trip implementation**: preserves standard fields, ordering, original
  text, IDs, references, unknown standard members, opaque future registry IDs,
  and unknown extensions through a read/write cycle.

A conformance declaration MUST identify the exact SREF version, unit-registry
version, and implemented capabilities.

See [docs/conformance.md](docs/conformance.md) and
[conformance/manifest.json](conformance/manifest.json).

### 22.1 Processor failure categories

A processor that rejects a SREF artifact, or refuses a SREF-defined operation on
one, MUST classify the failure under exactly one of the following categories,
and MUST make that category available to its caller in machine-readable form.

| Category                       | Meaning                                                                                                                                                                                                        |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `invalid-artifact`             | The recipe document, package, bundle, manifest, or registry violates a syntax, schema, semantic, reference-integrity, or version-defined content rule, and none of the more specific categories below applies. |
| `unsupported-format-version`   | The declared SREF recipe, package, or bundle format version belongs to an unsupported compatibility line. A merely newer compatible version is not sufficient for this category.                               |
| `unsupported-registry-version` | The declared unit-registry version belongs to an unsupported compatibility line. A merely newer compatible registry version is not sufficient for this category.                                               |
| `unknown-unit`                 | The applicable registry version is otherwise understood or readable, but the referenced unit identifier or its semantics are unavailable for the requested validation or unit-dependent operation.             |
| `integrity-failure`            | Declared digests, sizes, member identities, paths, or cross-manifest assertions disagree with the artifact's actual bytes or members.                                                                          |
| `unsafe-archive`               | An archive contains a forbidden path, entry type, normalized-path collision, duplicate entry, or other structure that cannot be processed safely.                                                              |
| `resource-limit`               | Processing stopped because an implementation's finite size, nesting, expansion, time, or other resource budget was exceeded. This category does not assert that the artifact is intrinsically invalid.         |

`invalid-artifact` is the fallback category. Where one isolated failure clearly
belongs to a more specific category, a processor MUST report that more specific
category rather than the fallback.

This specification does not prescribe how the category reaches a caller. An
exception property, a result object, an enumeration, a command-line JSON member,
or any equivalent interface satisfies the requirement. Human-readable messages,
exception classes, path representation, diagnostic context, and
implementation-specific detail codes remain implementation-defined, and a caller
MUST NOT depend on them.

These boundaries decide most classifications:

- `unsafe-archive` describes archive structure. A recipe document declaring an
  asset path that violates section 12 is `invalid-artifact`; the same path
  appearing as an entry in a package or bundle is `unsafe-archive`.
- `unknown-unit` describes a unit whose meaning is unavailable from a registry
  the processor can otherwise use. A registry snapshot that is itself invalid is
  `invalid-artifact`, and one from an unsupported compatibility line is
  `unsupported-registry-version`.
- `integrity-failure` requires a declaration to disagree with the artifact's
  actual bytes, or with another member of it. A defect visible in the
  declarations alone, such as a manifest that declares the same asset twice,
  repeats a member identifier, or gives a member a path not derived from its
  identity, is `invalid-artifact`.

The archive rules of sections 15 and 19 are applied before anything is read out
of the archive, and that ordering decides the category. An entry rejected by
those rules (its path shape, its entry type, a normalized-path collision, or a
bundle layout other than `recipes/<member_id>.sref`) is `unsafe-archive`, and
remains so whether or not a manifest would have declared it. An entry that
satisfies them and only disagrees with a manifest is `integrity-failure`. An
archive missing a member no declaration has yet named, such as a package without
`manifest.json`, is `invalid-artifact`.

The set of failure categories is open, and a category's meaning never changes. A
caller that encounters a category it does not recognize MUST treat the operation
as unsuccessful, and MAY fall back to generic handling; it MUST NOT reinterpret
it as success.

### 22.2 Reporting more than one failure

This specification defines neither a universal validation order nor a precedence
among independent failures. A processor MAY report one applicable failure or
several, and each reported failure carries its own category.

Consequently, an implementation MUST NOT be judged nonconforming merely because
it identified a different defect first. A conformance case that requires a
particular category or requirement isolates that fault; an artifact carrying
independent defects cannot require one of them to win.

A `resource-limit` result is not evidence that any other defect was detected.
Resource thresholds are implementation policy except where this specification
establishes a required floor.

## 23. Semantic validation requirements

In addition to JSON Schema, validators MUST check:

- every non-extension member is defined by the document's declared recipe
  version, except for opaque members admitted while reading a newer compatible
  recipe version;
- canonical and bounded rational values;
- `min <= max` for ranges;
- recipe-wide uniqueness of ingredient IDs;
- recipe-wide uniqueness of step IDs;
- uniqueness of section IDs within their respective section types;
- resolution and uniqueness by `ingredient_ref` within step `ingredient_uses`;
- resolution, image media type, and uniqueness of step `image_refs`;
- resolution, image media type, and uniqueness of recipe-level `image_refs`;
- uniqueness of timing assertion IDs;
- a `label` on every timing assertion whose kind is `other`;
- resolution and uniqueness of step `timing_refs`;
- asset ID and path uniqueness;
- `primary_image` resolution, image media type, and membership in recipe-level
  `image_refs`;
- supported or forward-compatible recipe and registry versions;
- existence of referenced unit IDs in an exact supported registry snapshot;
- opaque preservation of syntactically valid IDs introduced by a newer
  compatible registry;
- physical-unit use in `package_size`;
- temperature-unit use in ingredient and step temperatures;
- non-temperature-unit use in equipment quantities;
- non-temperature-unit use in yield quantities and nutrition basis quantities;
- nutrition value forms: energy units only for `energy`, mass units never for
  `energy`, and no nutrient and label repeated within one statement;
- a `quantity` nutrition basis carrying `quantity`, and an `unspecified` basis
  carrying none;
- uniqueness of variant IDs, and resolution of every dietary-claim and
  allergen-declaration `variant_ref`;
- no ingredient `recipe.recipe_id` equal to the recipe's own `id`;
- valid BCP 47 language and locale tags, including translation languages;
- a recipe `language` wherever `translations` occur, at most one `original`
  translation, and no translation `recipe_id` equal to the recipe's own `id`;
- package manifest/recipe agreement;
- package path and extraction safety;
- bundle manifest and member agreement, including member digests and sizes; and
- bundle member independence, so every member validates as a package on its own.

Validators SHOULD report all independent failures they can identify safely,
rather than stop after the first field error. Each reported failure carries its
own category under section 22.1, and section 22.2 governs how several of them
are treated together.

## 24. Round-trip semantics

Round-trip conformance is semantic, not byte-for-byte. A writer MAY change JSON
member ordering and insignificant whitespace.

It MUST preserve:

- every standard field and array order;
- author order, names, kinds, kind labels, and URLs;
- authored category, course, cuisine, cooking-method, and keyword order;
- publication and modification values without changing date precision;
- exact rational values;
- source and opaque text;
- normalization method, review, and warnings;
- ingredient optionality;
- variant order, titles, and text;
- equipment order, names, quantities, and notes;
- recipe-local IDs and references;
- unit IDs and registry version;
- ingredient temperatures, timing assertions, step timing references, and step
  temperatures;
- temperature purpose kinds and labels;
- timing assertion order, duration-expression shape, source text, and authored
  attention semantics;
- microwave condition roles, source text, restrictions, and ordered choice
  pairings;
- translation order, relations, languages, titles, recipe IDs, and URLs;
- yield assertion order and every assertion, including ones that appear
  equivalent;
- nutrition statement order, bases, nutrient order, labels, amounts, units,
  source text, and opaque values;
- dietary claim and allergen declaration order, text, subjects, suitability,
  presence, conditions, and variant references;
- variant IDs;
- ingredient recipe references;
- asset metadata, including asset provenance;
- unknown standard members accepted from a newer compatible recipe version, at
  the same scope;
- unknown extension members at the same scope; and
- field presence when omission has semantics distinct from an explicit value or
  empty array.

Field presence is not independently authored information when this specification
defines an omitted field to have the same semantics as an explicit default. A
writer MAY omit or materialize such a default during a round trip. In
particular, omitted `approximate` and explicit `"approximate": false` are
semantically equivalent for amounts and normalized duration expressions, as are
omitted `optional` and explicit `"optional": false` for an ingredient. The
permission covers only the default value: dropping `"optional": true` is a loss
of authored meaning, not a materialized default. This permission does not apply
to unknown standard members admitted from a newer compatible recipe version, or
to extension members, whose presence and JSON value MUST be preserved.

A writer MUST NOT replace an original unit with a display conversion during a
round trip.

## 25. Excluded semantics

SREF does not standardize:

- expansion or resolution of recipe dependencies, or recipes nested inside a
  recipe document;
- portable collections, books, or chapters, which a bundle's order does not
  claim to be;
- recipe revision identity;
- canonical JSON or ZIP bytes;
- digital signatures or encryption;
- nutrition calculation, dietary targets, or nutritional scoring;
- ingredient ontologies or density conversions;
- allergen or diet vocabularies beyond the subjects of section 6.11, or safety
  certification;
- rights adjudication for assets;
- multilingual parallel fields;
- application backup state; or
- a universal set of yield labels.

Implementations MAY experiment through extensions. Experimental extensions MUST
NOT be presented as standard SREF fields.
