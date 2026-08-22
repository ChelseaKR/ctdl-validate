# What is already in the Credential Registry: 1,200 documents, validated

**Draw date:** 2026-08-21. **Tool:** `ctdl-validate` at the commit this file
landed on, with the vendored CTDL/CTDL-ASN snapshot retrieved 2026-08-06.
**Harness:** [`tools/registry_survey.py`](../../tools/registry_survey.py).
**Evidence:** [`2026-08-21-registry-survey-at-scale.json`](2026-08-21-registry-survey-at-scale.json).

The [2026-08-15 survey](2026-08-15-published-registry-survey.md) validated 120
published documents and found that every ERROR it raised traced to CTDL's own
schema encoding. That finding changed the tool. This run asks the next
question at ten times the scale, with the false-positive class removed: what
does the validator say about the published corpus now, and how much of what it
says is an answer rather than "I cannot see the document this points at"?

## Protocol, fixed before the draw

Everything in this section was written and committed before the first page was
fetched. The results sections below were written afterwards and do not alter
it.

**Frame.** `GET https://credentialengineregistry.org/ce-registry/envelopes?page=N&per_page=1`,
for N in 1..`X-Total`, where `X-Total` is the response header read at draw
time. One item per page makes page N the Nth envelope, so a uniform draw of
page numbers is a uniform draw of envelopes. The endpoint ignores
`resource_type` and `envelope_ctdl_type` query parameters — the same `X-Total`
comes back with or without them, checked 2026-08-21 — so there is **no keyless
per-type frame and therefore no stratified draw.** The per-type breakdown below
is reported from each envelope's own `envelope_ctdl_type` label after the
fact, and a type with fewer than 20 documents in the sample is listed but not
interpreted.

**Draw.** 1,200 page numbers: `random.Random(20260821).sample(range(1, X-Total + 1), 1200)`,
sorted. The seed is the date. The evidence file records `X-Total`, the seed,
and every page number, so the draw is recomputable without the network, and
`tests/test_findings_evidence.py` recomputes it. *(Amended after the draw,
2026-08-21: the tests for this run were given their own module,
`tests/test_findings_registry_at_scale.py`, to keep the 2026-08-15 tests
untouched. Nothing else in this section has changed since it was committed.)*

**Every drawn page is published.** Each of the 1,200 appears in the evidence
exactly once: as a document row, or as an exclusion with one of six reasons
fixed in advance in the harness (`EXCLUSION_REASONS`): `fetch-failed`,
`empty-page`, `not-resource-data`, `no-document`, `duplicate-ctid`,
`unreadable`. No retries. A page that fails is a row that says so.

**Two passes.** Every document is validated alone, as a publisher would run
the tool, and then with `--resolve` supplied every document its references
name. Resolution is one hop and follows only references into
`credentialengineregistry.org/resources/`; a reference to a credreg.net
vocabulary term, to some other path on the Registry host, or to anybody's own
website is not fetched and is counted by kind, never by name. There is no cap
on the number of neighbours fetched. A neighbour the validator cannot read is
recorded by CTID and reason and left out of the supplied set rather than
allowed to abort the pass.

**What is recorded.** Per document: the page number, the CTID, the Registry's
type label, an opaque publisher label (`P001`, `P002`, … in order of first
appearance, so concentration can be measured without recording identity), the
entity count, the declared classes, finding codes with counts and one example
location per code for each pass, the Registry resources it referenced, and the
kinds of reference left unsettled. Every recorded example value passes an
allow-list — a JSON pointer, a CTID, a blank node id, a Registry or credreg.net
IRI, a prefixed term — and anything else is replaced by its length. No name,
description, price, address, contact detail, or third-party URL. The fetched
documents are cached locally and are not committed.

**What will be published, whatever it shows.** Headline counts for both
passes; per-code and per-severity totals; the per-type table; publisher
concentration; every document carrying an ERROR, named by CTID and JSON
pointer; every exclusion, named by page and reason; the unsettled residue by
kind; and the change against the 120-document run, which is comparable because
that run's cache has been re-validated by the same tool version
([`2026-08-15-published-registry-survey.revalidated-2026-08-21.json`](2026-08-15-published-registry-survey.revalidated-2026-08-21.json)).
Every number in those tables is recomputed from the evidence JSON by
`tests/test_findings_evidence.py` *(see the amendment above: the module is
`tests/test_findings_registry_at_scale.py`)*.

**Hand verification.** Every ERROR in the resolved pass is checked against the
cached source bytes of the document and, where the finding depends on it, of
the neighbour, before it is published. A finding that does not hold against
the bytes is reported as a defect in this tool, not in the document.

**Politeness.** One process, one request at a time, a 2-second minimum
interval, the `ctdl-validate` product token and a link to this repository in
the User-Agent, robots.txt checked before the first request and at every
redirect, no bulk endpoint, no API key. Nothing is filed with anyone on the
strength of this run.

**Conformance.** A document with no findings has passed this tool's five
structural checks and nothing else. It has not been shown to conform to CTDL,
to the Registry's Minimum Data Policy, or to anything this tool does not
check. No percentage here is a population estimate of anything but the
documents the tool read.

## How the draw went

{{ACCESS}}

## The headline

{{HEADLINE_PROSE}}

{{HEADLINE_TABLE}}

By finding code:

{{CODES_TABLE}}

## By Registry type

{{TYPES_PROSE}}

{{TYPES_TABLE}}

## Every ERROR, named and checked against the bytes

{{ERRORS_PROSE}}

{{ERRORS_TABLE}}

{{ERRORS_ANALYSIS}}

## What stayed unsettled after `--resolve`

{{RESIDUE_PROSE}}

{{RESIDUE_TABLE}}

## Who published what

{{PUBLISHERS_PROSE}}

## Against the 120-document run

{{DELTA_PROSE}}

{{DELTA_TABLE}}

## Exclusions

{{EXCLUSIONS}}

## What this changes

{{CHANGES}}

## Reproducing it

    uv run python tools/registry_survey.py --sample 1200 --seed 20260821 \
        --resolve-cap 100000 --cache .registry-cache-2026-08-21 \
        --out docs/findings/2026-08-21-registry-survey-at-scale.json

The same seed draws the same page numbers against the same `X-Total`; the
corpus moves, so a fresh draw against today's `X-Total` is a different sample
and is meant to be. Add `--from-dir` to re-derive this evidence file from the
cache, byte for byte, with no network: the draw, the robots outcome, the
request count and every fetch failure are read back from
`<cache>/provenance.json`. The cache is gitignored; the evidence file is not.
