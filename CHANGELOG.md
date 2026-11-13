# Changelog

Notable changes to the SREF specification, schemas, unit registry, and
conformance corpus. Versions follow [versioning](docs/versioning.md): the format
and the unit registry are versioned separately, and each release lists both.

## 0.5.0

Unreleased. Format 0.5.0, unit registry 0.3.0.

- Add Turkish, Portuguese, Hebrew, Arabic, and Romanian cup and spoon aliases.
- Add the decagram (`mass.decagram`), with `dag`, `dkg`, and `deka` aliases, and
  the hectogram (`mass.hectogram`), with Italian `etto` and Thai `ขีด`.
- Add the Japanese rice measure `合` (`volume.go.jp`).
- Add the 200 mL Greek cup (`volume.cup.gr`). Greek cup words name it and the
  250 mL culinary cup, and Greek spoon words without `της σούπας` or
  `του γλυκού` name the measuring spoons.
- Add Russian spoon and clove abbreviations, Russian and Ukrainian spoon forms
  for fractions (`чайной ложки`), Ukrainian clove forms, the common Thai
  spelling `ช้อนโต้ะ`, the colloquial Arabic spoon spelling `معلقة`, Dutch
  `handje`, the Vietnamese counter `con`, the Chinese bottle counter `瓶`,
  Arabic slice, Indonesian handful, Ukrainian pinch, and Korean measuring-cup
  words, Korean `T` and `t` spoons, and Chinese, Japanese, and Thai counter
  words.
- Add count units for pieces, slices, sticks, stalks, heads, sheets, leaves,
  strips, squares, fillets, cubes, knobs, ears, loaves, wheels, racks, dashes,
  drops, and splashes.
- Add jar, bottle, bag, box, carton, tub, pot, punnet, and envelope containers.
- Add count and container words from each language's standard dictionary for
  Czech, Danish, Finnish, Greek, Hebrew, Hungarian, Indonesian, Norwegian,
  Polish, Romanian, Russian, Swedish, Turkish, Ukrainian, and Vietnamese, such
  as `flaske`, `vartta`, `kapek`, `fej`, `koçan`, and `скибок`.
- Add `pkg`, `pkt`, and `sachet` as English packet aliases, and aliases for the
  new units in the most common recipe languages.
- Ignore a full stop that ends a unit form, so `tbsp.` matches `tbsp`, and drop
  the registered forms that ended in one.
- Add ingredient-line cases for spelled-out numbers, articles, measure
  modifiers, equivalents after the name, and count and container words, which
  read as the new units.

## 0.4.0

Released 2026-09-29. Format 0.4.0, unit registry 0.2.0.

First release.
