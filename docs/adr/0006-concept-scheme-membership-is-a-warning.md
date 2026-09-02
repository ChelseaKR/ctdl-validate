# 6. Concept scheme membership: a warning for the wrong scheme, never an error for an unfamiliar term

## Status

Accepted

## Context

The README listed concept scheme membership under "Not covered in v0,
deliberately", with the reason "`meta:targetScheme` declarations exist for 45
properties and would support a real check; cut for scope". That is a deferral
with a capacity reason, not a refusal, and the capacity reason has expired.

Both halves of the check are already vendored. Across the two encodings, 48
distinct properties declare `meta:targetScheme` -- the concept scheme a value
of that property is drawn from -- and 456 concepts declare `skos:inScheme`.
Nothing needs fetching.

What made this worth an ADR is not the mechanism. It is what the published
corpus does on exactly these properties. Measured over the 1,200 documents of
the 2026-08-21 Registry survey, re-read offline from that run's cache, the
values on scheme-bound properties divide as:

| Value | Count | Documents |
|---|---|---|
| A concept the snapshot declares, in a scheme the property names | 2,907 | 1,070 |
| Something the snapshot does not declare, mostly an external framework URI | 1,194 | 500 |
| An alignment object naming its term in words, with no `ceterms:targetNode` | 60 | 22 |
| A concept the snapshot declares, in some **other** scheme | **0** | **0** |

Roughly a quarter of the values on these properties point outside CTDL
altogether: O\*NET occupation pages, IPEDS CIP codes, Census NAICS codes. That
is not abuse. `ceterms:CredentialAlignmentObject` exists to align a resource to
a framework, and the Registry publishes documents that do exactly this.

So the naive reading of `meta:targetScheme` -- "a value of this property must
be a term of this scheme" -- would report an ERROR against 1,194 values in 500
of 1,200 published documents. That is the failure the README's severity
section is written against.

## Decision

Add check 7. Every value on a scheme-bound property falls into exactly one of
four outcomes, and each one is reported or explicitly clean. Nothing is
skipped.

1. **The encoding declares the term, in a scheme the property names.** No
   finding.

2. **The encoding declares the term, in some other scheme.**
   `CONCEPT_OUTSIDE_SCHEME`, **WARNING**. Both declarations are in the
   vendored files, so this is a term from the wrong vocabulary rather than a
   term the tool does not recognise. It is a WARNING and not an ERROR because
   the README defines WARNING as "a cited signal that something is very likely
   wrong, where the rule is not absolute or Registry enforcement of it is not
   documented", and no published Credential Engine document says the Registry
   enforces `meta:targetScheme` on ingest. The evidence supports the finding;
   it does not support the claim that the Registry will reject the document.

3. **The encoding does not declare the term.** `CONCEPT_OUTSIDE_SNAPSHOT`,
   **UNVERIFIABLE**. This is the external-framework case and the
   snapshot-lag case at once, and the tool cannot tell them apart without
   vendoring frameworks it has not vendored. UNVERIFIABLE is the severity this
   tool already reserves for exactly that: never a pass, never a fail, never
   an exit code.

4. **An alignment object with no `ceterms:targetNode`.**
   `CONCEPT_NOT_IDENTIFIED`, **UNVERIFIABLE**. The value states a term by
   label. There is nothing to match against a scheme, and the message says
   what would make it checkable.

## Alternatives considered

**ERROR for the wrong scheme.** The same evidentiary standing as
`RANGE_VIOLATION`, which is an ERROR: two declarations in one vendored file
that contradict each other. Rejected on the second half of the README's
WARNING definition. `schema:rangeIncludes` is a range in the ordinary
RDF-schema sense and the tool has published-document evidence of what the
Registry does with it; `meta:targetScheme` is in Credential Engine's own
`meta:` namespace, and the tool has no evidence of enforcement either way. The
finding is worth reporting and is not worth gating a build on.

**Say nothing about a term the snapshot does not declare.** Rejected. It is
the single most common thing these properties carry, and a check that looked
at a value and then said nothing would be the silent-skip path this tool does
not have. Reporting UNVERIFIABLE is the difference between "checked and fine"
and "not checked", which is the distinction the whole severity contract exists
to preserve.

**Treat an external framework URI as its own severity, below UNVERIFIABLE.**
Rejected as a distinction without a difference: the tool would still be saying
it did not check the value, and a fifth severity would dilute the four the
README defines.

## Consequences

Adding check 7 to the corpus adds 1,190 `CONCEPT_OUTSIDE_SNAPSHOT` and 30
`CONCEPT_NOT_IDENTIFIED` findings across 504 of 1,200 documents, removes none,
and changes no ERROR or WARNING count: 159 ERROR and 42 WARNING before and
after. No document's exit code moves.

`CONCEPT_OUTSIDE_SCHEME` fires zero times on the published corpus. That is the
expected result for documents the Registry has already ingested, and it is
reported here rather than hidden, because a check whose value rests on a catch
rate it does not have would be worse than no check. Its value is in payloads
that have not been published yet, which is what this tool is for.
`tests/test_break_the_gate.py` proves it fires.

The README's scope list loses the concept-scheme line, and
`docs/EXPANSION-PLAN.md`'s "Read by a check today" column moves off zero for
three rows.
