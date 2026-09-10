# ctdl-validate

Deterministic structural validation for
[CTDL (Credential Transparency Description Language)](https://credreg.net/ctdl/handbook)
JSON-LD payloads, meant to run before publication to the Credential Registry.
Point it at the document you are about to publish; it checks the things a
publisher can get wrong silently: identifier kinds, reference targets, and
class pairings.

**[Try it in your browser](https://chelseakr.github.io/ctdl-validate/)**, with
nothing installed: the validator runs on your own machine via WebAssembly, so an
unpublished payload stays in the tab. To run it on the command line instead,
`pip install ctdl-validate`. Both are described in full below.

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

**Measured against the Registry:** this tool has been run over published
Credential Registry documents three times: a 120-document survey, that
survey's offline revalidation after a rule fix, and a 1,200-document run
drawn uniformly at random from the 395,847 documents in the `ce-registry`
community, with every referenced document the sample named supplied back to
it. What came back, including the 108 defects in this validator the
1,200-document run surfaced (hand-checked against the cached bytes and fixed
before publication) and the conflicts found in the published spec itself, is
in [Pointed at the Registry](#pointed-at-the-registry) and under
[`docs/findings/`](docs/findings/).

**Try it without installing anything:**
[chelseakr.github.io/ctdl-validate](https://chelseakr.github.io/ctdl-validate/)
runs the validator in your browser via WebAssembly. Nothing is uploaded, which
matters here: payloads usually need checking while they are still unpublished.
The page also lists every rule this build can report, with a payload behind
each one, derived by running the validator rather than written down beside it.
See [`web/README.md`](web/README.md) for how it is built and gated.

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
with the same content, and `--format sarif` the same findings as SARIF 2.1.0
for code-scanning viewers: ERROR is `error`, WARNING is `warning`, INFO and
UNVERIFIABLE are `note`, and no result is ever rendered as a pass. The
reasoning, including why UNVERIFIABLE is `kind: open` and not `level: none`,
is in `src/ctdl_validate/sarif.py`; the output validates offline against the
OASIS schema vendored in `tests/sarif/`.

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
pip install ctdl-validate
ctdl-validate <file.json>
ctdl-validate <file.json> --format json
ctdl-validate <file.json> --format sarif   # SARIF 2.1.0, for code scanning
ctdl-validate <file.json> --suggest        # name the corrections the payload determines
ctdl-validate --report-schema        # the shape that report conforms to

# What changed between two runs. No network, exit 0 either way.
ctdl-validate diff before.json after.json
```

That installs the release on PyPI. To run the code in this checkout instead —
which is what you want when `main` is ahead of the last tag, and what
`CONTRIBUTING.md` assumes — install it from the working tree:

```
uv sync --locked        # the pinned development environment
pip install -e .        # or, without uv, an editable install
```

Input can be a JSON-LD object with `@graph`, a single entity object, or an
array of entities.

### The JSON report is a published contract

`--format json` is what the GitHub Action, the playground, and the Registry
survey harness read. Its shape is published as a JSON Schema (draft 2020-12),
shipped inside the package and printed by `ctdl-validate --report-schema`, and
every report carries the `report_schema_version` it conforms to. That version
is the schema's, not the tool's, and the two move independently;
[docs/API.md](docs/API.md) says which kind of change moves which part of it,
and names the library surface with the same promise.

Read counts out of `summary` by key, never with a default:

```python
errors = report["summary"]["ERROR"]  # yes
errors = report["summary"].get("ERROR", 0)  # no
```

Every severity is always present, including the ones that are zero, so that a
missing key is a broken report rather than a count of none. `additionalProperties`
is false throughout the schema for the same reason: a consumer that validates
what it reads learns about a new key instead of passing over it. And an empty
`findings` array means no rule was tripped, not that everything was checked —
what the payload alone cannot settle is reported as `UNVERIFIABLE`.

It also does not mean there was anything to check. This tool reads `ceterms:`
and `ceasn:` terms; hand it `package.json` and it correctly trips no rule, and
until report schema 1.1.0 that report was byte-identical to a clean CTDL
payload's. `document.checked_entities` now says how many entities were in
scope, and the text report says in words when nothing was — which is what a
`pre-commit` hook needs before a `files:` pattern can be trusted. `null` there
is a third state, meaning the producer did not measure the scope; it is not
zero, and a consumer must not read it as zero.

### `diff`: what changed between two runs

```console
$ ctdl-validate diff tests/fixtures/clean_framework.json \
    tests/fixtures/bug_class_252_wrong_framework_identifier.json
added: present after, absent before (3)
  WARNING      ISPARTOF_FRAMEWORK_MISMATCH  entity=...ce-9e492574-...
      ceasn:isPartOf = ...ce-82566cee-...
      rule: ...
removed: present before, absent after (0)
  (none)
...
0 unchanged. A removed finding is a finding this run did not report; it is not
evidence that it was fixed.
```

Each side is a CTDL payload, validated on the spot with its own
`--resolve-before` / `--resolve-after` set, or a saved `--format json` report.
`--format json` for machine use. The exit code is 0 whether or not anything
changed, because a diff is data rather than a verdict; `--fail-on-new` exits 1
when an ERROR is present after and absent before.

This repository already computed this by hand every time a rule changed — "36
of 120 documents failing became 0, as all 38 `RANGE_VIOLATION` findings became
`CONCEPT_RANGE_CONFLICT`" is a diff between two runs, produced once and then
typed. The verb makes it reproducible, and gives every publisher the same
before/after view, offline.

Two identical findings are the same finding when their code, entity, property
and rule citation match. A finding whose value or message moved under that
identity is *changed*. A finding that differs only in its entity — a re-minted
CTID, a renumbered blank node — is *moved*, but **only where exactly one was
removed and exactly one added** under the same code, property, value and rule.
Where several were, which went where is a guess, so the pairing is declined
and said to be declined.

Two things it deliberately does not say:

- **A removed finding is not a resolved one.** Two finding lists cannot tell a
  repair from a run that read a different payload, used a different resolve
  set, or could not get far enough to report anything. It says *removed*, and
  prints what that is worth beneath the summary.
- **A saved report does not record which vendored CTDL snapshot produced it.**
  It records the tool version and the report schema version and nothing else
  about the run, so two reports can be compared with no way to know whether
  the same schema and context documents were behind them. That is printed as
  unknown in the header rather than passed over, and a tool-version mismatch
  is printed too. Neither stops the diff: they make it something the reader
  has to interpret, which they can only do if they are told.

## `--suggest`: the corrections the payload already determines

Four of this tool's codes name a defect whose repair is not a search. The
corrected value is written somewhere in the run's own input, and the only
thing missing is for a reader to see it beside the finding.

```console
$ ctdl-validate credential.json --suggest
WARNING      CTID_UPPERCASE  entity=$.@graph[0]
    ceterms:ctid = ce-B55F88E3-DFD4-430B-AB47-3E5F9986E1E4
    ...
    suggested: ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4  (the same CTID in lower case)
```

| Code | What is offered |
|---|---|
| `CTID_UPPERCASE` | the same CTID in lower case |
| `CTID_URI_MISMATCH` | the CTID this entity's own `@id` already carries — or, on the `@graph` envelope's own `@id`, the envelope URI re-spelled with the payload's one declared CTID |
| `REF_BARE_CTID` | the `@id` of the entity in this run that declares that CTID |
| `ISPARTOF_FRAMEWORK_MISMATCH` | the `@id` of the one `ceasn:CompetencyFramework` in reach |

Nothing is invented. No CTID is minted, no language is guessed, no literal
becomes an IRI, no model is involved: every candidate is a string already in
this run's input, drawn from the payload or from a `--resolve` document. Where
the run holds more than one candidate, or none, nothing is offered rather than
one being picked.

Three refusals are permanent, and
[`suggest.py`](src/ctdl_validate/suggest.py) carries the reason for each as
data rather than as a comment. `CTID_BARE_UUID` and `REF_BARE_UUID` get
nothing, because prefixing the UUID with `ce-` would produce a well-formed
CTID — which is exactly the problem: it would assert that a generated UUID
names a Registry resource, the claim the finding disputes. `LANGUAGE_MAP_EXPECTED`
gets nothing, because wrapping a literal needs a language tag the document does
not supply. And no UNVERIFIABLE finding of any code gets one, because a
candidate computed from the payload cannot settle what the payload cannot
settle.

Off by default, and the flag adds only: with it absent, this command's bytes
in every format are what they were. In `--format json` a finding carries a
`suggestions` array only where a candidate was derived — never an empty one,
so a report never spells "nothing was derived" the same way as "nothing was
asked". [docs/API.md](docs/API.md) states the shape and the version rule.

### `repair --draft`: those corrections, written out

`--suggest` names a correction. `repair --draft` applies the ones the payload
determines to a **copy**, re-validates the copy with the same deterministic
engine, and reports what moved.

```console
$ ctdl-validate repair credential.json --draft --out draft.json --patch-out patch.json
draft written to draft.json

applied (1)
  WARNING      CTID_UPPERCASE  entity=$.@graph[0]
      ceterms:ctid = ce-B55F88E3-DFD4-430B-AB47-3E5F9986E1E4
      -> ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4   at /@graph/0/ceterms:ctid

not applied (1)
  WARNING      CTID_NOT_UUIDV4  entity=$.@graph[1]
      ceterms:ctid = ce-59e8d15f-7895-1346-a5a8-7a0739a3d344
      left alone: no correction this payload determines

resolved (1) … introduced (0) … untouched: 1
```

**The input is never written.** An `--out` that is the input, or that is any
`--resolve` path, is refused before anything is opened — compared by resolved
path, so `./x.json` and `x.json` are the one file they are on disk.

**`replace` operations only**, and `--patch-out` writes them as an RFC 6902
patch. These four codes are re-spellings of a value already written, so there
is nothing to add and nothing to remove; a patch of `replace` operations
cannot change the document's shape.

**The counts come from re-running the checks**, not from the patcher. So a
draft that resolves nothing says so, and one that *introduces* a finding says
that too, with the finding — which is not hypothetical. A `ceterms:ownedBy`
written as a bare CTID is `REF_BARE_CTID`, and the correction is the `@id` of
the entity declaring that CTID. Once the reference resolves, the range check
can finally see what it points at, and an ERROR the unresolvable reference had
been hiding appears. The re-spelling is right and the document reads worse.
**That is the reason this writes a draft rather than a repair**, and why
`--draft` is required rather than defaulted.

A finding becomes an operation only when the run derived **exactly one**
candidate *and* **exactly one** place in the source carries the reported
value. The second condition is not redundant: an `@id` declared by two objects
is a defect this tool reports rather than refuses to read, so a finding against
that identifier can name a value written in two places, and patching one would
be a guess about which the finding meant. Every finding that fails either
condition is printed under *not applied* with the reason.

Exit is 0 when the draft was written and 2 when the input could not be read or
an output path was refused. **Not 1 for "the draft still has ERRORs"**: the
exit code that gates a publication is the validator's, run over whatever a
person decides to keep.

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
a glob such as `payloads/**/*.json`. Three further inputs, all optional:

- `resolve`: space-separated documents or directories to resolve references
  against, passed through as repeated `--resolve`. Same rules as the CLI, so
  they are indexed and never validated, and nothing is fetched.
- `fail-on`: `error` (default), `warning`, or `info`. The CLI itself gates on
  ERROR and only ERROR; a lower threshold is applied by the action, from the
  counts in the CLI's own `--format json` summary. UNVERIFIABLE is gated at no
  setting, because the tool counts it as neither a pass nor a fail.
- `sarif-file`: a path to write SARIF 2.1.0 to, for
  `github/codeql-action/upload-sarif`. Empty by default, which writes nothing.
  See [below](#code-scanning).

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

### Code scanning

Annotations vanish with the workflow run. To keep the findings, set
`sarif-file` and hand the file to `github/codeql-action/upload-sarif`; the
findings then appear in the Security tab and inline on the pull request. Every
UNVERIFIABLE finding arrives as an alert at level `note`, on purpose; filter by
rule, never by hiding them.

```yaml
permissions:
  contents: read
  security-events: write

jobs:
  code-scanning:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: ChelseaKR/ctdl-validate@v0.2.1 # `sarif-file` is newer than v0.2.1; pin a commit that carries it
        id: ctdl
        with:
          path: payloads/
          resolve: reference-data/
          sarif-file: ctdl-validate.sarif
      - if: ${{ !cancelled() && steps.ctdl.outcome != 'skipped' }}
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ctdl-validate.sarif
          category: ctdl-validate
```

The `if:` is what carries a *failing* run's findings to the Security tab:
without it the upload is skipped exactly when there is something to upload.

Every payload goes into one SARIF run, not one run each, because GitHub
accepts at most twenty runs per file and a publication set is routinely more
than twenty payloads. The file is written only when every document produced a
complete SARIF run, and the run fails without writing it otherwise. That is
deliberate and worth knowing: `upload-sarif` treats an upload as the complete
picture and resolves any alert it does not contain, so a file that had quietly
lost one payload's findings would close those alerts as fixed. A missing file
fails the upload step loudly instead.

`tool.driver.properties.vendoredSnapshot` in the log records the snapshot's
retrieval date and the SHA-256 of all four vendored files the run read,
computed from the files themselves. An alert outlives the checkout that
produced it, and the version of the tool alone does not say which encoding
decided the verdict — which matters here more than most places, because this
tool already reports `TERM_UNSTABLE` and `CONCEPT_OUTSIDE_SNAPSHOT` precisely
because CTDL moves.

The gate is tested in both directions, because a gate that cannot fail is
worse than no gate: `tests/test_action_runner.py` asserts the exit code for
clean documents, gated findings, unreadable input, and a `path` that matches
nothing, and CI runs the composite action itself over a clean fixture and a
deliberately broken one, failing the build if the broken one passes.

## pre-commit hook

The Action catches a bad payload after it is pushed. The hook catches it
before it is committed.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/ChelseaKR/ctdl-validate
    rev: v0.2.1 # the hook is newer than v0.2.1; pin a commit that carries it
    hooks:
      - id: ctdl-validate
        files: ^payloads/.*\.json$
        args: [--resolve, reference-data/]
```

Exit codes are the CLI's: 0 nothing gating, 1 at least one ERROR finding, 2 a
staged file that could not be read. `--resolve` behaves as it does everywhere
else — it lets a staged document resolve references against neighbours you
already hold, and the neighbours are never themselves validated.

**Set `files:` to the paths that hold your CTDL.** The hook declares
`types: [json]` and ships **no** default `files:` pattern, and that is a
decision rather than an omission. Without a pattern pre-commit hands it every
staged JSON file, and most repositories hold a great deal of JSON that is not
CTDL. Shipping a narrow default instead would trade that for a pattern that
can just as easily match nothing in your repository — and a gate that ran over
zero files reports success exactly as loudly as one that ran over all of them.

Neither problem is fixable by choosing a better pattern, so the hook counts
the three outcomes separately and prints all three:

```
ctdl-validate 0.2.1: 12 staged file(s) -- 3 checked, 9 not CTDL, 0 unreadable
```

A file that is valid JSON but declares no `ceterms:` or `ceasn:` term is
listed by name under **not CTDL**, and gets no report of its own — because
`0 finding(s): 0 ERROR, 0 WARNING, 0 INFO, 0 UNVERIFIABLE` printed under
`package.json` is not a fact about `package.json`. If *every* staged file
turns out that way, the run still exits 0, and says so in a sentence:

```
Nothing was checked. None of the staged files declared a term this tool
validates, so this run is not evidence that any CTDL payload is clean.
```

A staged `.json` file that does not parse exits 2 and names the parse error,
even when every other file is clean — a gate that could not read its input is
not a gate that passed, which is the posture the Action takes too. If your
repository keeps JSON-with-comments under a `.json` extension, `exclude:` those
paths.

The hook installs this package, which requires Python 3.12 or newer, into the
environment pre-commit builds for it — and pre-commit builds that environment
with the interpreter *it* is running under. If yours is older, the install
fails while resolving build dependencies, in a message about `setuptools` that
says nothing about this project. Point it at a supported interpreter:

```yaml
default_language_version:
  python: python3.12
```

CI runs `pre-commit try-repo` against this repository's own fixtures, in all
three directions: the clean fixture must pass, the broken one must fail, and a
JSON file that is not CTDL must pass *while saying it checked nothing*.

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
reproducible offline; it decodes those bytes exactly as the fetch path does --
the page's own `<meta charset>`, then a labelled `errors="replace"` fallback --
so the same bytes give the same document either way, and the report names the
encoding it used.

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

### What extraction reports

Under-reporting is only visible in the notes if the notes are written down, so
here they are. Every one is a statement about *this page and this mapping*, not
a defect in the page: WARNING means the page published something the extract
does not carry, INFO means something worth a human's eye that lost nothing.
ERROR is not used here -- extraction either completes and reports, or fails
outright with a nonzero exit code.

| Code | Severity | What it says |
|---|---|---|
| `NO_STRUCTURED_DATA` | WARNING | The page publishes no JSON-LD, microdata or RDFa. Reading the credential off the prose would mean inventing structure the publisher never asserted. |
| `JSONLD_PARSE_ERROR` | WARNING | A `<script type="application/ld+json">` block is not valid JSON, so it was skipped whole. |
| `JSONLD_CONTEXT_UNRESOLVED` | WARNING | The block's `@context` is not one this tool resolves, so its unprefixed keys were left unread rather than resolved against a vocabulary nobody declared. |
| `MICRODATA_NAME_UNRESOLVED` | WARNING | A bare `itemprop` on an item with no `itemtype`. The HTML standard makes such a name proprietary to the author, so there is nothing to resolve it against. |
| `MICRODATA_ITEMREF` | WARNING | The page associates properties with items through `itemref`, which this reader does not follow, so any property reached only that way is missing. |
| `EMPTY_VALUE` | INFO | An element carries an `itemprop` and publishes no value for it. An empty value asserts nothing. |
| `RDFA_TERM_UNRESOLVED` | WARNING | A bare RDFa term with no `vocab` in scope. |
| `RDFA_BEYOND_LITE` | WARNING | An element carries RDFa 1.1 Core attributes alongside Lite ones. The Core attributes are not interpreted, so statements depending on them are missing. |
| `ITEM_UNTYPED` | WARNING | The markup declares no type for an item, so there is no class to map and nothing was emitted for it. |
| `CLASS_NOT_MAPPED` | WARNING | No CTDL class is declared equivalent to this type, so the item and its values were dropped rather than filed under a class this tool chose. |
| `CLASS_RELATED_NOT_EQUIVALENT` | INFO | A CTDL class is declared a *subclass* of this type. That relation runs from CTDL outward and does not license reading the type as that class. |
| `CLASS_AMBIGUOUS` | WARNING | More than one CTDL class declares an equivalence to this type, so no single class follows from the markup. |
| `PROPERTY_NOT_MAPPED` | WARNING | No CTDL property is declared equivalent to this term, so the value was dropped. The page published it; the extract does not carry it. |
| `PROPERTY_RELATED_NOT_EQUIVALENT` | INFO | A CTDL property is declared a *subproperty* of this term, which does not license reading the term as that property. |
| `PROPERTY_AMBIGUOUS` | WARNING | Two or more CTDL properties claim this term and the subject's class does not single one out by declared domain. |
| `NESTED_ITEM_DROPPED` | WARNING | The value is a nested item that produced no CTDL entity, so the reference would point at nothing. |
| `VALUE_NOT_LITERAL` | WARNING | The page published a nested item where the CTDL property takes a literal; flattening it would mean composing text this tool wrote. |
| `VALUE_NOT_IDENTIFIER` | WARNING | The CTDL property takes an identifier and the page published a literal. Minting one to hold it would invent an entity. |
| `LANGUAGE_UNDECLARED` | INFO | CTDL declares the property a language map and the page declared no language. The literal is emitted untagged for a publisher to complete. |
| `CTID_ABSENT` | INFO | No entity in the extract carries a CTID, because the page published none. Registry publication needs one per resource; this tool will not generate it. |

Like the rule table below, this is a hand-written list held up by a gate:
`tests/test_every_rule_fires.py` fails if a code here is not emitted by
`src/ctdl_validate/extract/` or a code that package emits is not here, and
each one is backed by a page in `EXTRACT_TRIPWIRES` that the extractor is
actually run over. That file also reconciles both tables against every finding
code the whole package constructs, so a directory falling outside them fails
rather than shrinking the denominator in silence.

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
| 4 | Domain and range per `schema:domainIncludes` / `schema:rangeIncludes`, with `rdfs:subClassOf` closure, plus the wrong-framework `isPartOf` pattern | `DOMAIN_VIOLATION`, `RANGE_VIOLATION`, `ISPARTOF_FRAMEWORK_MISMATCH`, `UNKNOWN_CLASS`, `UNKNOWN_PROPERTY`, `RANGE_DOCS_CONFLICT`, `CONCEPT_RANGE_CONFLICT`, `VERSION_RANGE_CONFLICT` | [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json), [CTDL-ASN schema encoding](https://credreg.net/ctdlasn/schema/encoding/json) |
| 5 | Inverse consistency for pairs the schema declares with `owl:inverseOf`; both directions present must agree, one direction alone is INFO | `INVERSE_MISMATCH`, `INVERSE_ONE_DIRECTION` | schema encodings, `owl:inverseOf` declarations |
| 6 | Identity: node objects sharing an `@id` are read as one entity, union of `@type` and properties, and the merge is reported | `ID_DECLARED_MORE_THAN_ONCE` | tool policy (below), [ADR-0005](docs/adr/0005-one-identifier-one-entity.md) |
| 7 | Concept scheme membership: a value on a property declaring `meta:targetScheme`, against the scheme it names; a term from another scheme is a WARNING, a term the snapshot does not declare is UNVERIFIABLE | `CONCEPT_OUTSIDE_SCHEME`, `CONCEPT_OUTSIDE_SNAPSHOT`, `CONCEPT_NOT_IDENTIFIED` | [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json) `meta:targetScheme` and `skos:inScheme` declarations, [ADR-0006](docs/adr/0006-concept-scheme-membership-is-a-warning.md) |
| 8 | Language-map shape: a property the context declares `{"@container": "@language"}` carrying a bare literal. 67 of the 80 such declarations, being the ones the schema encodings also declare as properties; the other 13 are context-only terms (`dct:`, `meta:objectText`, `rdfs:`, `skos:historyNote`, `vann:usageNote`, `qdata:`) and are not checked | `LANGUAGE_MAP_EXPECTED` | [CTDL context](https://credreg.net/ctdl/schema/context/json), [CTDL-ASN context](https://credreg.net/ctdlasn/schema/context/json) |
| 9 | Term status: a term the encoding declares `vs:term_status vs:unstable`, used as a class, a property or a concept value, is disclosed and not interpreted. Those three roles reach 461 of the 478 unstable terms; the other 17 are `skos:ConceptScheme` declarations, which a payload never names directly | `TERM_UNSTABLE` | [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json) `vs:term_status` declarations |

Every finding carries its rule citation, source URL, and retrieval date in
the output itself, in both text and JSON formats.

This table is not the only place the rule set is written down, and it is the
only place it is written down *by hand*. `tests/test_every_rule_fires.py`
fails if a code here is not emitted by the source or a code the source emits
is not here, and the
[playground](https://chelseakr.github.io/ctdl-validate/) shows the same set
derived at run time: one document per code, validated in the browser, each row
being that run's own output.

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
- Concept scheme membership for any term the vendored snapshot does not
  declare. Check 7 decides membership for the 456 concepts the encodings
  declare and for nothing else. Published documents put external framework
  identifiers -- O\*NET occupation pages, IPEDS CIP codes, Census NAICS codes
  -- on those same properties, by design; 1,194 of the 4,161 scheme-bound
  values in the 2026-08-21 survey were of that kind. Those are reported
  `CONCEPT_OUTSIDE_SNAPSHOT` (UNVERIFIABLE), which says the tool did not check
  the value, not that the value is wrong. Four of the 40 schemes those
  properties name are not themselves declared as `skos:ConceptScheme` anywhere
  in the snapshot (`ceterms:IndustryClassification`,
  `ceterms:InstructionalProgramClassification`,
  `ceterms:OccupationClassification`, `qdata:CollectionMethod`), so no value
  drawn from them can ever be more than unverifiable here.
- Literal datatype validation beyond the CTID (dates, durations). Language
  map *shape* is now check 8, because the declaration it rests on is in the
  vendored context. The datatypes are not, and are blocked rather than
  deferred: checking that a value coerced to `xsd:date` is a date means
  knowing the lexical space of `xsd:date`, and nothing in the four vendored
  files defines it. Writing that grammar from memory is the one thing this
  project does not do. It needs the XML Schema datatypes specification
  vendored under the existing hashing policy.
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

6. `ceterms:hasMember` and `owl:sameAs` declare `rdfs:Resource` as their whole
   range. RDF Schema 1.1 section 3.1 makes that "the class of everything", so
   it excludes nothing — but no CTDL class reaches it by `rdfs:subClassOf`, so
   a naive subclass match rejects every entity instead of accepting every one.
   Not a conflict in CTDL so much as a trap in reading it, and one this tool
   fell into: a declared range naming only `rdfs:Resource` is now treated as
   unconstraining and raises nothing.

   `ceterms:isSimilarTo` is **not** a third case of that, though this README
   said it was until 2026-09-06. It declares 84 `schema:rangeIncludes` entries,
   83 distinct — CTDL lists `ceterms:CredentialType` twice — of which
   `rdfs:Resource` is one and the other 82 are real classes. The tool's
   exemption tests for `rdfs:Resource` *anywhere* in a range, so `isSimilarTo`
   is exempted too and CTDL's published 82-term union is never enforced.

   Whether it should be is an open question, recorded at
   [#60](https://github.com/ChelseaKR/ctdl-validate/issues/60) and deliberately
   unsettled. It is a real conflict inside the encoding: if `rdfs:Resource`
   belongs in the union, the other 82 terms constrain nothing; if the 82 terms
   are the constraint, `rdfs:Resource` does not belong. Enforcing them would
   raise `RANGE_VIOLATION` — an ERROR worded as a publisher's mistake — on the
   strength of that ambiguity, and the union reads arbitrarily from inside: it
   admits `ceasn:CompetencyFramework`, `ceasn:Rubric` and
   `ceasn:RubricCriterion` while excluding `ceasn:Competency`. That is a
   judgment about what this tool asserts about publishers, so it is the
   maintainer's to make rather than a mechanical fix. The snapshot fact and the
   current disposition are both pinned by tests, so neither can drift quietly.

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
| Accessibility | Applies — the browser playground is a published human-facing page, so it is in scope on its own; the CLI's own surface is plain-text terminal output plus `--format json`. | [`.github/workflows/accessibility.yml`](.github/workflows/accessibility.yml) runs axe-core against the page in both colour schemes at `wcag2a,wcag2aa,wcag22aa` plus axe's `best-practice` rules (heading order, one `<main>` and one `<h1>`, content inside landmarks), checks reflow at 320 CSS px, and Lighthouse must score 1.00. Since 2026-08-29 it audits two states: the post-run report and rule catalogue, and the startup. Measured 2026-08-29: 0 violations, 42 rules passed in the post-run state and 39 in the startup state, in each scheme; Lighthouse 1.00 in each. What is not gated, and why, is written in that workflow's header. |
| Internationalization | N/A (findings quote English-language spec prose verbatim; see [docs/I18N.md](docs/I18N.md) for the reason and the flip-to-applies trigger) | Multilingual payload *data* validates identically; the declaration covers operator-facing strings only. |
| AI Evaluation | N/A (deterministic rule engine and a deterministic extractor; no model, prompt, retrieval, embedding, or LLM call anywhere, including in `extract`; AI-assisted authoring is disclosed under [Disclosure](#disclosure)) | Zero runtime dependencies makes the no-model claim mechanically checkable; the extractor's refusals are tested in `tests/test_extract_break_the_gate.py`. |
| Documentation | Applies | This README, [CHANGELOG.md](CHANGELOG.md), ADRs in [docs/adr/](docs/adr/), [CITATION.cff](CITATION.cff), [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md). |
| Quality & Metrics | Applies | [docs/ROADMAP.md](docs/ROADMAP.md) names every gate as AUTO, REVIEW, or a reasoned exception; nothing is silently skipped. |
| Release & Versioning | Applies | SemVer; `CHANGELOG.md` kept current; trusted-main signed-tag release workflow. Three signed tags (`v0.1.0` 2026-08-08; `v0.2.0` and `v0.2.1` 2026-08-16), each a GitHub Release with the wheel and sdist attached and on PyPI as `ctdl-validate`. `tests/test_release_state.py` pins this README, `CITATION.cff`, and the `uses:` examples to `pyproject.toml`'s version and to the CHANGELOG's dated heading for it. |
| Performance | Applies — the score control is met **and gated**; the byte control is **declared N/A**, not quietly waived. The playground downloads a 5.6 MB WebAssembly Python runtime, because the alternative to running the validator in the visitor's browser is uploading unpublished credential data to a server. | [`.github/workflows/performance.yml`](.github/workflows/performance.yml) runs Lighthouse against the real page — no static mode, so the Pyodide boot is included — and fails below **0.90**. That threshold is measured, not assumed: on 2026-09-05 the page scored **1.00** with **0 ms** of total blocking time on five runs, and forcing the boot back onto the main thread scored **0.70** with **10,210 ms**, so the gate was watched failing for the reason it exists before it was trusted to pass. The floor stays at 0.90 rather than the 1.00 it clears because a performance score is a weighted function of continuous timings on a shared runner, where the accessibility gate's 1.00 is a discrete rule set that scores the same every time. The byte control cannot be met by a page whose point is a 5.6 MB local runtime, so per the standard's own rule it is declared N/A with its reason in [docs/ROADMAP.md](docs/ROADMAP.md) rather than run with a threshold nobody intends to meet; the workflow still prints the figure (**248,285 B** against < 204,800 B, summed across every resource type because Lighthouse's "script" type now excludes what a worker requested) so the overage stays visible. |
| AI Development Measurement | Applies — this tool was built with AI assistance and reviewed by a human, disclosed under [Disclosure](#disclosure). What is measured is delivery outcomes, not tool-usage counters: sessions, tokens, and percent-AI-generated are not tracked here, and would not gate anything if they were. | [docs/ROADMAP.md](docs/ROADMAP.md) § Delivery health carries the DORA signals with an explicit note that a single release supports a fact, not a rate; the rows that cannot be computed yet say so instead of carrying invented zeroes. |
| Incident Response | Applies — private vulnerability reporting with a 72-hour acknowledgement target, and a definition of what counts as a vulnerability here that names a false clean report as a first-class integrity bug rather than a cosmetic one. | [SECURITY.md](SECURITY.md). No incident has been recorded for this repo, so there is no `docs/incidents/` directory; a real one would ship a dated postmortem alongside the fix. |
| Data Governance | Applies — the validator reads a local file and writes a report; it stores nothing, sends nothing, and has no telemetry. `extract` is the one subcommand that opens a network connection, and it fetches only the page it was given after checking `robots.txt` at every hop. | Vendored schema snapshots carry their retrieval date and SHA-256 in `src/ctdl_validate/vendor/SOURCES.md`, and `tests/test_vendor_integrity.py` fails if one is altered. Payload data stays on the operator's machine; the playground runs the validator in the visitor's browser for the same reason. |

## License

Apache-2.0. CTDL and CTDL-ASN are Credential Engine's, published under
Creative Commons Attribution 4.0; the vendored files retain their origin in
SOURCES.md. This project is not affiliated with or endorsed by Credential
Engine.
