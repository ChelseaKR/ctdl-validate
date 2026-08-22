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

`X-Total` was **395,847** envelopes when the draw was made, so the sample is
1,200 of 395,847 — a little under a third of one percent. `robots.txt` answered
HTTP 404 again at run time, which RFC 9309 section 2.3.1.3 treats as permission
to proceed, and that outcome is recorded in the evidence rather than assumed
from the earlier check.

**Nothing was lost.** All 1,200 drawn pages were fetched, **none failed**, and
**none were excluded** — every one carried a `resource_data` envelope with a
CTID and a `decoded_resource`, no two drew the same CTID, and the validator
read all 1,200. The six exclusion reasons fixed in advance went unused.

**The resolve hop.** The 1,200 documents referenced **1,660** distinct
`credentialengineregistry.org/resources/` URIs. **1,659** were fetched and
**one** answered HTTP 404, leaving **zero** referenced documents neither
fetched nor accounted for. All 1,659 parsed, so none was rejected from the
supplied set; the second pass had 1,659 documents and 1,659 entities in hand.

**Requests, and a counter that was wrong.** The cache the analysis reads cannot
have been built by fewer than **2,861** requests: 1,200 envelope pages, 1,659
neighbour documents, the one neighbour that answered 404, and one probe for
`X-Total`. The harness's own counter recorded **1,770**, and that discrepancy
is the more useful finding. The draw was interrupted partway through and
resumed; the counter was banked only at the end of a phase, so the interrupted
run carried its whole tally out with it. A count that a resume can lose is not
a measurement. The harness now banks the tally after every request, and the
evidence file publishes both numbers side by side — `access.requests.recorded`
and `access.requests.implied_by_the_cache` — rather than the one that reads
better. Every number elsewhere in this write-up is derived from the cache and
the sample, not from that counter.

The resumed run needed no further requests: the cache was already complete, so
the pass that produced this evidence file made zero. The 2-second minimum
interval was never shortened, no `Crawl-delay` was published, and nothing in
the run was rate-limited — the single 404 is a document that is not there, not
a refusal.

## The headline

Both passes read the same 1,200 documents. **94** of them (8%) produced no
finding of any kind, and **28** (2%) carry at least one ERROR. The difference
`--resolve` makes is the whole right-hand column: supplying the 1,659
neighbours converted **3,171 of 3,326** UNVERIFIABLE findings (95%) into real
verdicts, and left 155. Document by document, 1,106 of the 1,200 had at least
one reference the tool could not see; with the neighbours in hand, 33 did.

It converted them into agreement. Supplying 1,659 other people's documents
produced **no new ERROR at all** — the ERROR count is identical in both
columns — because every ERROR in this corpus is either a domain violation,
which needs no neighbour to judge, or a blank-node reference, which no
neighbour can ever settle. That is the outcome ADR 0004 predicted and did not
guarantee: resolution settled unknowns without manufacturing failures.

| Measure | Alone | With `--resolve` |
|---|---|---|
| Documents validated | 1,200 | 1,200 |
| Documents with no findings | 94 | 94 |
| Documents with at least one ERROR | 28 | 28 |
| ERROR findings | 159 | 159 |
| WARNING findings | 42 | 42 |
| INFO findings | 385 | 3,598 |
| UNVERIFIABLE findings | 3,326 | 155 |

By finding code:

| Code | Severity | Alone | With `--resolve` |
|---|---|---|---|
| `CONCEPT_RANGE_CONFLICT` | INFO | 335 | 335 |
| `CTID_NOT_UUIDV4` | WARNING | 42 | 42 |
| `DOMAIN_VIOLATION` | ERROR | 137 | 137 |
| `INVERSE_ONE_DIRECTION` | INFO | 31 | 31 |
| `REF_OUTSIDE_PAYLOAD` | UNVERIFIABLE | 3,326 | 155 |
| `REF_RESOLVED_SUPPLIED` | INFO | 0 | 3,171 |
| `REF_UNRESOLVED_BNODE` | ERROR | 22 | 22 |
| `VERSION_RANGE_CONFLICT` | INFO | 19 | 61 |

