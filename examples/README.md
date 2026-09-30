# Examples

These original recipes show complete, realistic recipe structures. Every example
MUST remain structurally and semantically valid and MUST be listed in the
conformance manifest.

Contributors adding a feature to the recipe model MUST add or extend a complete
example when the feature affects how a real recipe is authored, imported,
rendered, or exchanged. Minimal valid and invalid cases belong under `tests/`.

- `chocolate-chip-cookies.recipe.json` demonstrates ordered person and
  organization authorship, an authoritative author URL, United States culinary
  measures, a sum quantity, instruction references, three independent yields,
  per-serving nutrition, and dietary claims and allergen declarations including
  a claim scoped to a variant.
- `australian-scones.recipe.json` demonstrates an Australian source locale and
  region-specific cup and tablespoon units.
- `sourdough.recipe.json` demonstrates metric mass, ranges, approximation, an
  opaque quantity, untitled instruction sections, and a coarse time summary
  without timing assertions.
- `complex-layer-cake.recipe.json` demonstrates several independent ingredient
  and instruction sections, alternative quantities, count units, an ingredient
  made by another recipe, and an extension that must survive round trips.
- `savory-hand-pies.recipe.json` demonstrates pastry, filling, and finish
  components whose instruction structure does not mirror the ingredients, plus
  multiple timing assertions attached to one step and shared across steps.
- `vegetable-biryani.recipe.json` demonstrates cross-component assembly and a
  counted spice whose per-item size is a physical length.
- `ramen-bowl.recipe.json` demonstrates an opaque authored measure, per-packet
  package size, and bowl assembly.
- `preserved-lemons.recipe.json` demonstrates a vessel-dependent amount that
  cannot be normalized and an opaque lower-bounded curing assertion.
- `pizza-night.recipe.json` demonstrates mass-based liquid measurement, a
  preserved opaque overnight fermentation between two distinct prep timings, a
  container size, and ingredient reuse.
- `holiday-punch.recipe.json` keeps an ambiguous Canadian `cup` unassigned and
  records the bottle size separately.
- `roast-chicken.recipe.json` demonstrates per-item mass, staged oven
  temperatures, a labeled internal-purpose target, ranged and approximate timing
  assertions, and distinct dry-brine and rest semantics.
- `microwave-chocolate-sauce.recipe.json` demonstrates a source-rated half-power
  heating range whose following standing interval remains separate.
- `mint-tea.recipe.json` and `mint-tea-english.recipe.json` are an Arabic recipe
  and its English translation. Each names the other by recipe ID; the
  translation splits a step and adds a note, and the Arabic text carries Latin
  unit abbreviations and a Latin tea name.
- `tempered-chocolate.recipe.json` demonstrates ordered temperature ranges that
  remain invariant under recipe scaling.
- `berry-granita.recipe.json` demonstrates a valid negative temperature.
- `vietnamese-pickles.recipe.json` demonstrates non-English Unicode content,
  metric quantities, localized section structure, and localized opaque timing.
- `creme-anglaise.recipe.json` demonstrates an ingredient temperature,
  approximate yield, a cooking range, and a partial assertion list with no
  authored total, showing that assertions need not be complete.
- `../tests/packages/valid-with-asset/recipe.json`, carried by the deterministic
  valid package fixture, demonstrates one image used as a recipe-level primary
  image and as supporting step imagery without duplicating the asset, and the
  provenance of that image.
