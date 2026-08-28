# Expansion plan: the published declarations this tool does not read

Written 2026-08-27. Owner: Chelsea Kelly-Reif. Horizon: two to three years.
Review cadence: per release, and whenever the vendored snapshot is refreshed.

This plan covers one subject: the declarations already sitting in
`src/ctdl_validate/vendor/` that no check reads. It proposes no new source, no
new network access and no new dependency. Every phase below is grounded in a
file this repository already vendors, hashes and pins, or is listed as blocked
with the thing that blocks it named.

The README states the scope this plan expands, under
[Scope, honestly](../README.md#scope-honestly):

> Not covered in v0, deliberately:
>
> - Required-property checking (the Registry's Minimum Data and Currency
>   Policy). v0 checks what is present, not what is missing.
> - Concept scheme membership (`meta:targetScheme` declarations exist for 45
>   properties and would support a real check; cut for scope).
> - Literal datatype validation beyond the CTID (dates, durations, language
>   map shapes).
> - Vocabularies beyond CTDL and CTDL-ASN (QData and other profiles).

Three of those four are the subject of Phases 2, 3 and 6. "Cut for scope" is a
deferral with a reason that has since expired; it is not a refusal, and it is
the difference between this plan and the section below it.

## The measured gap

Five checks read the vendored encodings today. They read
`schema:domainIncludes`, `schema:rangeIncludes`, `rdfs:subClassOf`,
`owl:inverseOf`, and the contexts' `{"@type": "@id"}` coercions. Counted from
the same four files, this is what they do not read:

| Declaration | Published | Read by a check today |
|---|---|---|
| Properties declaring `meta:targetScheme` | 48 | 0 |
| Concept schemes | 36 | 0 |
| Concepts declaring `skos:inScheme` | 456 | 0 |
| Context datatype coercions | 87 | 0 |
| Context `{"@container": "@language"}` declarations | 80 | 0 |
| Terms declaring `vs:term_status` | 1153 | 0 |

`tests/test_expansion_plan.py` recomputes every number in that table from the
vendored files and fails the build if the table drifts from them. The counts
are of declarations, not of defects: a declaration nothing reads is an
opportunity, not a bug, and none of these six rows says a payload is wrong.

The README's scope section says 45 where this table says 48, and the README is
right about what it counts. CTDL declares `meta:targetScheme` on 45
properties; CTDL-ASN declares it on 6; three of those 6 --
`ceterms:industryType`, `ceterms:instructionalProgramType` and
`ceterms:occupationType` -- are re-declarations of the same `ceterms:`
properties, and both encodings name the same scheme for each. So the union is
48 distinct properties carried by 51 declaration nodes, and no phase here
needs to correct the README. The three re-declarations agreeing exactly is
worth stating because Phase 2 has to load both encodings and must not treat a
property declared twice as a conflict when the two declarations say the same
thing.

### What that surface looks like in published documents

Measured 2026-08-27 against the local 1,200-document cache of the
[2026-08-21 Registry survey](findings/2026-08-21-registry-survey-at-scale.md),
re-read offline from that run's cache:

- 1,101 of the 1,200 documents use at least one scheme-bound property.
- Those documents carry 4,161 values on scheme-bound properties: 2,907 naming
  a concept the vendored snapshot declares, 1,194 naming an external framework
  by URI (O\*NET occupation pages, IPEDS CIP codes), and 60 alignment objects
  carrying a label with no `ceterms:targetNode` at all.
- Of the 2,907, **zero** fall outside the scheme their property declares.

Those figures are not re-derived in CI, whose checkout does not carry the
cache. They are stated here because they set two of this plan's expectations
in advance, and both are load-bearing:

1. A concept-scheme check will find nothing in the published corpus. That is
   the expected result for documents the Registry has already ingested, and it
   is not a reason to skip the check: the tool exists to be run on payloads
   *before* they are published. It is a reason to say so in the write-up
   rather than to imply a catch rate.
2. The external-framework URIs are the real design problem. `meta:targetScheme`
   names a CTDL scheme, and 1,194 published values on those same properties
   name something else entirely. A check that called those out of scheme would
   report an ERROR against roughly a third of the values it looked at, on
   documents the Registry accepted. Phase 2 has to settle that before it
   settles anything else.

## Phases

Phases 1 through 4 are sequenced. Phases 5 through 7 are blocked, and the
thing blocking each is named rather than scheduled.

### Phase 1: one `@id`, one entity

**Delivers.** A payload that declares the same `@id` on more than one node is
reported, and the report does not depend on which one the parser saw first.

**Why first.** `Graph.by_id` keeps whichever duplicate parsed first and drops
the rest ([#33](https://github.com/ChelseaKR/ctdl-validate/issues/33)). Every
check that resolves an entity by identifier inherits that, so every check this
plan adds would inherit it too. The issue's own words are the reason this is
Phase 1 and not Phase 4: "the ERROR is stable, not correct." A verdict that is
reproducible and wrong is the failure mode this repository's determinism tests
are least able to see, because byte-identical output is exactly what a stable
wrong answer produces.

**Depends on.** Nothing.

**Done when.** A duplicated `@id` produces a finding naming every declaration
site; the finding is order-independent, proven by validating the same entities
in both array orders and asserting identical output; a break-the-gate case
covers it; and no existing fixture changes verdict except where the duplicate
was the defect.

### Phase 2: concept scheme membership

**Delivers.** Check 6. For each of the 48 properties declaring
`meta:targetScheme`, a value naming a concept the snapshot declares is checked
against the scheme the property names.

**The decision this phase turns on.** What to say about the 1,194 published
values naming an external framework. The honest reading of the evidence is that
`meta:targetScheme` constrains values drawn from CTDL's own schemes and says
nothing about a value drawn from somewhere else, because the Registry accepts
both on the same property. So: a concept the snapshot declares, in the wrong
scheme, is a defect the encoding is sufficient to prove. A value the snapshot
does not declare at all is not a defect this tool can decide, and gets the
severity the tool already reserves for that. This gets an ADR, because it
shapes the severity contract.

**Depends on.** Phase 1, for entity identity.

**Done when.** Every scheme-bound property's values are classified; each
classification cites the `meta:targetScheme` and `skos:inScheme` declarations
it rests on; a break-the-gate case moves a concept into the wrong scheme and
asserts it is caught; the 1,200-document corpus is re-validated and the result
published as a findings document, including if the result is nothing; and the
README's scope list moves this line out of "not covered in v0".

### Phase 3: literal datatypes and language-map shape

This was drafted as one phase and is two, with different grounding. Building
it is what showed the difference, and the plan is corrected here rather than
left as written.

#### Phase 3a: language-map shape. Buildable.

**Delivers.** A check over the 80 `{"@container": "@language"}` declarations
in the contexts, 67 of which the schema encodings also declare as properties:
a bare literal where the context declares a language map.

**Why this half is groundable.** The declaration being violated is in the
vendored context itself, and the validator already reads it -- `graph.py`
keeps such a value as the map it is instead of walking it as a nested node
object. The check reports that same reading rather than only relying on it.

**Done when.** Language-map shape is reported at a severity that cannot gate
an exit code, the covered properties are read out of the index rather than
listed by hand, a break-the-gate case exists, and the corpus result is
published including if it is nothing.

#### Phase 3b: literal datatype validation. Blocked.

**Blocked on the same kind of thing as Phases 5 and 6: bytes this repository
does not vendor.** The contexts declare 87 datatype coercions, but nothing in
the four vendored files defines the lexical space of any datatype. Their
complete key set is `@id`, `@type`, `dct:description`, `meta:changeHistory`,
`meta:domainFor`, `meta:hasConcept`, `meta:targetScheme`,
`owl:equivalentClass`, `owl:equivalentProperty`, `owl:inverseOf`,
`rdfs:comment`, `rdfs:label`, `rdfs:subClassOf`, `rdfs:subPropertyOf`,
`schema:domainIncludes`, `schema:rangeIncludes`, `skos:broader`,
`skos:definition`, `skos:hasTopConcept`, `skos:inScheme`, `skos:narrowMatch`,
`skos:narrower`, `skos:prefLabel`, `skos:relatedMatch`, `skos:topConceptOf`,
`vann:usageNote` and `vs:term_status`, plus the contexts' `@container` and
`@type`. No pattern, no format, no lexical constraint.

Writing the grammar of an ISO 8601 date from memory is the rule-from-memory
the first invariant forbids, and it is not a small risk in this instance:
`xsd:date` admits a timezone offset and a negative year, which a regexp
written from recollection reliably gets wrong.

**What would unblock it.** The XML Schema Part 2 datatypes specification
retrieved byte-exact, committed under `src/ctdl_validate/vendor/` with its
SHA-256 in `SOURCES.md` and enforced by `tests/test_vendor_integrity.py`. A
maintainer action at a network connection.

### Phase 4: term status, disclosed

**Delivers.** Check 8. A payload using a term the vendored encoding declares
`vs:unstable` is disclosed, at the severity the tool reserves for a signal
that is not a defect.

**What this phase must not do.** It must not interpret what `vs:unstable`
means beyond the fact of the declaration. The finding says the published
encoding marks this term unstable and cites the encoding; it does not say the
term will be withdrawn, that the Registry will reject it, or that the payload
should change. Any of those would be a rule encoded from memory.

**Depends on.** Nothing structurally; sequenced last of the buildable four
because it is the least likely to change a verdict and the most likely to add
noise, and it should land after the checks that carry weight.

**Done when.** Unstable-term use is reported with the declaration cited; a
stable term produces nothing; the 478 unstable terms are covered by the check
rather than by a list; and the corpus measurement says how much noise this adds
to a real document before it is switched on by default.

### Phase 5: required properties (Minimum Data Policy)

**Blocked.** The rule lives in the Registry's Minimum Data and Currency Policy,
which this repository does not vendor. The vendored snapshot declares nothing
about whether a property is required: its property nodes carry `@type`, `@id`,
`rdfs:label`, `rdfs:comment`, `dct:description`, `vann:usageNote`,
`vs:term_status`, `meta:changeHistory`, `meta:domainFor`, `meta:targetScheme`,
`rdfs:subPropertyOf`, `owl:equivalentProperty`, `owl:inverseOf`,
`schema:domainIncludes` and `schema:rangeIncludes`, and no requiredness term
among them.

**What would unblock it.** A byte-exact retrieval of the published policy,
committed under `src/ctdl_validate/vendor/` with its SHA-256 recorded in
`SOURCES.md` and enforced by `tests/test_vendor_integrity.py`, the same way the
four current sources are held. That is a maintainer action at a network
connection, and it is deliberately not something to approximate: a
requiredness rule transcribed from a reading rather than from bytes is the
rule-from-memory this project's first invariant forbids.

### Phase 6: vocabularies beyond CTDL and CTDL-ASN

**Blocked, for the same reason as Phase 5.** QData is a separate published
encoding at its own URL. The work is not the checking, which the existing
schema loader would largely absorb; the work is vendoring a fifth and sixth
file under the hashing policy. `SOURCES.md` and the loader are already written
to take more than two vocabularies, so this phase is small once the bytes
exist, and impossible before.

### Phase 7: the third release

**Blocked, and not an engineering task.** `docs/ROADMAP.md` states it: `main`
carries a disposition that turned 36 of 120 published documents from failing to
passing, and PyPI does not. Cutting the tag requires the maintainer's signing
key, and `.github/allowed_signers` exists so that no one else's will do. Every
phase above lands in `[Unreleased]` and reaches a user at the maintainer's tag,
not before.

## Refused, and staying refused

Reopening one of these means overturning its reason, not re-proposing the idea.

- **Fetching anything during validation.** README, "Scope, honestly"; enforced
  by `tests/test_offline_guarantee.py`. `--resolve` settles references from
  files the operator already has, and
  [ADR-0004](adr/0004-resolution-is-additive.md) fixes the direction: supplying
  a document can turn a non-answer into an answer and can never turn one into a
  failure. No phase here touches that.
- **A model, anywhere.** [ADR-0003](adr/0003-extraction-as-a-separate-command.md):
  "Coverage would go up sharply, and so would the number of well-formed
  credentials that no page ever claimed."
- **A hand-written crosswalk, or any rule from memory.** Same ADR, and
  `CONTRIBUTING.md`'s first invariant.
- **Deferring the playground's Pyodide download to the first click.** ROADMAP,
  "Why the performance budget is not met". The score would clear and the first
  validation would take tens of seconds with no warning.
- **Raising a severity to make a check look useful.** The severity contract is
  the tool. A check that finds nothing in the published corpus reports that it
  found nothing.

## Sequencing

| Phase | Depends on | Buildable here |
|---|---|---|
| 1. One `@id`, one entity | — | Yes |
| 2. Concept scheme membership | 1 | Yes |
| 3a. Language-map shape | 1 | Yes |
| 3b. Literal datatype validation | vendored XSD datatype bytes | No |
| 4. Term status, disclosed | 1 | Yes |
| 5. Required properties | vendored policy bytes | No |
| 6. Vocabularies beyond CTDL/CTDL-ASN | vendored encoding bytes | No |
| 7. Third release | maintainer signing key | No |
