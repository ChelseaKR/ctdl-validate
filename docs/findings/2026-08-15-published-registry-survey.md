# What is already in the Credential Registry: 120 documents, validated

**Run date:** 2026-08-15. **Tool:** `ctdl-validate` at the commit this file
landed on, with the vendored CTDL/CTDL-ASN snapshot retrieved 2026-08-06.
**Harness:** [`tools/registry_survey.py`](../../tools/registry_survey.py).
**Evidence:** [`2026-08-15-published-registry-survey.json`](2026-08-15-published-registry-survey.json).

This validator was built to check a payload before it is published. Until this
run it had never been pointed at a payload that already was. The provider
survey of 2026-08-14 asked what credential providers publish on their own
websites; this one asks what the Registry itself is holding.

> **Followed by** [the 2026-08-21 run](2026-08-21-registry-survey-at-scale.md):
> 1,200 documents, a protocol committed before the draw, and the false-positive
> class this run found already removed from the tool.

## The headline

**Forty ERROR findings across 120 randomly sampled published documents, and
every one of them traces to an inconsistency inside CTDL's own published
schema encoding rather than to a mistake any publisher made.**

That is not the result this run was expecting, and it is a finding about this
tool as much as about the corpus: `ctdl-validate` currently reports 36 of 120
published Registry documents as failing, and on the evidence below it should
not. Both inconsistencies are set out in full, with the declarations they come
from, in [What the errors actually are](#what-the-errors-actually-are).

The second result is about `--resolve`. Validated document by document, the
report is 299 UNVERIFIABLE findings and almost nothing else: 86% of the 348
findings the tool produced were "I cannot see the document this points at."
With the 177
referenced documents fetched and supplied, 294 of those 299 became real
verdicts, and **two ERROR findings appeared that no amount of looking at the
documents individually could have produced.**

## How the sample was drawn, and what it can be said to represent

The read surface is public and needs no key. Verified at run time, by the
harness, through the same fetcher the `extract` command uses:

- `GET https://credentialengineregistry.org/robots.txt` returns **HTTP 404**.
  [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) section 2.3.1.3 treats an
  unavailable robots.txt as permission to proceed, and that branch is recorded
  in the evidence file for this run in the words the fetcher produced.
- `GET /ce-registry/envelopes?page=N&per_page=1` returns HTTP 200 and one
  envelope, with `X-Total` giving the size of the community: **395,878
  envelopes** at run time. Each envelope carries `decoded_resource`, the whole
  CTDL JSON-LD document, in exactly the shape `ctdl-validate <file.json>`
  reads.
- `GET /resources/<ctid>` returns the single entity a reference names.
- The bulk dump, `GET /ce-registry/envelopes/download`, answers **401 Invalid
  token**. That one does need a key. Nothing here uses it.

One page per request with one item per page means page *N* is the *N*th
envelope, so **120 page numbers drawn uniformly at random from 1..395,878
(seed 20260815) is a uniform random sample of the corpus.** Every page drawn
was fetched successfully; none was skipped.

What that sample is and is not:

- It **is** representative of *documents*, within sampling error. At n=120 a
  proportion near 30% carries a 95% interval of roughly ±8 points, so treat
  every percentage below as a rough magnitude, not a measurement.
- It is **not** representative of *publishers*. The Registry is dominated by a
  small number of organizations publishing at volume; a random document is far
  more likely to be theirs. A finding that appears in 30% of documents may be
  one publisher's tooling repeated thirty thousand times, and the
  `creditUnitType` result below almost certainly is.
- Ordering is by date and the corpus grows during a run, so the frame shifted
  by a few envelopes while the sample was being drawn. Immaterial at this
  scale, and stated rather than hidden.

**Politeness.** 299 requests in total, single-threaded, one at a time, with a
2-second minimum interval per host, the `ctdl-validate` product token and a
link to this repository in the User-Agent, and robots.txt checked before the
first request and at every redirect. No concurrency, no retries, no bulk
endpoint.

**What is recorded.** The evidence file holds CTIDs, declared classes, finding
codes and counts, and one example location per code. It holds no name,
description, price, address or contact detail from anybody's record. Registry
documents do carry personal contact details, including individual names,
phone numbers and email addresses; a survey about structural validity has no
business republishing them. The fetched documents are cached locally for
reproducibility and are not committed.

## The counts

Validated one document at a time, as a publisher would:

| Severity | Findings | Codes |
|---|---|---|
| ERROR | 38 | `RANGE_VIOLATION` 38 |
| WARNING | 6 | `CTID_NOT_UUIDV4` 6 |
| INFO | 5 | `INVERSE_ONE_DIRECTION` 5 |
| UNVERIFIABLE | 299 | `REF_OUTSIDE_PAYLOAD` 299 |

3 of 120 documents produced no findings at all. 36 produced at least one
ERROR. Of the other 81, **72 produced only UNVERIFIABLE findings** — which is
to say the tool had nothing to tell them — and 9 produced something short of an
error: 5 a `CTID_NOT_UUIDV4` warning and 4 an `INVERSE_ONE_DIRECTION` note,
each alongside UNVERIFIABLE findings.

Re-validated with the 177 referenced Registry resources fetched and supplied
through `--resolve`:

| Severity | Findings | Codes |
|---|---|---|
| ERROR | 40 | `RANGE_VIOLATION` 40 |
| WARNING | 6 | `CTID_NOT_UUIDV4` 6 |
| INFO | 299 | `REF_RESOLVED_SUPPLIED` 294, `INVERSE_ONE_DIRECTION` 5 |
| UNVERIFIABLE | 5 | `REF_OUTSIDE_PAYLOAD` 5 |

The five that stayed unverifiable are the honest residue and are worth naming:
one is a reference to a provider's own web page
(`https://www.ivytech.edu/...`), and four are references to a CTDL-ASN
vocabulary term (`https://credreg.net/ctdlasn/vocabs/publicationStatus/Published`).
Neither is a Registry resource, so neither was fetched. The harness only
follows references into `credentialengineregistry.org/resources/`, on purpose:
a survey of the Registry should not turn into a crawl of everybody's website.

## What the errors actually are

### 1. Concept-valued properties: CTDL declares two different ranges for the same kind of value

38 of the 40 errors are one pattern, on two properties: `ceterms:creditUnitType`
(36) and `ceterms:creditLevelType` (2). Every occurrence looks like this:

    "ceterms:creditValue": [{
      "@type": "ceterms:ValueProfile",
      "ceterms:creditUnitType": [{
        "@type": "ceterms:CredentialAlignmentObject",
        "ceterms:framework": "https://credreg.net/ctdl/terms/CreditUnit",
        "ceterms:targetNode": "creditUnit:SemesterHour"
      }],
      "schema:value": 1.0
    }]

The tool calls that a `RANGE_VIOLATION`, because the vendored CTDL schema
encoding declares:

- `ceterms:creditUnitType` → `schema:rangeIncludes: [skos:Concept]`, with
  `meta:targetScheme: [ceterms:CreditUnit]`
- `ceterms:CredentialAlignmentObject` → `rdfs:subClassOf: [schema:AlignmentObject]`

`schema:AlignmentObject` is not `skos:Concept`, and CTDL declares no path
between them, so a `CredentialAlignmentObject` standing where a `skos:Concept`
is declared is out of range on the face of the encoding.

The reason to doubt the tool rather than the corpus is inside the same
snapshot. CTDL has **two families of concept-valued properties**: 46
properties declare `schema:rangeIncludes: ceterms:CredentialAlignmentObject`,
and 45 declare `schema:rangeIncludes: skos:Concept`. The families are not
distinguished by anything about the values they hold. The clearest
demonstration is a pair that points at the *same* concept scheme:

| Property | `meta:targetScheme` | `schema:rangeIncludes` |
|---|---|---|
| `ceterms:audienceLevelType` | `ceterms:AudienceLevel` | `ceterms:CredentialAlignmentObject` |
| `ceterms:creditLevelType` | `ceterms:AudienceLevel` | `skos:Concept` |

> **Correction, 2026-08-18.** This paragraph first read "31 declare
> `skos:Concept`". That was the count in `ctdl/schema.json` alone; the
> validator indexes `ctdl/schema.json` and `ctdlasn/schema.json` together, and
> across both the count is **45**. The `CredentialAlignmentObject` figure of 46
> is the same either way. Nothing else in this write-up depends on the number,
> and the run's own measurements below are unaffected — but the sentence
> claimed to be about "the same snapshot" the tool reads, and was not.
> `tests/test_domain_range.py` now derives these figures from the snapshot so
> they cannot drift again.

Both name a term from the CTDL Audience Level vocabulary. Publishers encode
both the same way, as a `CredentialAlignmentObject` carrying `ceterms:framework`
and `ceterms:targetNode`. The two families overlap on three
properties — `ceterms:instructionalProgramType`, `ceterms:specialistSubject`
and `schema:unitText` — which declare both ranges, and 46 plus 45 counts those
three twice.

The `AudienceLevel` pair is not the only case. Measured across the snapshot,
**three concept schemes are named by properties in both families**, and a
fourth is named by one property that declares both ranges at once:

| Concept scheme | `skos:Concept`-ranged | `CredentialAlignmentObject`-ranged |
|---|---|---|
| `ceterms:AudienceLevel` | `ceasn:educationLevelType`, `ceterms:creditLevelType` | `ceterms:audienceLevelType` |
| `ceterms:CostType` | `ceterms:financialAssistanceForType` | `ceterms:directCostType` |
| `ceterms:ScheduleFrequency` | `ceterms:paymentPatternType` | `ceterms:offerFrequencyType`, `ceterms:scheduleFrequencyType` |
| `ceterms:InstructionalProgramClassification` | `ceterms:instructionalProgramType` | `ceterms:instructionalProgramType` (the same property declares **both**) |

So the honest reading is that the `skos:Concept` range on those 31 properties
does not describe how CTDL is actually encoded, and a validator that turns
that into an ERROR is reporting Credential Engine's own dominant encoding as
a defect. **That is a false-positive class in this tool, not 36 broken
documents,** and it is the single most consequential thing this run found.
This repository already has the right machinery for it: `RANGE_DOCS_CONFLICT`
(INFO), the disposition used for the `ceasn:isChildOf` conflict, exists to
report exactly this shape. It has not been applied here, deliberately: this
write-up establishes the evidence, and changing the severity is a spec ruling
that belongs in its own change with its own citations.

> **Resolved, 2026-08-18.** That change landed. A new code,
> `CONCEPT_RANGE_CONFLICT` (INFO), now covers the 20 properties that declare
> both `skos:Concept` and a `meta:targetScheme` — the properties for which the
> evidence above holds — and only those. A `skos:Concept` range with no
> `meta:targetScheme` (`skos:broader`, `ceterms:classification`) is ordinary
> SKOS and remains a `RANGE_VIOLATION` / ERROR, as does any other out-of-range
> class on a scheme-bound property.
>
> **Measured on this same corpus**, re-validated offline from this run's cache
> with no network access:
>
> | | before | after |
> |---|---|---|
> | Documents with >= 1 ERROR (alone) | 36 / 120 | **0 / 120** |
> | Documents with >= 1 ERROR (`--resolve`) | 36 / 120 | **1 / 120** |
> | ERROR findings (alone) | 38 | **0** |
> | ERROR findings (`--resolve`) | 40 | **2** |
> | `CONCEPT_RANGE_CONFLICT` (INFO) | — | 38 |
>
> The 2 surviving errors are the `ceterms:TransferValueProfile` version
> relations in section 2 below, on `ce-5f2b7ce4-6952-43aa-89fa-bcb06d67313f`,
> which are the ones this survey judged real. Every other finding, at every
> severity, is unchanged across all 120 documents. The reclassified findings
> are `ceterms:creditUnitType` (36) and `ceterms:creditLevelType` (2), which is
> the whole of what section 1 predicted and nothing besides.
>
> What is and is not gated: the re-run is reproducible with
> `tools/registry_survey.py --from-dir` against this run's cache, and that
> cache is gitignored, so CI cannot re-run it. What CI does gate, since
> 2026-08-21, is the table itself: the re-run's evidence is committed as
> [`2026-08-15-published-registry-survey.revalidated-2026-08-21.json`](2026-08-15-published-registry-survey.revalidated-2026-08-21.json),
> and `tests/test_findings_evidence.py` recomputes every cell above from the
> two evidence files and checks, document by document, that the only change
> between them is `RANGE_VIOLATION` becoming `CONCEPT_RANGE_CONFLICT`. CI also
> gates the mechanism — which properties the disposition covers, that it
> covers them only when `meta:targetScheme` is declared, and that the
> declarations it rests on are still in the vendored snapshot — in
> `tests/test_domain_range.py`.

### 2. Version relations whose domain includes a class their range excludes

The remaining two errors appeared **only** after `--resolve`, and they are
real. `ce-5f2b7ce4-6952-43aa-89fa-bcb06d67313f` is a
`ceterms:TransferValueProfile` whose `ceterms:latestVersion` and
`ceterms:nextVersion` both point at
`ce-f565ae5e-3944-4a40-937b-93b80cf0a0ad`, which is also a
`ceterms:TransferValueProfile`. Checked by hand against both documents.

The schema encoding declares, for `ceterms:latestVersion`,
`ceterms:nextVersion` and `ceterms:previousVersion` alike:

- `schema:domainIncludes` **includes** `ceterms:TransferValueProfile`
- `schema:rangeIncludes` **excludes** `ceterms:TransferValueProfile`

A versioning relation that a class is allowed to carry but not allowed to
point at another instance of that same class cannot be used correctly by that
class at all. The publisher did the only sensible thing. The declaration is
what is inconsistent.

This one is the argument for `--resolve` in a single example. The reference is
a bare Registry URI; nothing about the referencing document says what class it
points at. Document by document, this is an UNVERIFIABLE and stays one
forever. One extra fetch turns it into a finding about the specification.

### 3. Six CTIDs are not UUID v4 (WARNING, and the severity was right)

Five percent of the sampled CTIDs match the 39-character shape but not the
published grammar's "a standard UUID v4":

| CTID | UUID version nibble | Variant nibble |
|---|---|---|
| `ce-1090a656-b71c-11ef-8f5a-005056bdd76e` | 1 (time-based) | 8, RFC 4122 |
| `ce-474996b6-b71c-11ef-8f5a-005056bdd76e` | 1 (time-based) | 8, RFC 4122 |
| `ce-6e17a972-de8f-79c6-1908-7190bac377ed` | 7 | 1, not RFC 4122 |
| `ce-3cca4521-90ea-d726-8b22-9ec2f3b99d79` | d, not a UUID version | 8, RFC 4122 |
| `ce-b9e034b1-7ecd-d89d-4861-fddad640f85d` | d, not a UUID version | 4, not RFC 4122 |
| `ce-14b10f64-0147-f078-c39b-2c50cc385730` | f, not a UUID version | c, not RFC 4122 |

Two are plain UUID v1s, complete with what looks like a MAC address in the
node field, published twice from the same generator. Three carry version
nibbles that name no UUID version at all, which means they are almost
certainly random hex in UUID shape rather than UUIDs.

The tool reports these as WARNING rather than ERROR, on the stated grounds
that Registry enforcement of the version bits is not documented. The Registry
accepted and is serving all six, so that call was correct, and this is the
first evidence for it.

## What this changes

1. **A false-positive class in this tool is now documented with evidence.**
   See item 1. Nobody should ship a CTDL gate on `RANGE_VIOLATION` alone until
   the concept-range question is settled. *(Settled 2026-08-18: see the
   resolution note in item 1. A gate on `RANGE_VIOLATION` is now safe against
   this corpus — it fires twice in 120 documents, on the one case this survey
   checked by hand and judged real.)*
2. **`--resolve` earns its place empirically.** 294 of 299 non-answers became
   answers, and two errors existed that were unreachable without it. Before
   the flag, a survey of this corpus could only have reported that it could
   not tell.
3. **Nothing was reported to anyone.** No issue, pull request, or message was
   filed with Credential Engine or with any publisher on the strength of this
   run. It describes documents and declarations, not the organizations behind
   them, and the two findings that matter are about the specification, which
   is Credential Engine's to correct if they agree.
4. **v0's deliberate omissions are still the right ones.** Required-property
   checking, concept-scheme membership and literal datatype validation were
   all cut for scope. This corpus is exactly where they would pay, and the
   `meta:targetScheme` declarations that item 1 rests on are the same ones a
   concept-scheme check would use.

## Reproducing it

    uv run python tools/registry_survey.py --sample 120 --seed 20260815 \
        --resolve-cap 250 --cache .registry-cache \
        --out docs/findings/2026-08-15-published-registry-survey.json

The same seed draws the same page numbers. Add `--from-dir` to re-run the
analysis against the cache without touching the network. The cache is
gitignored; the evidence file is not.
