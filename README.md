# ctdl-validate

Deterministic structural validation for [CTDL](https://credreg.net/ctdl/handbook)
JSON-LD payloads, meant to run before publication to the Credential Registry.
Point it at the document you are about to publish; it checks the things a
publisher can get wrong silently: identifier kinds, reference targets, and
class pairings.

No network calls at validation time. No model calls, ever. Same input, same
output, byte for byte. Every finding cites the published rule it came from.

There is a second command, `ctdl-validate extract <url>`, which reads the
structured markup a page already publishes and emits CTDL-shaped JSON-LD to
validate. It is the only part of this tool that opens a network connection,
and it still makes no model calls: see [Extraction](#extraction) for the
boundary, stated precisely.

**Status:** Beta. Version `0.2.1`, released 2026-08-16 from a signed tag, with
the sdist and wheel attached to the GitHub Release and published to PyPI as
[`ctdl-validate`](https://pypi.org/project/ctdl-validate/). The rule set, the
CLI, `extract`, `--resolve`, the GitHub Action, and the text and JSON
reporters are all in that release. What `main` carries beyond it is listed
under *Unreleased* in [CHANGELOG.md](CHANGELOG.md). This line is pinned to
`pyproject.toml` by `tests/test_release_state.py`, because a validator whose
own front page misreports its version has the defect it exists to catch.
Nothing here has been published to the Credential Registry, and this project
is not affiliated with or endorsed by Credential Engine.

**Try it without installing anything:**
[chelseakr.github.io/ctdl-validate](https://chelseakr.github.io/ctdl-validate/)
runs the validator in your browser via WebAssembly. Nothing is uploaded, which
matters here: payloads usually need checking while they are still unpublished.
See [`web/README.md`](web/README.md) for how it is built.

```
$ ctdl-validate my-framework.json
ERROR        CTID_BARE_UUID  entity=$.@graph[0]
    ceterms:ctid = b55f88e3-dfd4-430b-ab47-3e5f9986e1e4
    Bare UUID where a CTID belongs: the ce- prefix is missing. Expected grammar:
    ce- followed by a UUID v4 in 8-4-4-4-12 form, 39 characters, lower case
    hexadecimal, e.g. ce-e8a41a52-6ff6-48f0-9872-889c87b093b7.
    rule: About the CTID, section "CTID Structure": ...
    source: https://credreg.net/ctdl/ctid (retrieved 2026-08-06)
```

Exit code 0 when there are no ERROR findings, 1 when there are, 2 when the
input cannot be read at all. `--format json` produces machine-readable output
with the same content.

## Why this exists

Two publicly reported bug classes on CTDL extraction tooling motivated it:

1. A generated UUID written where a CTID belongs. The ce- prefix and the
   CTID semantics are silently lost; every downstream reference is wrong.
2. A competency extract whose `ceasn:isPartOf` carries an identifier that is
   not its framework's. The extract looks fine locally and is wrong globally.

Both are symptoms of one absence: nothing checks, before an extract is
written, that an identifier is of the expected kind and that a reference
resolves to an entity of the expected class. This tool is that check, as a
standalone gate any publisher can run against their own data.

`tests/fixtures/bug_class_250_bare_uuid_for_ctid.json` and
`tests/fixtures/bug_class_252_wrong_framework_identifier.json` reproduce the
two bug classes generically. They are original test data built for this
repository; nothing is copied from any upstream repository or issue tracker.

## Install and run

Python 3.12+, no runtime dependencies.

```
pip install .
ctdl-validate <file.json>
ctdl-validate <file.json> --format json
```

Input can be a JSON-LD object with `@graph`, a single entity object, or an
array of entities.

## Resolving references against documents you already have

CTDL payloads reference other payloads by URI as a matter of routine: a
credential names the organization that owns it, a competency names its
framework. On its own the validator reports each of those
`REF_OUTSIDE_PAYLOAD` / UNVERIFIABLE, which is honest and, run against a real
published Registry document, is often the entire report.

`--resolve` hands the run the neighbouring documents so those references can
be settled. It is repeatable and takes files or directories:

```
ctdl-validate credential.json --resolve owner.json --resolve neighbours/
```

- A reference that resolves in a supplied document becomes
  `REF_RESOLVED_SUPPLIED` (INFO), naming the file and the class found there,
  and check 4 then judges it against the property's declared range exactly as
  it judges an in-payload reference. A wrong-class target is an ERROR and
  gates the exit code.
- A reference that resolves nowhere stays UNVERIFIABLE, and the message names
  what was supplied, so "you did not give me the document" reads differently
  from "the documents you gave me do not contain it."
- Supplied documents are indexed, never validated. Their own defects are not
  your report's findings.
- **Nothing is fetched.** `--resolve` reads local files;
  `tests/test_offline_guarantee.py` runs a resolved validation with `socket`
  taken away.

Why this stops short of the ERROR that `oscal-validate` raises in the same
situation, and every other constraint on it:
[ADR-0004](docs/adr/0004-resolution-is-additive.md).

## GitHub Action

If the payloads you publish live in a repository, [`action.yml`](action.yml)
validates them on every pull request and annotates each finding on the file it
came from:

```yaml
name: Validate CTDL
on: [pull_request]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      # Pin a release tag, or a commit SHA for stricter supply-chain hygiene.
      - uses: ChelseaKR/ctdl-validate@v0.2.1
        with:
          path: payloads/
```

`path` takes one document, a directory (searched recursively for `*.json`), or
a glob such as `payloads/**/*.json`. Two further inputs, both optional:

- `resolve`: space-separated documents or directories to resolve references
  against, passed through as repeated `--resolve`. Same rules as the CLI, so
  they are indexed and never validated, and nothing is fetched.
- `fail-on`: `error` (default), `warning`, or `info`. The CLI itself gates on
  ERROR and only ERROR; a lower threshold is applied by the action, from the
  counts in the CLI's own `--format json` summary. UNVERIFIABLE is gated at no
  setting, because the tool counts it as neither a pass nor a fail.

```yaml
      - uses: ChelseaKR/ctdl-validate@v0.2.1
        id: ctdl
        with:
          path: payloads/**/*.json
          resolve: reference-data/ organizations.json
          fail-on: warning
      - run: echo "${{ steps.ctdl.outputs.unverifiable-count }} reference(s) unsettled"
```

The counts are published as outputs: `error-count`, `warning-count`,
`info-count`, `unverifiable-count`, and `files-validated`. The exit codes are
the CLI's, unchanged: 0 when nothing meets the threshold, 1 when something
does, 2 when a document could not be read. A `path` that matches no file at
all is also exit 2, because a run that validated nothing is not a run that
passed.

There is no install step and no lock file to hash-pin, because there is
nothing to install: `ctdl-validate` has zero runtime dependencies and ships
`python -m ctdl_validate`, so the action runs the checked-out source directly
and resolves nothing from PyPI while it runs. `actions/setup-python` is pinned
to a commit SHA and to the same Python 3.12 the rest of this repository uses.

The gate is tested in both directions, because a gate that cannot fail is
worse than no gate: `tests/test_action_runner.py` asserts the exit code for
clean documents, gated findings, unreadable input, and a `path` that matches
nothing, and CI runs the composite action itself over a clean fixture and a
deliberately broken one, failing the build if the broken one passes.

## Extraction

`ctdl-validate extract <url>` reads the structured markup a page already
publishes and emits CTDL-shaped JSON-LD. It exists because the thing that
gets published to the Registry usually starts life on a provider's website,
and "check what you are about to publish" is only half a workflow if the
other half is undocumented.

```
$ ctdl-validate extract https://example.edu/courses/weld-101 --format jsonld > extract.json
$ ctdl-validate extract.json
```

or in one run:

```
$ ctdl-validate extract https://example.edu/courses/weld-101 --validate
```

`--format text` (the default) prints the extraction report; `--format json`
puts the report and the document in one envelope; `--format jsonld` prints
the document alone on stdout and the report on stderr, so piping the document
somewhere never silently discards what was dropped on the way. `--from-file
PATH` reads a saved copy of the page instead of fetching it, which makes a run
reproducible offline.

Exit codes: 0 when at least one CTDL entity came out, 1 when the page was read
and produced none, 2 when nothing could be read at all. With `--validate` the
exit code is the worse of the extraction's and the validation's.

### The boundary, precisely

The promise at the top of this README is about the validator, and it is
unchanged. Restating it against the new command:

| | `ctdl-validate <file.json>` | `ctdl-validate extract <url>` |
|---|---|---|
| Network | None, with or without `--resolve`. `tests/test_offline_guarantee.py` removes `socket` and runs both anyway. | Fetches `robots.txt`, then at most one page. Nothing else. |
| Model calls | None. | None. There is no model anywhere in this repository. |
| Determinism | Same input, same output, byte for byte. | Same *page bytes*, same output, byte for byte. The network is the only nondeterminism and it lives in one module, `extract/fetch.py`. |
| Inference | Applies published rules; reports what it cannot see as UNVERIFIABLE. | Maps a term only where Credential Engine's schema encoding declares an equivalence. Never reads a credential out of prose. |

### The network posture

Set out in full in `src/ctdl_validate/extract/fetch.py`, and enforced by
`tests/test_extract_fetch.py` against a server on localhost:

- **robots.txt is fetched first and obeyed.** A `Disallow` matching this
  tool's product token `ctdl-validate` is a hard stop with exit code 2. There
  is no flag to override it, because a flag to ignore robots.txt is the whole
  of the harm. ([RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) 2.3.1.1)
- **An unreachable robots.txt stops the fetch too** (2.3.1.4: a crawler MUST
  assume complete disallow). A 4xx means no robots.txt exists and the fetch
  may proceed (2.3.1.3).
- **The User-Agent identifies the tool** and links to this repository, with
  the product token as a substring (2.2.1). `--contact` appends a contact
  detail; nothing replaces it with a browser's.
- **Redirects are followed manually, at most five, and robots.txt is checked
  again at every hop**, so a redirect cannot carry the fetch onto a host that
  disallows it.
- **One page per invocation**, http or https only, with a byte cap
  (`--max-bytes`), a timeout (`--timeout`), and a minimum interval between
  requests to a host (`--min-interval`) that a site's `Crawl-delay` can
  lengthen but never shorten.
- **Failures are loud.** Every stop is an error and a nonzero exit, never a
  partial page or an empty extract standing in for one.

### Where the mapping comes from

There is no mapping table in this repository. Credential Engine's schema
encodings already declare, in machine-readable form, which CTDL terms are
equivalent to terms in other vocabularies, and extraction reads those
declarations out of the same vendored, hash-checked snapshot the validator's
rules come from. In the snapshot retrieved 2026-08-06 that is 24
`owl:equivalentClass` and 118 `owl:equivalentProperty` declarations, spanning
schema.org, ASN, Dublin Core, Open Badges, SKOS, LRMI, CASE and Wikidata; of
those, 6 classes and 56 properties are schema.org's.

Direction is enforced. `ceterms:LearningProgram rdfs:subClassOf
schema:EducationalOccupationalProgram` says every LearningProgram is an
EducationalOccupationalProgram, not the reverse, so a page publishing
`EducationalOccupationalProgram` gets an INFO note naming the relation and no
CTDL entity. Where two CTDL terms claim one foreign term, the subject's class
must appear in exactly one of their `schema:domainIncludes` declarations;
otherwise the value is dropped as ambiguous.

### What it can and cannot extract

**Can:**

- JSON-LD in `<script type="application/ld+json">`, including `@graph`,
  nested objects, `@value`/`@language` objects, and CTDL language maps.
- Microdata, following the value rules in the [HTML Living
  Standard](https://html.spec.whatwg.org/multipage/microdata.html) section
  5.2.4 case for case.
- [RDFa Lite 1.1](https://www.w3.org/TR/rdfa-lite/): `vocab`, `typeof`,
  `property`, `resource`, `prefix`.
- Pages that already publish CTDL, which pass through unchanged.

**Cannot, by construction:**

- **Read a credential out of prose.** A page with no structured markup yields
  nothing, and says so. This is the price of the guarantee below, and on the
  open web it is the common case: of 29 provider pages surveyed on 2026-08-14,
  11 published no structured data at all and 4 produced a CTDL entity for the
  thing they were offering. See
  [docs/findings/](docs/findings/2026-08-14-provider-markup-survey.md).
- **Invent a CTID.** No entity in an extract carries `ceterms:ctid` unless the
  page published one. A minted identifier is indistinguishable from a real one
  downstream, and an extract is a draft for a human to finish.
- **Map a class schema.org declares a subclass of a mapped class.** CTDL
  declares an equivalence for `schema:Organization`, not for
  `schema:CollegeOrUniversity`. Resolving that would need schema.org's own
  class hierarchy, which this tool does not load; it is the single largest
  coverage limit, and it is reported per item rather than guessed.
- **Mint an identifier for a literal.** Where a CTDL property takes an IRI and
  the page published a name, the value is dropped with a note.
- **Infer a language tag.** CTDL declares 80 properties as language maps; a
  value is emitted as a map only where the markup declared a language (a
  JSON-LD `@language`, or the nearest HTML `lang`).
- **Follow `itemref`,** or interpret RDFa 1.1 Core attributes (`about`,
  `rel`, `rev`, `datatype`, `inlist`). Both are reported when present.
- **Resolve bare terms under a `@context` it does not recognize.** Recognized:
  schema.org, the CTDL and CTDL-ASN contexts, or an inline `@vocab`/prefix
  map. Anything else leaves the block's bare keys unread rather than assuming
  a vocabulary.
- **Parse HTML the way a browser does.** The tree builder handles the common
  implied end tags and no more; a page that leans on the full HTML5 tree
  construction algorithm may nest items differently here. Nesting deeper than
  200 elements is refused outright rather than read partially.

The reason for every one of these is the same, and it is the reason there is
no model in this tool: a language model would raise coverage and would also,
sometimes, produce a well-formed credential that the page never claimed. A
deterministic extractor limited to declared equivalences can only ever under-
report. Under-reporting is visible in the notes; a fabricated credential in
the Registry is not.

### Pointed at reality

[`docs/findings/2026-08-14-provider-markup-survey.md`](docs/findings/2026-08-14-provider-markup-survey.md)
is what came back from running `extract` over 32 real provider pages: two-year
colleges, universities, certification bodies, learning platforms, private
training providers, and employers running their own apprenticeships. Of the 29
that could be read, 62% published some structured data, 17% declared a type
describing the credential itself, and 14% produced a CTDL entity for it. Two
of the eleven extracts failed validation, both for the reason below. The
survey harness and its target list are in [`tools/`](tools/), and the run is
reproducible.

### An extract can be faithful and still invalid

Which is the whole argument for running the validator on it. A page publishing
`schema:Organization` with a `schema:address` pointing at a
`schema:PostalAddress` maps cleanly, term by term, through declared
equivalences, and the result fails validation: `ceterms:address` declares its
range as `ceterms:Place`, not `ceterms:PostalAddress`. Nothing went wrong in
the extraction; the two vocabularies simply do not compose the way a
term-by-term crosswalk implies. That gap is exactly what a publisher needs to
see before publishing, and it is what `extract --validate` shows.

## Pointed at the Registry

[`docs/findings/2026-08-21-registry-survey-at-scale.md`](docs/findings/2026-08-21-registry-survey-at-scale.md)
is what came back from validating 1,200 documents drawn uniformly at random
from the 395,847 published in the Credential Registry's `ce-registry`
community, and [the 2026-08-15
survey](docs/findings/2026-08-15-published-registry-survey.md) is the
120-document run before it. The read surface is public and needs no key; the
harness ([`tools/registry_survey.py`](tools/registry_survey.py)) re-checks
robots.txt every run, spends one request every two seconds, and records
structure and counts rather than anybody's data.

At 1,200 documents, with every reference the sample named supplied back to it:
1,200 fetched, none failed, none excluded; 1,659 of the 1,660 referenced
Registry resources in hand, the last one a 404. **28 of 1,200 carried an ERROR
finding**, and 94 carried nothing at all. Validated one document at a time, 85%
of findings were "I cannot see the document this points at"; `--resolve`
settled 3,171 of those 3,326 and **introduced no new ERROR**, which is the
additive property [ADR 0004](docs/adr/0004-resolution-is-additive.md) claims.
Of the 267 ERRORs the run first raised, 108 were defects in this validator,
found by hand-checking every one against the cached bytes and fixed before
publication; the write-up names all three shapes of the 159 that survived.

Two results. Forty ERROR findings, **every one of which traces to an
inconsistency inside CTDL's own published schema encoding rather than to a
publisher's mistake** — including a false-positive class in this tool that
the write-up documents in full and does not paper over. And, validated one
document at a time, 86% of the 348 findings the tool produced were "I cannot
see the document this points at"; supplying the 177 referenced documents through
`--resolve` turned 294 of those 299 non-answers into verdicts and surfaced two
errors that were unreachable without it.

That false-positive class is now fixed (conflict 4 below), and the same corpus
re-validated offline from the survey's own cache is the measurement of the
fix: document by document, **36 of 120 documents failing became 0**, as all 38
`RANGE_VIOLATION` findings became `CONCEPT_RANGE_CONFLICT` (INFO). With
`--resolve`, 40 ERROR findings became 2 — the `ceterms:TransferValueProfile`
version-relation errors in conflict 5, in the one document that survey
identified by hand. Every other finding, at every severity, is byte-for-byte
unchanged. Those 2 are no longer errors either: the 1,200-document run
re-examined conflict 5 and made it a disposition, so the same two findings are
`VERSION_RANGE_CONFLICT` (INFO) under the current tool. The revalidated
evidence file is left as it was written, because it is the measurement of a
different fix and re-running it would erase that.

## What it checks (v0)

| # | Check | Codes | Rule source |
|---|---|---|---|
| 1 | CTID grammar on `ceterms:ctid`, on `@id`, and on the tail of every Registry resource/graph URI; `ctid` must match the `@id` tail | `CTID_BARE_UUID`, `CTID_MALFORMED`, `CTID_UPPERCASE`, `CTID_NOT_UUIDV4`, `REGISTRY_URI_MALFORMED`, `CTID_URI_MISMATCH` | [About the CTID](https://credreg.net/ctdl/ctid), sections "CTID Structure" and "CTID-Based URI Structure" |
| 2 | Identifier kind: properties the CTDL context declares as `{"@type": "@id"}` with entity ranges must carry IRIs or blank node ids, not bare UUIDs or bare CTIDs | `REF_BARE_UUID`, `REF_BARE_CTID`, `REF_NOT_IRI` | [CTDL context](https://credreg.net/ctdl/schema/context/json), [CTDL-ASN context](https://credreg.net/ctdlasn/schema/context/json) |
| 3 | Reference resolution across what the run can see; undefined blank nodes are errors, IRIs resolved from a `--resolve` document are INFO, IRIs resolved nowhere are UNVERIFIABLE | `REF_UNRESOLVED_BNODE`, `REF_RESOLVED_SUPPLIED`, `REF_OUTSIDE_PAYLOAD` | Handbook, "Blank Node Identifier"; tool policy (below), [ADR-0004](docs/adr/0004-resolution-is-additive.md) |
| 4 | Domain and range per `schema:domainIncludes` / `schema:rangeIncludes`, with `rdfs:subClassOf` closure, plus the wrong-framework `isPartOf` pattern | `DOMAIN_VIOLATION`, `RANGE_VIOLATION`, `ISPARTOF_FRAMEWORK_MISMATCH`, `UNKNOWN_CLASS`, `UNKNOWN_PROPERTY`, `RANGE_DOCS_CONFLICT`, `CONCEPT_RANGE_CONFLICT` | [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json), [CTDL-ASN schema encoding](https://credreg.net/ctdlasn/schema/encoding/json) |
| 5 | Inverse consistency for pairs the schema declares with `owl:inverseOf`; both directions present must agree, one direction alone is INFO | `INVERSE_MISMATCH`, `INVERSE_ONE_DIRECTION` | schema encodings, `owl:inverseOf` declarations |
| 6 | Identity: node objects sharing an `@id` are read as one entity, union of `@type` and properties, and the merge is reported | `ID_DECLARED_MORE_THAN_ONCE` | tool policy (below), [ADR-0005](docs/adr/0005-one-identifier-one-entity.md) |

Every finding carries its rule citation, source URL, and retrieval date in
the output itself, in both text and JSON formats.

## Methodology

### Severities, honestly defined

- **ERROR**: the payload violates a cited structural rule. Gates the exit
  code.
- **WARNING**: a cited signal that something is very likely wrong, where the
  rule is not absolute or Registry enforcement of it is not documented.
  Example: a CTID with upper case hex matches the shape but not the published
  examples; the Registry's case handling is not documented, so the tool does
  not claim it will be rejected.
- **INFO**: worth a human look, not a defect. Example: one direction of a
  declared inverse pair without the other.
- **UNVERIFIABLE**: the answer cannot be determined from what the run was
  given. A reference to an entity outside the payload may be perfectly valid;
  the tool does not fetch anything, so it says so instead of guessing. Never
  rendered as a pass or a fail, and never gates the exit code. `--resolve`
  can turn one of these into an answer; nothing turns one into a failure
  ([ADR-0004](docs/adr/0004-resolution-is-additive.md)).

The rule behind UNVERIFIABLE is the rule behind the whole tool: never punish
what you cannot see, and never bless it either.

### Break the gate before trusting it

`tests/test_break_the_gate.py` starts from a proven-clean fixture, corrupts
one thing at a time (strips a ce- prefix, points `isPartOf` at the wrong
identifier, breaks an inverse pair, retypes the framework, corrupts a
Registry URI), and asserts each corruption is caught. A gate that has not
been deliberately broken is a gate you are trusting on faith.

The extractor's failure mode is the opposite one, so its suite asks the
opposite question. `tests/test_extract_break_the_gate.py` feeds it pages that
tempt a tool into a guess (a type with only a subclass relation to CTDL, a
name where an identifier belongs, untagged text under a language-map property,
prose with no markup at all) and asserts that no guess was made. One case
removes an equivalence from the crosswalk and asserts the mapping disappears
rather than falling back on something.

### Determinism

`tests/test_determinism.py` asserts byte-identical output for repeated runs,
including across separate interpreter processes. There is nothing to seed:
no sampling, no timestamps, no network.

The same test covers extraction from a saved page, which is the honest form of
the claim once a command fetches: the extract report carries no timestamp and
no duration, so the same page bytes always produce the same bytes out.

## Where the rules come from

The schema and context files are vendored unmodified in
`src/ctdl_validate/vendor/`, with source URLs, retrieval dates, and SHA-256
hashes recorded in [SOURCES.md](src/ctdl_validate/vendor/SOURCES.md) and
enforced by `tests/test_vendor_integrity.py`. All four were retrieved
2026-08-06. Prose rules (the CTID grammar, blank node scope, framework
publication) are quoted in `src/ctdl_validate/rules.py` with their page URLs.
No rule is encoded from memory.

## Scope, honestly

Covered in v0: the CTDL (`ceterms:`) and CTDL-ASN (`ceasn:`) vocabularies as
published in the encodings above, which includes the classes and properties
declared there for credentials, organizations, learning opportunities,
competency frameworks, and competencies, plus the SKOS terms those encodings
declare.

Not covered in v0, deliberately:

- Required-property checking (the Registry's Minimum Data and Currency
  Policy). v0 checks what is present, not what is missing.
- Concept scheme membership (`meta:targetScheme` declarations exist for 45
  properties and would support a real check; cut for scope).
- Literal datatype validation beyond the CTID (dates, durations, language
  map shapes).
- Vocabularies beyond CTDL and CTDL-ASN (QData and other profiles).
- Fetching anything *during validation*. References outside the payload are
  UNVERIFIABLE by design, not a network call away from being verified.
  `--resolve` settles them from files the operator already has and opens no
  socket to do it. The `extract` subcommand fetches a page; it never resolves
  a reference for the validator, and the validator never calls it.

Not covered by `extract`, deliberately: everything in [What it can and cannot
extract](#what-it-can-and-cannot-extract).

Terms in `ceterms:`/`ceasn:` namespaces that the vendored snapshot does not
declare produce WARNINGs, not ERRORs, because the snapshot can lag a schema
release. Terms in foreign namespaces (schema.org, Dublin Core) are not
CTDL's to judge and are skipped.

## Conflicts found in the published spec

Encoding the rules surfaced three places where Credential Engine's published
sources disagree with each other. The tool handles each explicitly rather
than picking a side silently:

1. `ceasn:isChildOf` does not list `ceasn:CompetencyFramework` in its
   declared range, but the `ceasn:isPartOf` usage note instructs top-level
   statements to use `isChildOf`, and the Handbook's own examples point it at
   the framework. Reported as `RANGE_DOCS_CONFLICT` (INFO), citing both
   sources.
2. `ceasn:hasTopChild` and `ceasn:isTopChildOf` read like an inverse pair
   but carry no `owl:inverseOf` declaration, so the tool does not treat them
   as one (`tests/test_inverses.py::test_undeclared_pairs_are_not_invented`).
3. Some Handbook example URIs omit the ce- prefix inside Registry resource
   URIs, which the About the CTID page (updated 2024) contradicts. The tool
   follows About the CTID and flags such URIs.
4. CTDL declares two different ranges for the same kind of concept reference.
   Across the vendored snapshot, 46 properties declare
   `schema:rangeIncludes: ceterms:CredentialAlignmentObject` and 45 declare
   `skos:Concept`, and nothing about the values tells the families apart.
   Three concept schemes are named by properties in *both* families —
   `ceterms:AudienceLevel` (`ceterms:audienceLevelType` vs
   `ceterms:creditLevelType` and `ceasn:educationLevelType`),
   `ceterms:CostType`, and `ceterms:ScheduleFrequency` — and a fourth,
   `ceterms:InstructionalProgramClassification`, is named by a single property
   that declares *both* ranges at once. Published Registry documents encode
   both families as a `CredentialAlignmentObject`. Reported as
   `CONCEPT_RANGE_CONFLICT` (INFO), citing both declarations, on the 20
   properties that declare `skos:Concept` **and** a `meta:targetScheme`. A
   `skos:Concept`-ranged property with no `meta:targetScheme` — `skos:broader`,
   `ceterms:classification` — is ordinary SKOS and still a `RANGE_VIOLATION`.

Validating the published corpus on 2026-08-15 surfaced a fifth, left as an
ERROR at the time because one document was the only evidence for it. The
1,200-document run of 2026-08-21 changed that disposition — on the strength of
the declarations rather than the count, which is still one publisher:

5. `ceterms:latestVersion`, `ceterms:nextVersion` and `ceterms:previousVersion`
   each declare a `schema:rangeIncludes` that is a strict subset of their own
   `schema:domainIncludes`, dropping the same six classes from all three:
   `ceasn:Competency`, `ceasn:CompetencyFramework`, `ceasn:Rubric`,
   `ceterms:Collection`, `ceterms:Pathway` and `ceterms:TransferValueProfile`.
   So a TransferValueProfile may carry a version relation but may not point it
   at another TransferValueProfile, and every class the range does admit would
   make its earlier version a credential. One of the two declarations is wrong
   whatever anybody publishes. Reported as `VERSION_RANGE_CONFLICT` (INFO),
   citing both declarations, and only where a resource is versioned by another
   of its own class — a version link to a *different* class is still a
   `RANGE_VIOLATION`. Unlike conflict 4 this is **not** supported by a
   frequency argument: only two publishers in the surveyed corpus use these
   properties at all, which the survey states plainly.

6. `ceterms:hasMember`, `ceterms:isSimilarTo` and `owl:sameAs` declare
   `rdfs:Resource` as their whole range. RDF Schema 1.1 section 3.1 makes that
   "the class of everything", so it excludes nothing — but no CTDL class
   reaches it by `rdfs:subClassOf`, so a naive subclass match rejects every
   entity instead of accepting every one. Not a conflict in CTDL so much as a
   trap in reading it, and one this tool fell into: a declared range naming
   only `rdfs:Resource` is now treated as unconstraining and raises nothing.

## Development

Uses [`uv`](https://docs.astral.sh/uv/) with a locked toolchain
(Python 3.12, see `.python-version`):

```
uv sync --locked
make verify   # lint + format + strict types + coverage-gated tests + pip-audit
```

`make verify` is the exact gate CI runs; see
[CONTRIBUTING.md](CONTRIBUTING.md) for the individual targets.

## Disclosure

This tool was built quickly with AI assistance (Claude), then reviewed and
tested by a human. The spec research was done first: the CTID grammar, the
context coercions, and every domain/range/inverse declaration were pulled
from credreg.net on 2026-08-06 and vendored before any check was written,
and the fixtures were built to reproduce two real bug classes without
copying any upstream data. Read the findings' citations critically; if a
cited source has changed since retrieval, the vendored snapshot, not this
tool's opinion, is what to update.

## Standards Conformance

This repository is part of a portfolio with shared engineering standards.
Status against each, with an explicit reason wherever a standard does not
apply; the enforcement ledger with targets and owners is
[docs/ROADMAP.md](docs/ROADMAP.md).

| Standard | State | Evidence |
|---|---|---|
| Responsible-Tech Framework | Applies | [docs/RESPONSIBLE-TECH-AUDITS.md](docs/RESPONSIBLE-TECH-AUDITS.md): the harm surface is false confidence, and the controls (severity contract, break-the-gate suite, cited rules) target it directly. |
| Code Quality | Applies | Floors in `pyproject.toml`: Python >= 3.12, ruff >= 0.15, mypy >= 1.18 (strict), complexity <= 10, branch coverage >= 90%; locked with `uv.lock`; reproduced locally by `make verify`. |
| Security & Supply-Chain | Applies | [SECURITY.md](SECURITY.md); SHA-pinned Actions; Semgrep and full-history TruffleHog in CI; pip-audit in `make verify`; Dependabot; gitleaks in pre-commit. |
| CI/CD | Applies | `ci.yml` runs the same `make verify` gate as local development; trusted-main release workflow (signed tag, re-verified at the tagged commit) wired ahead of the first tag. |
| Observability | N/A (single-shot CLI; no service, no telemetry, nothing reported anywhere; the report on stdout is the entire observable surface, and `extract` puts its whole transport story in that report) | Exit-code contract and JSON output are tested in `tests/test_cli.py` and `tests/test_extract_cli.py`. |
| Accessibility | Applies — the browser playground is a published human-facing page, so it is in scope on its own; the CLI's own surface is plain-text terminal output plus `--format json`. | [`.github/workflows/accessibility.yml`](.github/workflows/accessibility.yml) runs axe-core against the page in both colour schemes at `wcag2a,wcag2aa,wcag22aa` plus axe's `best-practice` rules (heading order, one `<main>` and one `<h1>`, content inside landmarks), checks reflow at 320 CSS px, and Lighthouse must score 1.00. Measured 2026-08-21: 0 violations and 39 rules passed in each scheme; Lighthouse 1.00 on the published page (2026-08-15). What is not gated, and why, is written in that workflow's header. |
| Internationalization | N/A (findings quote English-language spec prose verbatim; see [docs/I18N.md](docs/I18N.md) for the reason and the flip-to-applies trigger) | Multilingual payload *data* validates identically; the declaration covers operator-facing strings only. |
| AI Evaluation | N/A (deterministic rule engine and a deterministic extractor; no model, prompt, retrieval, embedding, or LLM call anywhere, including in `extract`; AI-assisted authoring is disclosed under [Disclosure](#disclosure)) | Zero runtime dependencies makes the no-model claim mechanically checkable; the extractor's refusals are tested in `tests/test_extract_break_the_gate.py`. |
| Documentation | Applies | This README, [CHANGELOG.md](CHANGELOG.md), ADRs in [docs/adr/](docs/adr/), [CITATION.cff](CITATION.cff), [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md). |
| Quality & Metrics | Applies | [docs/ROADMAP.md](docs/ROADMAP.md) names every gate as AUTO, REVIEW, or a reasoned exception; nothing is silently skipped. |
| Release & Versioning | Applies | SemVer; `CHANGELOG.md` kept current; trusted-main signed-tag release workflow. Three signed tags (`v0.1.0` 2026-08-08; `v0.2.0` and `v0.2.1` 2026-08-16), each a GitHub Release with the wheel and sdist attached and on PyPI as `ctdl-validate`. `tests/test_release_state.py` pins this README, `CITATION.cff`, and the `uses:` examples to `pyproject.toml`'s version and to the CHANGELOG's dated heading for it. |
| Performance | Applies — and one control is **not met**. The playground downloads a 5.6 MB WebAssembly Python runtime, because the alternative to running the validator in the visitor's browser is uploading unpublished credential data to a server. | Measured against the published page 2026-08-15: Lighthouse performance **0.42** against a budget of >= 0.90, script transfer **248,147 B** against a budget of < 204,800 B, LCP 29.2 s, accessibility 1.00, CLS 0. `PERF-02` cannot be met without giving up local execution; the trade is stated in [docs/ROADMAP.md](docs/ROADMAP.md) rather than waived quietly, and no advisory-mode gate is wired for a budget that is not met. |
| AI Development Measurement | Applies — this tool was built with AI assistance and reviewed by a human, disclosed under [Disclosure](#disclosure). What is measured is delivery outcomes, not tool-usage counters: sessions, tokens, and percent-AI-generated are not tracked here, and would not gate anything if they were. | [docs/ROADMAP.md](docs/ROADMAP.md) § Delivery health carries the DORA signals with an explicit note that a single release supports a fact, not a rate; the rows that cannot be computed yet say so instead of carrying invented zeroes. |
| Incident Response | Applies — private vulnerability reporting with a 72-hour acknowledgement target, and a definition of what counts as a vulnerability here that names a false clean report as a first-class integrity bug rather than a cosmetic one. | [SECURITY.md](SECURITY.md). No incident has been recorded for this repo, so there is no `docs/incidents/` directory; a real one would ship a dated postmortem alongside the fix. |
| Data Governance | Applies — the validator reads a local file and writes a report; it stores nothing, sends nothing, and has no telemetry. `extract` is the one subcommand that opens a network connection, and it fetches only the page it was given after checking `robots.txt` at every hop. | Vendored schema snapshots carry their retrieval date and SHA-256 in `src/ctdl_validate/vendor/SOURCES.md`, and `tests/test_vendor_integrity.py` fails if one is altered. Payload data stays on the operator's machine; the playground runs the validator in the visitor's browser for the same reason. |

## License

Apache-2.0. CTDL and CTDL-ASN are Credential Engine's, published under
Creative Commons Attribution 4.0; the vendored files retain their origin in
SOURCES.md. This project is not affiliated with or endorsed by Credential
Engine.