`RANGE_VIOLATION` is absent from both columns. Across 1,200 published
documents and 1,659 supplied neighbours, this tool found **no reference whose
target was of a class the property's declared range excludes** that survived
hand-checking — see the ERROR section, where 108 of them did not.

## By Registry type

The draw is uniform over envelopes, not over types, so this table describes
what the corpus is made of rather than what any type is like in general.
Forty-four distinct `envelope_ctdl_type` labels appeared; the sixteen with at
least 20 documents are interpreted, and the rest are pooled. Columns are the
resolved pass.

| Registry type | Documents | No findings | With an ERROR | UNVERIFIABLE left |
|---|---|---|---|---|
| `ceterms:Task` | 150 | 0 | 0 | 0 |
| `ceterms:Course` | 128 | 0 | 5 | 0 |
| `ceterms:Certificate` | 121 | 0 | 0 | 0 |
| `ceterms:CredentialOrganization` | 107 | 94 | 0 | 0 |
| `ceterms:LearningProgram` | 79 | 0 | 0 | 0 |
| `ceterms:TransferValueProfile` | 74 | 0 | 22 | 0 |
| `ceterms:LearningOpportunityProfile` | 63 | 0 | 1 | 0 |
| `qdata:DataSetProfile` | 63 | 0 | 0 | 0 |
| `ceterms:AssociateDegree` | 61 | 0 | 0 | 0 |
| `ceterms:BachelorDegree` | 59 | 0 | 0 | 0 |
| `ceasn:CompetencyFramework` | 35 | 0 | 0 | 149 |
| `ceterms:MasterDegree` | 29 | 0 | 0 | 0 |
| `ceterms:Certification` | 28 | 0 | 0 | 0 |
| `ceterms:License` | 28 | 0 | 0 | 1 |
| `ceterms:CertificateOfCompletion` | 27 | 0 | 0 | 0 |
| `ceterms:AccreditAction` | 26 | 0 | 0 | 0 |
| all other types (28) | 122 | 0 | 0 | 5 |

Two columns are almost entirely one row each. **Every one of the 94 documents
with no findings is a `ceterms:CredentialOrganization`** — 94 of the 107 drawn.
Organizations describe themselves with literals and reference little, so there
is less for a structural checker to have an opinion about; this is a fact about
what the checks can reach, not a quality ranking. Likewise **149 of the 155
references still unsettled after `--resolve` belong to the 35 competency
frameworks**, which point at credreg.net vocabulary terms and at alignment
targets on other people's websites, neither of which this hop follows.

## Every ERROR, named and checked against the bytes

The protocol committed to checking every ERROR against the cached source bytes
before publishing it, and to reporting any that did not hold as a defect in
this tool. **That is what happened.** The resolved pass first raised **267
ERROR findings across 39 documents**. Hand-checking each one against the bytes
and against the schema declaration it cites found that **108 of them, in 11
documents, were this tool's fault**, in two classes:

- **47 findings, one document.** `ceterms:hasMember` declares exactly one
  range term, `rdfs:Resource`. RDF Schema 1.1 section 3.1 defines that as "the
  class of everything", so the declaration excludes nothing — but no CTDL class
  reaches `rdfs:Resource` by `rdfs:subClassOf`, so matching a target's classes
  against it rejected *every* entity instead of accepting every entity. One
  collection listing 47 licences was reported as 47 range violations. The same
  inversion applied to `ceterms:isSimilarTo` and `owl:sameAs`.
