# Bundle fixtures

The `.srefbundle` files in this directory are deterministic conformance
fixtures. Run `python3 conformance/build_archive_fixtures.py` from the
repository root after changing the packages they are built from, and `--check`
to rebuild in an isolated directory and compare.

Every bundle here is built from packages in `../packages/`, so a change to a
package fixture changes the bundles that carry it.

- `valid.srefbundle` carries two members in a stated order: the package with
  assets and an asset-free package. Its first member ID begins with a digit.
  Extracting either member gives a usable `.sref`.
- `manifest-duplicate-format.srefbundle` repeats the bundle format member.
- `manifest-duplicate-member-id.srefbundle` repeats an identity-bearing member
  ID inside a recipe entry.
- `manifest-trailing-value.srefbundle` appends a second JSON value after the
  complete manifest.
- `missing-member.srefbundle` declares a member the archive does not carry.
- `undeclared-member.srefbundle` carries a package below `recipes/` that the
  manifest does not declare.
- `undeclared-root-entry.srefbundle` carries a root file that is not the
  manifest.
- `member-digest-mismatch.srefbundle` alters a member's bytes without changing
  its length.
- `member-size-mismatch.srefbundle` lengthens a member.
- `duplicate-recipe-id.srefbundle` validly carries two different packages whose
  recipe-local IDs are the same.
- `missing-member-id.srefbundle` omits the required bundle-local identity from
  one manifest entry.
- `duplicate-member-id.srefbundle` declares one bundle-local member ID twice.
- `member-path-mismatch.srefbundle` names a member by application convention
  instead of by its bundle-local member ID.
- `recipe-id-disagreement.srefbundle` carries a member that verifies against its
  digest and holds a different recipe than the manifest claims.
- `invalid-bundle-member-package.srefbundle` carries a member whose digest is
  correct and whose package is incomplete, which is why verifying a member is
  not the same as validating it.
- `empty-bundle.srefbundle` declares no recipes.
- `bundle-manifest-timestamp.srefbundle` adds a prohibited generation timestamp,
  introducing container variation unrelated to recipe content.
- `missing-bundle-manifest.srefbundle` omits the manifest.
- `unsafe-member-path.srefbundle` names a member outside the archive root.
- `not-a-zip.srefbundle` verifies that malformed archive bytes fail safely.

The builder fixes member timestamps, ordering, mode bits, and compression, and
stores members rather than deflating them. Conformance still depends on bundle
meaning, not byte identity.
