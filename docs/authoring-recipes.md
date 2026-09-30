# Authoring a SREF recipe

This tutorial creates a small recipe document and validates it. It assumes a
checkout of this repository and Python 3.10 or later. Run commands from the
repository root with the
[development environment](../CONTRIBUTING.md#set-up-the-repository) active.

## 1. Start from the maintained minimal fixture

Copy [`tests/valid/minimal.recipe.json`](../tests/valid/minimal.recipe.json) to
a working file outside `tests/`. Starting from the fixture avoids copying a
stale format or registry identifier from prose.

```sh
cp tests/valid/minimal.recipe.json /tmp/my-recipe.recipe.json
```

Change `id` and `title` in that working file. Keep the identifier portable:
begin with an ASCII letter or digit, then use only ASCII letters, digits,
periods, underscores, or hyphens, up to 128 characters total. Digit-leading
UUIDs are valid as written.

Add credited authors as ordered objects. A name is enough when the source gives
no trustworthy classification:

```json
"authors": [
  {"name": "Avery Morgan"},
  {
    "name": "Example Test Kitchen",
    "kind": "organization",
    "url": "https://recipes.example/test-kitchen"
  }
]
```

Use `person` or `organization` only when the source establishes that kind. For
another explicit source classification, use `kind: "other"` with an optional
`kind_label`. Do not classify an ambiguous displayed name or turn the source
website or importing application into a recipe author.

Preserve classifications and publication chronology only when the recipe or
source states them:

```json
"categories": ["Bread"],
"courses": ["Breakfast"],
"cuisines": ["French"],
"cooking_methods": ["Baking"],
"keywords": ["overnight", "weekend"],
"published": "2024-03-10",
"modified": "2025-01-18T14:30:00-05:00"
```

Use `categories` when a source offers one undifferentiated classification field.
Use `courses` separately only when the source distinguishes a meal role. Keep a
date as a date and a timestamp with its stated offset; do not invent a time or
timezone. These fields belong to the authored work, not to library tags,
retrieval history, SREF export time, or the current application revision. Do not
infer them from the recipe prose.

## 2. Add ingredients without inventing meaning

Each ingredient needs a recipe-local ID and name. Add a normalized quantity only
when its meaning is defensible.

For an exact metric amount:

```json
{
  "id": "flour",
  "name": "bread flour",
  "quantity": {
    "kind": "simple",
    "amount": { "value": "500" },
    "unit": "mass.gram"
  },
  "source_text": "500 g bread flour"
}
```

For an amount that cannot be normalized safely:

```json
{
  "id": "oil",
  "name": "olive oil",
  "quantity": {
    "kind": "opaque",
    "text": "a thin drizzle"
  },
  "source_text": "a thin drizzle of olive oil",
  "normalization": {
    "method": "unresolved",
    "warnings": ["The authored measure has no defensible physical quantity."]
  }
}
```

Do not use zero for `to taste`, and do not convert volume to mass through an
unstated ingredient density.

When the source says an ingredient may be left out, record that as `optional`
rather than burying it in prose:

```json
{
  "id": "blueberries",
  "name": "blueberries",
  "quantity": {
    "kind": "simple",
    "amount": { "value": "1/2" },
    "unit": "volume.cup.us.customary"
  },
  "optional": true,
  "source_text": "1/2 cup blueberries (optional)",
  "normalization": { "method": "extracted" }
}
```

The test is whether the author sanctioned leaving it out, not whether a cook
physically could. Set `optional` only for that. `Salt to taste` is required but
unquantified, so omit `quantity` and keep the wording in `source_text`.
`Lemon wedges, for serving` describes a purpose and `preferably fresh parsley`
describes a preference, so both use `note`.

`optional` defaults to `false`, so leave it off ordinary ingredients rather than
marking every one of them required. Optionality belongs to the occurrence: if a
garnish section repeats an ingredient the method already requires, only the
garnish entry is optional.

When the source describes an alternate version of the whole recipe, record it as
a variant rather than as a note:

```json
{
  "variants": [
    {
      "title": "Vegetarian version",
      "text": "For a vegetarian version, omit the bacon and replace the chicken stock with vegetable stock."
    }
  ]
}
```

Keep the authored wording. A variant is preserved, not applied, so do not try to
express the change as structured edits and do not restructure the recipe inside
it. Variants do not nest.

Three nearby things stay apart. A base recipe that permits an omission uses
`optional` on the ingredient. One ingredient occurrence offering interchangeable
choices uses an alternative quantity. Only an authored alternate version of the
recipe is a variant. If the source gives something its own structured ingredient
list and instructions, it is a separate recipe, regardless of what the source
calls it.

Record equipment the recipe requires as an ordered root collection:

```json
"equipment": [
  {
    "name": "baking sheet",
    "quantity": {
      "kind": "simple",
      "amount": {"value": "2"},
      "unit": "count.item"
    }
  },
  {
    "name": "stand mixer with dough hook",
    "note": "A sturdy hand mixer may not handle this dough."
  }
]
```

Keep dimensions and qualifications in the authored name or note; do not invent
an equipment taxonomy. Do not scale equipment quantities with yield, turn a
user's ownership or availability into recipe data, or add step references.
Procedural setup remains in the instructions when the source states it as an
action.

When an ingredient is made by another recipe, keep the ingredient and add a
`recipe` reference with whatever identity the source gives:

```json
{
  "id": "pastry-cream",
  "name": "pastry cream",
  "quantity": {
    "kind": "simple",
    "amount": { "value": "400" },
    "unit": "mass.gram"
  },
  "source_text": "400 g pastry cream (see Vanilla Pastry Cream)",
  "recipe": {
    "title": "Vanilla Pastry Cream",
    "url": "https://recipes.example/vanilla-pastry-cream"
  }
}
```

Do not copy the other recipe's ingredients into this one, and do not add a
reference because a name matches another recipe's title.

## 3. Keep components independent

Create ingredient sections for components such as dough and filling. Create
instruction sections for the actual workflow. Their boundaries do not need to
match.

Give every step a recipe-local ID. Add `ingredient_uses` only where the
relationship is clear; the recipe remains valid without them. Each use requires
an `ingredient_ref`. Add its optional `quantity` only when the source states how
much the step uses:

```json
"ingredient_uses": [
  {
    "ingredient_ref": "sugar",
    "quantity": {
      "kind": "simple",
      "amount": {"value": "3/2"},
      "unit": "volume.cup.us.customary"
    }
  }
]
```

Do not force step quantities to add up to the ingredient's declared quantity or
infer a missing amount from other steps. Preserve a bare `ingredient_ref` when
the source says only that an ingredient is involved.

## 4. Record timings and temperatures without rewriting the instruction

Store each authored timing fact once under `times.assertions`:

```json
"times": {
  "assertions": [
    {
      "id": "bake-time",
      "kind": "cook",
      "duration": {
        "min": "PT18M",
        "max": "PT22M",
        "source_text": "18–22 minutes"
      },
      "attention": "passive"
    }
  ]
}
```

Keep the complete instruction in `text`, then refer to that assertion and add
machine-readable temperatures:

```json
{
  "id": "bake",
  "text": "Bake at 220 °C for 18–22 minutes, until deeply browned.",
  "timing_refs": ["bake-time"],
  "temperatures": [
    {
      "amount": { "value": "220" },
      "unit": "temperature.celsius",
      "purpose": { "kind": "oven" },
      "source_text": "220 °C"
    }
  ]
}
```

One step can list several timing references, and several steps can refer to the
same assertion. Do not duplicate a timing assertion inside a step. Structured
timings and temperatures support cooking views and display conversion, but the
instruction text remains authoritative.

Use a temperature purpose only when the source supports it. The stable kinds are
`oven`, `internal`, `oil`, `water`, `surface`, and `other`. An unusual purpose
uses `other` with the source's label; do not add a new kind or infer a purpose
from array order. Purpose does not declare equipment or make an internal target
into completion logic.

When the source supplies a temperature condition without a numeric reading,
write its exact wording as `text` instead of guessing an amount or unit:

```json
{ "text": "moderate oven", "purpose": { "kind": "oven" } }
```

This is an opaque temperature, not a standardized heat-level scale. Do not turn
`moderate oven`, `quick oven`, or `very slow oven` into a numeric value or
range. Conversely, `cook over high heat` is usually a burner-power instruction,
not automatically a temperature.

## 5. Validate

Validate the working document against this checkout's schema and semantic
checks. This uses the repository's reference helpers, not an installed runtime
library API:

```sh
python3 - <<'PYTHON'
from pathlib import Path
from conformance.validate import ROOT, load_json, recipe_semantic_errors, validator

recipe = load_json(Path("/tmp/my-recipe.recipe.json"))
validator("recipe.schema.json").validate(recipe)
registry = load_json(ROOT / "registry/units.json")
units = {unit["id"]: unit for unit in registry["units"]}
errors = recipe_semantic_errors(recipe, units)
if errors:
    raise SystemExit("\n".join(errors))
print("Recipe schema and semantic checks passed")
PYTHON
```

`python3 conformance/validate.py` validates the repository's indexed artifacts;
it does not discover or validate your working file outside that index. For a
runtime library, follow the [implementation guide](implementation-guide.md).
Passing JSON Schema alone is insufficient.

### Preserve step headings without inventing sections

Use an instruction-section `title` only for a real authored grouping. When the
source gives one step both a heading and prose, preserve the heading on the step
itself:

```json
{
  "id": "make-sauce",
  "title": "Make the sauce",
  "text": "Whisk the butter, flour, and milk until smooth."
}
```

For Schema.org imports, map `HowToSection.name` to the section title,
`HowToStep.name` to the step title, and `HowToStep.text` to the step text. If a
step has only `name`, copy that wording into required `text` and optionally
retain it as `title`; do not create a one-step section or invent a title from
ordinary prose.

## 6. Add assets only through a package

A standalone document with declared assets is not self-contained. Follow
[the package reference](package-format.md) and place the recipe, manifest, and
all declared files in a `.sref` archive.

Declare recipe and step image relationships explicitly. `image_refs` at the
recipe root records ordered gallery membership, `primary_image` selects one of
those recipe images, and a step's `image_refs` records images that support that
instruction. The same asset can occur in both arrays:

```json
{
  "image_refs": ["finished-dish", "mixing-step"],
  "primary_image": "finished-dish",
  "instruction_sections": [
    {
      "id": "method",
      "steps": [
        {
          "id": "mix",
          "text": "Mix until smooth.",
          "image_refs": ["mixing-step"]
        }
      ]
    }
  ]
}
```

Do not use an asset role to imply gallery, primary, or step placement. Asset
roles are limited to `image`, `source`, and `other`.

Record asset provenance only from metadata the source attaches to that file:

```json
{
  "id": "finished-dish",
  "path": "assets/finished-dish.jpg",
  "media_type": "image/jpeg",
  "sha256": "…",
  "size": 48213,
  "credit": "Photo: Jane Smith",
  "license": {
    "name": "CC BY 4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/"
  }
}
```

Do not copy a page footer, the recipe author, or the recipe source into asset
provenance. Leave `license` out when the source does not state one.

## 7. Record yields, nutrition, and claims as the source states them

List every yield the source states, in its order. Do not add a conversion of one
yield into another:

```json
"yields": [
  {"text": "24 cookies", "quantity": {"kind": "simple", "amount": {"value": "24"}}, "label": "cookies"},
  {"text": "12 servings", "quantity": {"kind": "simple", "amount": {"value": "12"}}, "label": "servings"}
]
```

Give nutrition the basis the source establishes. Use `unspecified` when the
source lists values without saying what they describe, and keep wording such as
`trace` as text:

```json
"nutrition": [
  {
    "basis": {"kind": "serving", "text": "2 cookies"},
    "nutrients": [
      {"nutrient": "energy", "amount": {"value": "310"}, "unit": "kcal"},
      {"nutrient": "fiber", "text": "less than 1 g"}
    ]
  }
]
```

Record dietary claims and allergen declarations only when the source makes them.
Keep a condition as a condition:

```json
"dietary_claims": [
  {"text": "Vegan when made with plant-based milk", "suitability": "suitable", "diet": "vegan", "condition": "when made with plant-based milk"}
],
"allergen_declarations": [
  {"text": "May contain tree nuts", "substance": "tree nuts", "presence": "may_contain"}
]
```