- **61 findings, 32 documents.** `ceterms:latestVersion`, `ceterms:nextVersion`
  and `ceterms:previousVersion` each declare a `schema:rangeIncludes` that is a
  strict subset of their own `schema:domainIncludes`, dropping the same six
  classes from all three: `ceasn:Competency`, `ceasn:CompetencyFramework`,
  `ceasn:Rubric`, `ceterms:Collection`, `ceterms:Pathway` and
  `ceterms:TransferValueProfile`. So CTDL says a `TransferValueProfile` may
  *have* a previous version while saying that version may not *be* a
  `TransferValueProfile`. Thirty-two transfer value profiles versioned
  themselves the only way the vocabulary leaves open, and were told they were
  wrong.

Both are now dispositions rather than errors: the first raises nothing at all,
the second raises `VERSION_RANGE_CONFLICT` at INFO, which is where the 61
findings in the code table come from. Both fixes are narrow, both are tested
against the snapshot they rest on, and both tests fail if Credential Engine
changes the declaration — at which point the disposition should be revisited
rather than silently kept.

**The second fix overturns a decision this project made deliberately, and the
grounds matter.** The 2026-08-15 survey found the same version-property
asymmetry in a single document, wrote it down as conflict 5, and chose to keep
raising an ERROR on the stated grounds that "one publisher's usage is not
enough to overturn a declaration". Scaling up did **not** answer that
objection. All 32 documents are from **one publisher** — the same one — and of
the 74 transfer value profiles drawn, only that publisher's 32 use a version
property at all. In the whole corpus of 2,859 documents fetched for this run,
exactly two publishers use any of the three version properties. So the
frequency argument that carries `CONCEPT_RANGE_CONFLICT`, where the Registry's
dominant encoding contradicts the declaration, is **not available here** and
is not being made.

What changed is the argument, not the count. The declaration is incoherent on
its own terms: the range of all three properties is a strict subset of their
own domain, and for the six dropped classes the two halves cannot both be
honoured in any way that means anything. A `TransferValueProfile` may have a
previous version, says the domain; that version may be any of 55 classes, none
of which is `TransferValueProfile`, says the range. Every option the range
leaves open makes a transfer value profile's earlier version a credential.
Either the domain wrongly admits these six classes or the range wrongly
excludes them — one of the two is wrong regardless of what anybody publishes,
and a document that picked the only usable reading is not the thing to report.
An ERROR means "fix this before publishing", and there is nothing here to fix
it to. That is why it is INFO and why the message says which decision the tool
is declining to make rather than pretending the question is settled.

That leaves **159 ERROR findings in 28 documents**, each checked against the
bytes and each standing. The count column is per document and per code; the
property and pointer name one example of that code in that document.

