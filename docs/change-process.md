# Specification change process

Changes are judged by their effect on recipe meaning over time, not by how much
code they need.

## Core admission

Before a proposal's design is reviewed, decide whether the concept belongs in
core SREF. SREF preserves portable, authored recipe information. It is not a
food ontology, an inference system, an application-state format, a workflow
model, or a list of every property another recipe format has. The proposal must
show that the concept belongs.

### Criteria

A new core semantic normally satisfies all seven:

1. **Portable**: it means the same thing across independent applications and
   formats.
2. **Source-authored**: the recipe author or source supplied it. Application
   state, workflow state, presentation, and a consumer's own interpretation do
   not qualify.
3. **Semantically stable**: SREF can define its meaning and limits without
   relying on application behavior or guesswork.
4. **Multi-consumer utility**: more than one independent consumer benefits from
   a structured form.
5. **Real recurrence**: it appears repeatedly in real recipes and sources.
6. **Core gap**: existing core semantics cannot preserve it adequately.
7. **Extension inadequacy**: leaving it to extensions would cause real,
   recurring loss between implementations.

Each criterion is `satisfied`, `not satisfied`, or `insufficient evidence`.
There is no score, weighting, or occurrence threshold.

### Procedure

- A proposal MUST address each criterion and identify its evidence for criteria
  5 to 7.
- A candidate with inadequate evidence SHOULD be deferred. A candidate MAY stay
  deferred indefinitely, and deferral MUST NOT block a release.
- A useful concept that does not justify core MAY be carried by an extension.
- Admission SHOULD use the smallest semantic that preserves the authored
  information.

A core semantic MUST NOT be justified only by:

- its presence in Schema.org or another vocabulary;
- one application implementing it;
- possible future usefulness;
- the fact that it can be modeled;
- making the schema look complete.

### Text preservation versus typed data

Keeping the author's wording is not the same as preserving the meaning in a form
other implementations can use, and a proposal MUST NOT treat one as the other.
An ingredient marked optional in prose keeps its wording but loses the typed
flag. Conversely, some concepts are served well by text, and for some constructs
text is the defined representation.

Criterion 7 asks what goes wrong when independent implementations each use their
own private extension. A concept can be common and useful and still belong in an
extension. When an extension cannot carry the concept at all, criterion 7 is
satisfied: [section 13](../spec.md#13-extensions) forbids extensions from
relaxing a conformance requirement or from being needed to recover standard
semantics.

Criterion 2 rules out identities and classifications a consumer derives, such as
an ontology term matched to an ingredient name or a category inferred from the
ingredients. When the source itself supplies the identifier, criterion 2 is
satisfied.

### Evidence for criteria 5 to 7

Corpus evidence comes from the
[external corpus loss audit](conformance.md#external-corpus-loss-audit). Cite
occurrence counts, the source families they come from, and example case IDs,
using verdicts from the corpus commit pinned in
`conformance/recipe-corpus.json`.

- Spread across source families matters more than a raw count. State how
  concentrated a count is. Independent publishers within one acquisition family
  count as independent sources.
- Project-authored fixtures show that a concept can be represented, not that it
  recurs. A project-authored recipe carried through an application shows how
  that application behaves. Keep such evidence separate, and count a fixture
  once no matter how many applications it passed through.
- Where no corpus feature records the concept, criterion 5 is
  `insufficient evidence`; the remedy is a new corpus feature.

| Verdict                | What it shows                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `sref_unsupported`     | A core gap: evidence for criterion 6.                                                                             |
| `mapping_unverified`   | A gap in the audit, not the format.                                                                               |
| `accidentally_lost`    | A defect in the corpus's generated target, not a format gap.                                                      |
| `misrepresented`       | A defect in the corpus's generated target, not a format gap.                                                      |
| `upstream_lost`        | The concept was lost before reaching SREF. It shows the concept occurs, but cannot by itself satisfy criterion 7. |
| `exact`                | The construct is present and matches the source.                                                                  |
| `semantics_unverified` | The construct is present; whether it matches the source is unknown.                                               |

Do not present an extraction limit, a source format's own loss, or a corpus
tooling defect as a core gap.

### Dispositions

Every candidate receives one disposition:

- **core**: all seven criteria are satisfied.
- **defer**: the concept could qualify, but evidence is insufficient or its
  semantics cannot yet be defined. A deferral SHOULD name what would resolve it.
- **extension**: the concept is worth preserving, but one or more criteria are
  not satisfied, so it belongs in an extension.

## Change proposal

A proposal that changes normative behavior MUST describe:

- the recipe or interoperability problem;
- representative source material or a synthetic equivalent;
- the semantics that MUST survive a round trip;
- alternatives considered;
- compatibility and migration effects;
- security and resource-limit effects; and
- the schemas, registry entries, examples, and conformance cases affected.

A proposal MUST NOT introduce a standard field solely because one application
stores it internally.

## Required evidence

Every normative change MUST include executable evidence:

- a complete example when the change affects ordinary recipe authorship;
- a minimal valid fixture;
- an invalid fixture for every new rejection rule;
- a round-trip fixture for preservation requirements; and
- package fixtures when archive behavior changes.

A unit-registry change additionally requires an official or primary standards
reference and an ambiguity analysis for its aliases.

## Review criteria

Reviewers MUST determine whether the proposal:

1. preserves authored information;
2. avoids unsupported inference;
3. distinguishes source semantics from projections;
4. has one unambiguous machine representation;
5. can be implemented independently from this repository;
6. defines semantic validation beyond JSON Schema where necessary;
7. has bounded behavior on untrusted input; and
8. follows the compatibility rules in [versioning.md](versioning.md).

Convenience for one implementation does not justify lasting ambiguity in the
format.

## Decision record

An accepted proposal MUST record its rationale with the change and update the
repository artifacts in the same change. Normative rules MUST live in the
specification or a document it incorporates; review discussion is not a
substitute for published requirements.

## Corrections

An objectively inconsistent fixture or editorial error MAY be corrected without
a full design proposal when the correction does not change conforming document
meaning. The change MUST still include a regression check and a clear changelog
entry.
