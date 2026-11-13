# Changelog

Notable changes to the SREF specification, schemas, unit registry, and
conformance corpus. Versions follow [versioning](docs/versioning.md): the format
and the unit registry are versioned separately, and each release lists both.

## 0.5.0

Released 2026-11-13. Format 0.5.0, unit registry 0.3.0.

### Added

- Add decagrams (`mass.decagram`) and hectograms (`mass.hectogram`), including
  regional forms such as `dkg`, `deka`, `etto`, and `ขีด`.
- Add the Japanese rice measure 合 (`volume.go.jp`).
- Add the 200 mL Greek cup (`volume.cup.gr`), preserving ambiguity with the 250
  mL cup where Greek wording permits either.
- Add count and container units, including slices, sticks, loaves, jars,
  bottles, and bags, with multilingual aliases.
- Add cup and spoon aliases for Turkish, Portuguese, Hebrew, Arabic, Romanian,
  and Greek.
- Add multilingual count and container vocabulary, including regional spellings,
  abbreviations, inflections, and counter words.
- Add ingredient-line conformance cases for written amounts, measure modifiers,
  package sizes, equivalents, and count and container units.

### Changed

- Ignore one trailing period when matching unit forms, so `tbsp.` matches
  `tbsp`. Registry aliases omit the trailing period.

## 0.4.0

Released 2026-09-29. Format 0.4.0, unit registry 0.2.0.

First release.