| Document (CTID) | Code | Example property | Example location | Findings |
|---|---|---|---|---|
| `ce-112e13c8-91ed-4e1f-b189-d112161270be` | `DOMAIN_VIOLATION` | `ceterms:framework` | `$.@graph[0].ceterms:teaches[0]` | 44 |
| `ce-42dbf192-24a2-497c-9e7c-ed88e837572d` | `DOMAIN_VIOLATION` | `ceterms:framework` | `$.@graph[0].ceterms:teaches[0]` | 32 |
| `ce-45d1f065-f65b-4372-8b78-d0565c86e74d` | `DOMAIN_VIOLATION` | `ceterms:framework` | `$.@graph[0].ceterms:teaches[0]` | 28 |
| `ce-472cac79-4599-4261-a40a-7b9d2d7d8965` | `DOMAIN_VIOLATION` | `ceterms:framework` | `$.@graph[0].ceterms:teaches[0]` | 20 |
| `ce-f2bf1ed1-0f8d-46d8-90c5-3827841923e8` | `DOMAIN_VIOLATION` | `ceterms:framework` | `$.@graph[0].ceterms:teaches[0]` | 12 |
| `ce-58c1723d-01d1-4636-90de-08c97f272320` | `DOMAIN_VIOLATION` | `qdata:relevantDataSet` | `$.@graph[0].ceterms:aggregateData[0]` | 1 |
| `ce-02c1f6af-cf0f-4a39-9138-c2a6c4a48339` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:dad498af-fb57-03a3-c89f-d3c9d3c1031d` | 1 |
| `ce-03155d72-17e2-4dc5-a809-6b388e1a81c3` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:8d3fa54d-eec3-413d-cc02-b37a725ac5c7` | 1 |
| `ce-0b032255-5f55-40f4-bb1c-9790a97ece7b` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:f3660390-195b-0173-9b02-36462dab7864` | 1 |
| `ce-195526f5-904b-437a-9966-008154148d49` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:3d90c57c-e986-5cbe-6b5c-4217ce9fe00f` | 1 |
| `ce-2e4f495c-7ee0-49b4-b526-adf329b81612` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:70a5fec9-1dd7-4ac6-0c59-8a135bac600b` | 1 |
| `ce-340cba36-8672-41b6-a279-5620d6295d6c` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:7df40def-4eff-6538-1c54-61fb1f156af1` | 1 |
| `ce-3fe27180-3928-4ce2-9a09-c5fccde090e1` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:14c742b0-f927-5ebc-7c5a-4da10296cfa0` | 1 |
| `ce-46ba1356-597e-4abc-86d4-dc511f0795cc` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:d7b1cf60-1ac8-d0c8-779d-1a16eec83d3a` | 1 |
| `ce-47602f69-b340-4714-92a6-c03c8e9075bc` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:d82225af-a2c7-462b-d3f0-88c7fcae1226` | 1 |
| `ce-500e1760-e561-48fc-8299-9df04a1a5c97` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:52f327cd-80f3-e8a6-7ad2-dd5698be6201` | 1 |
| `ce-6c33ff48-c9c9-4f19-b32e-d3890cfc9527` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:beb1678f-6c4d-a46a-9b03-05ea04d15b5d` | 1 |
| `ce-6e2b7809-ab45-4263-94cc-52db3651d74d` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:5f65f04a-4764-4010-ddf8-cdcd49d6bfa4` | 1 |
| `ce-87f081b4-efee-4369-a6d4-e69f6769c520` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:3e0ddcb7-2b53-5840-03cb-bea6c80bd69e` | 1 |
| `ce-ab264e86-8188-4d54-bb7b-6477f2f36fdd` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:fcffdd1f-cc30-cd4b-5a9a-0b813fa3213d` | 1 |
| `ce-b0083555-5e0a-424f-9c28-2240221592ad` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:26822d7b-29f7-7118-90f9-d5860894213f` | 1 |
| `ce-c3570a3b-fa79-4b25-bc1a-37c7e09df436` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:43bdaef5-bf72-72b7-ff38-eae807c0aec0` | 1 |
| `ce-c73b88ac-d683-4784-bf9a-0c1e8d93374d` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:e0266955-6a71-34c1-8a02-ce85ed310a43` | 1 |
| `ce-cfdea799-3feb-46f7-8233-e0aed115f2c0` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:943b1689-23cf-773b-e86d-7359d8c749c3` | 1 |
| `ce-d6feb462-f5f7-48e2-a0b8-6b9f99ae1bca` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:a4d8b414-6baf-f7e7-db20-40874613cbbb` | 1 |
| `ce-e3796db1-b190-4ace-ade1-a975134e07f1` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:2ec10c76-a2ec-2002-fba7-a27f5f23fe52` | 1 |
| `ce-eba6705b-9ef4-422e-8368-9c5b65a03705` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:f23dea3f-f538-8c6f-465c-f365e89ee069` | 1 |
| `ce-f5af1b64-696e-4db9-85d7-e5c0fea9d77b` | `REF_UNRESOLVED_BNODE` | `ceterms:ownedBy` | `_:4e7fa578-5462-6ee1-f9bc-fdbed21467fa` | 1 |

They are three shapes, and each was checked a different way.

**136 findings, 5 documents: an alignment object typed as a competency.** Each
of these is a `ceterms:Course` whose `ceterms:teaches` values carry exactly
four properties — `ceterms:framework`, `ceterms:frameworkName`,
`ceterms:targetNode`, `ceterms:targetNodeName` — which is the canonical
`ceterms:CredentialAlignmentObject` shape, and nothing else. Each is typed
`ceasn:Competency`. CTDL declares all four properties for
`ceterms:CredentialAlignmentObject` and `ceterms:FinancialAlignmentObject`
only, and `ceasn:Competency` has no `rdfs:subClassOf` path to either, so all
four fall outside their declared domain on every such node — four findings per
node, 34 nodes. `ceterms:teaches` ranges on *both* `ceasn:Competency` and
`ceterms:CredentialAlignmentObject`, so the reference itself is fine; only the
`@type` is wrong. Changing it to `ceterms:CredentialAlignmentObject` clears all
136. Verified by reading the nodes in all five cached documents.

**22 findings, 22 documents: a blank node that is not there.** Each is a
`ceterms:TransferValueProfile` document containing one nested
`ceterms:Course` node whose `ceterms:ownedBy` names a blank node identifier
that the document never defines. Verified mechanically against the bytes of
all 22: each document defines exactly one blank node and references two, and
the undefined one is always the `ownedBy` target. Blank node identifiers are
scoped to the document they appear in, so this cannot be settled by supplying
anything — there is no document anywhere that `_:96953f6f-…` could be found
in — which is why `--resolve` changed nothing here. Four of the identifiers
recur across different documents, which points at a publishing pipeline
emitting a stable internal id for an organization whose node never makes it
into the output.

**1 finding, 1 document: an outcome-data property on the profile that holds
the data.** A `ceterms:LearningOpportunityProfile` carries a nested
`ceterms:AggregateDataProfile` whose `qdata:relevantDataSet` points at a data
set. `qdata:relevantDataSet` declares 61 classes in its domain — credentials,
organizations, learning opportunities, jobs, occupations — and
`ceterms:AggregateDataProfile` is not among them, so the property sits one
level deeper than either published encoding allows. This is the one finding
worth arguing about, because the property's own `rdfs:comment` reads "Data Set
on which earnings or employment data is based", and the only class in CTDL
that *holds* earnings and employment data is the one its domain omits. It is
published as an ERROR anyway, for a measured reason: the **QData** encoding at
`credreg.net/qdata/schema/encoding/json`, which is where this term lives,
declares the identical 61-class domain and also omits
`ceterms:AggregateDataProfile`. Two published sources agree with each other
and the document differs from both, which is the line this project draws
between an ERROR and a disposition. The nearest class that *is* in the domain
is the `LearningOpportunityProfile` that owns the profile. Readers should know
the base rate: `qdata:relevantDataSet` appears twice in all 2,859 documents
fetched for this run, and both uses are on `ceterms:AggregateDataProfile`.

**A check on the snapshot itself.** Because two of the three shapes turn on
what the schema declares, the vendored snapshot was re-fetched from
`credreg.net` during verification and is **byte-identical to the copy this
tool ships** (SHA-256 `a2dd28cb…`, the hash already recorded in
`vendor/SOURCES.md`). None of these findings is an artefact of a stale
snapshot.

## What stayed unsettled after `--resolve`

155 references remain UNVERIFIABLE, 4.7% of the 3,326 the tool started with.
They are not a backlog of documents nobody fetched: exactly **one** is a
Registry resource that could have been supplied, and it is the neighbour that
answered HTTP 404. The rest are outside the one hop this survey defined.

| What the unsettled reference points at | Findings |
|---|---|
| Registry /resources/ URI whose document was not supplied | 1 |
| credreg.net term | 48 |
| other host | 106 |

The 48 credreg.net references are CTDL vocabulary terms, which are concept
identifiers rather than documents to fetch. The 106 on other hosts are
alignment targets on publishers' own websites, which this survey does not
follow and does not record by name. So the honest ceiling on this method is
not 95% — it is that **one** referenced Registry document out of 1,660 was
beyond reach, and everything else left unsettled was never a Registry document
in the first place.

## Who published what

The 1,200 documents come from **169 distinct publishers**. Concentration is
real but not extreme: the most frequent accounts for 213 of 1200 (18%), and
the five most frequent for 492 of 1200 (41%).

The ERRORs are more concentrated than the corpus. All 159 come from **three**
publishers: one contributed the 5 courses with 136 findings, one the 22
transfer value profiles with 22, and one the single outcome-data finding. Both
of the larger groups look like one pipeline emitting the same shape repeatedly
rather than 27 separate mistakes, which is the useful thing to notice: at this
scale a structural defect is usually a property of a publishing tool, not of a
document.

## Against the 120-document run

The 2026-08-15 run drew 120 documents with a different seed against a corpus
of a different size, so this is a comparison of two samples, not a time series.
It is comparable in the way that matters — the earlier cache was re-validated
by this same tool version — but a difference between the columns is at least as
likely to be sampling as change in the Registry.

| Measure | 120 documents (2026-08-15) | 1,200 documents (2026-08-21) |
|---|---|---|
| Documents with no findings, alone | 3 of 120 (2%) | 94 of 1200 (8%) |
| Documents with at least one ERROR, with `--resolve` | 1 of 120 (1%) | 28 of 1200 (2%) |
| Documents carrying `CONCEPT_RANGE_CONFLICT` | 36 of 120 (30%) | 282 of 1200 (24%) |
| Documents carrying `CTID_NOT_UUIDV4` | 6 of 120 (5%) | 42 of 1200 (4%) |
| Share of findings that were UNVERIFIABLE, alone | 86% | 85% |
| UNVERIFIABLE findings settled by `--resolve` | 294 of 299 (98%) | 3171 of 3326 (95%) |

The two most load-bearing numbers barely moved. The UNVERIFIABLE share before
resolution is 86% and 85% — this really is what a Registry document looks like
to a validator that will not guess — and the settle rate is 98% and 95%. The
clean-document share rose from 2% to 8%, which is almost entirely the
`CredentialOrganization` share of each draw rather than any change in quality.

## Exclusions

None: there were no exclusions. All 1,200 drawn pages produced a document row.

## What this changes

1. **Two false-positive classes are gone from the tool.** A range of
   `rdfs:Resource` no longer rejects everything, and versioning a resource with
   another of its own class is a disposition rather than a failure. Between
   them they accounted for 108 of the 267 ERRORs this run first raised, against
   11 published documents that had done nothing wrong. This is the second
   consecutive survey whose main result was a bug in the validator, which is an
   argument for running the tool against real corpora before trusting it, not
   an argument that the corpus is clean. **Conflict 5 in the README is now
   handled** rather than deliberately unhandled, on the grounds set out above,
   and with the single-publisher base rate stated rather than buried.
2. **The harness stopped publishing a number it could not defend.** The request
   counter lost an interrupted run's tally and reported 1,770 for work costing
   at least 2,861. It is now banked after every request, the neighbour tallies
   are counted off the cache rather than off a per-run counter, and a
   referenced document that was neither fetched nor recorded as failed is
   counted as `unresolved` instead of disappearing.
3. **`--resolve` earned its ADR.** It settled 95% of the unknowns on a
   1,200-document corpus and introduced no new failure, which is exactly the
   additive property ADR 0004 claimed and could not previously demonstrate at
   scale.
4. **Nothing is filed with anyone.** No issue, pull request or report has been
   opened against any publisher, against Credential Engine, or against the
   Registry on the strength of this run. The two schema disagreements it turned
   up are described here and encoded as dispositions; that is the whole of the
   action taken.

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

That claim was measured rather than asserted. Running both ways against this
cache produced 2,422,812 bytes and 2,422,811 bytes differing on **exactly one
line** — `"from_cache": false` against `"from_cache": true`, the field whose
job is to record which way the file was made. With that one field normalised,
both files hash to SHA-256
`82656f17fee334a099b602d99f5a973bd056d3e18f6967620c7e8bc238233d0e`. Every
other byte, including all 1,200 document records, is identical.
