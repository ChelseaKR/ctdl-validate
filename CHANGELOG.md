# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Check 7, concept scheme membership: `CONCEPT_OUTSIDE_SCHEME` (WARNING),
  `CONCEPT_OUTSIDE_SNAPSHOT` (UNVERIFIABLE) and `CONCEPT_NOT_IDENTIFIED`
  (UNVERIFIABLE). 48 properties across the two encodings declare
  `meta:targetScheme`, and 456 concepts declare `skos:inScheme`; both halves
  were already vendored and neither was read. A value on a scheme-bound
  property is now classified against the scheme the property names, and every
  outcome is reported rather than skipped.

  A term the snapshot declares in another scheme is a WARNING, not an ERROR:
  no published Credential Engine document says the Registry enforces
  `meta:targetScheme` on ingest. A term the snapshot does not declare is
  UNVERIFIABLE, because roughly a quarter of the values published on these
  properties point at O*NET, CIP and NAICS by design, and this tool has not
  vendored those frameworks and fetches nothing.

  Measured against the 1,200 published Registry documents of the 2026-08-21
  survey, re-validated offline from that run's cache: 1,190
  `CONCEPT_OUTSIDE_SNAPSHOT` and 30 `CONCEPT_NOT_IDENTIFIED` added across 504
  documents, no finding removed, and ERROR and WARNING counts unchanged at 159
  and 42. `CONCEPT_OUTSIDE_SCHEME` fires zero times on the published corpus.
  See [ADR-0006](docs/adr/0006-concept-scheme-membership-is-a-warning.md).

- `ID_DECLARED_MORE_THAN_ONCE` (INFO) and check 6, identity. Node objects that
  declare the same `@id` are now read as one entity -- the union of their
  `@type` values and of their properties -- and the merge is reported with
  every path that declared the identifier.

  Before this, `Graph.by_id` kept whichever declaration was parsed first and
  dropped the rest, so a reference to a repeated identifier was judged against
  a declaration chosen by `@graph` array position
  ([#33](https://github.com/ChelseaKR/ctdl-validate/issues/33)). The issue's
  worked case is a `ceterms:Place`, correctly declared and correctly
  referenced by a `ceterms:address`, reported `RANGE_VIOLATION` / ERROR
  because an unrelated entity embedded a stub with the same `@id` and an
  incidental `ceterms:Organization` type earlier in the file. Moving the real
  declaration to the front of the array made the ERROR disappear.

  Measured against the 1,200 published Registry documents of the 2026-08-21
  survey, re-validated offline from that run's cache: no document repeats an
  `@id`, and all 1,200 produce findings identical to those on the previous
  commit. The defect is real and reachable and does not occur in the published
  corpus, which is the honest form of that result. See
  [ADR-0005](docs/adr/0005-one-identifier-one-entity.md).

- `CONCEPT_RANGE_CONFLICT` (INFO): a new finding code for CTDL's two
  incompatible declarations of the same kind of value. A property that
  declares `schema:rangeIncludes: skos:Concept` **and** a `meta:targetScheme`
  is a reference to a term from one of CTDL's own concept schemes, and the
  Registry's published documents encode those as
  `ceterms:CredentialAlignmentObject` — which the encoding gives no path to
  `skos:Concept`. That combination is now reported as a documented conflict
  rather than a `RANGE_VIOLATION` / ERROR, citing both declarations and, where
  the snapshot has one, a sibling property drawing on the same concept scheme
  with the other range declared.

  Twenty properties are covered, derived from the vendored snapshot rather
  than listed by hand. A `skos:Concept` range with no `meta:targetScheme`
  (`skos:broader`, `ceterms:classification`) is ordinary SKOS and remains an
  ERROR, as does any other out-of-range class on a covered property.

  Measured against the 120 published Registry documents of the 2026-08-15
  survey, re-validated offline from that run's cache: documents failing
  validation went from 36 of 120 to 0 (document by document) and from 36 to 1
  with `--resolve`; ERROR findings went from 38 to 0 and from 40 to 2. The two
  survivors are the `ceterms:TransferValueProfile` version relations the survey
  identified by hand. No other finding changed, at any severity. (Those two are
  no longer errors either: the 1,200-document survey re-examined them and they
  are now `VERSION_RANGE_CONFLICT` / INFO — see below. The revalidated evidence
  file is left as written, because it measures a different fix.)

- `VERSION_RANGE_CONFLICT` (INFO): CTDL's three version properties —
  `ceterms:latestVersion`, `ceterms:nextVersion`, `ceterms:previousVersion` —
  each declare a `schema:rangeIncludes` that is a strict subset of their own
  `schema:domainIncludes`, dropping the same six classes from all three
  (`ceasn:Competency`, `ceasn:CompetencyFramework`, `ceasn:Rubric`,
  `ceterms:Collection`, `ceterms:Pathway`, `ceterms:TransferValueProfile`). A
  resource of a dropped class versioned by another resource of that same class
  is now this disposition rather than a `RANGE_VIOLATION` / ERROR: the domain
  says such a resource may have a version, the range says that version may not
  be one of its own kind, and every class the range does admit would make the
  earlier version of a transfer value profile a credential. One of the two
  declarations is wrong whatever anybody publishes, and an ERROR would be
  telling a publisher to fix something with nothing to fix it to.

  This reverses the deliberate decision recorded as conflict 5 in the README,
  and reverses it on the declarations rather than on frequency: the
  1,200-document survey found 32 documents doing this, but all 32 are from one
  publisher, and only two publishers in the whole surveyed corpus use these
  properties at all. The classes it applies to are derived from the vendored
  snapshot (`SchemaIndex.domain_only_classes`), and a test fails if the
  asymmetry ever leaves the snapshot. A version link to a *different* class is
  still an ERROR.

- `docs/findings/2026-08-21-registry-survey-at-scale.md` and its evidence JSON:
  1,200 documents drawn uniformly at random from the 395,847 in the
  `ce-registry` community, validated alone and again with all 1,659 reachable
  referenced documents supplied through `--resolve`. 1,200 fetched, none
  failed, none excluded. `--resolve` settled 3,171 of 3,326 UNVERIFIABLE
  findings and introduced no new ERROR. Every number the write-up publishes is
  recomputed from the evidence by `tests/test_findings_registry_at_scale.py`.

- `PropertyDef.target_scheme` on the schema index, carrying the
  `meta:targetScheme` declarations that were previously parsed and discarded.
- `tests/test_release_state.py`: the README status line, `CITATION.cff`, the
  README's `uses:` examples, and the DORA rows in `docs/ROADMAP.md` are pinned
  to `pyproject.toml`'s version and to the CHANGELOG's dated heading for it.
  From 2026-08-16 to 2026-08-21 the README and the GitHub repository
  description both said `0.1.0` while `0.2.1` was the release on PyPI, and the
  `uses:` examples pointed at `@main` with a comment saying no release carried
  the action (#19, #23). The repository description now carries no version at
  all, for the same reason `__version__` no longer carries a literal: a field
  that does not exist cannot drift.

### Changed

- A declared range naming only `rdfs:Resource` is now treated as
  unconstraining and raises nothing. RDF Schema 1.1 section 3.1 makes
  `rdfs:Resource` "the class of everything", so it excludes no entity — but no
  CTDL class reaches it by `rdfs:subClassOf`, so matching a target's declared
  classes against it rejected *every* entity instead of accepting every one.
  This affected `ceterms:hasMember`, `ceterms:isSimilarTo` and `owl:sameAs`;
  in the 1,200-document survey it produced 47 spurious range errors against a
  single published collection that listed 47 licences.

- `tools/registry_survey.py` no longer publishes counts a resumed run can
  lose. The request tally is banked to `provenance.json` after every request
  rather than at the end of a phase — the 2026-08-21 draw was interrupted
  after 1,091 pages and its record claimed 1,770 requests for work that cannot
  have cost fewer than 2,861 — and the evidence file now reports both
  `access.requests.recorded` and `access.requests.implied_by_the_cache`.
  Neighbour tallies are counted off the cache and the sample's own references
  instead of a per-run counter, and a referenced document that was neither
  fetched nor recorded as failed is counted as `unresolved` rather than
  vanishing from the denominator.

- The playground's accessibility gate now runs axe-core's `best-practice`
  rules alongside the three WCAG tags. That is where heading order
  (`heading-order`), the one-`<main>`/one-`<h1>` landmark rules, and
  duplicate-id checks live, none of which a WCAG tag selects. Measured
  2026-08-21 in both colour schemes: 0 violations, 0 incomplete, 39 rules
  passed (was 25). Nothing in the page changed; the bar did (#20).
- `docs/ROADMAP.md` § Delivery health carries measured values for all four
  DORA signals across three releases, including a change-fail rate of 1 of 3
  (`v0.2.0` reported itself as 0.1.0) and a 27-minute time to restore, each
  with the timestamps it was computed from. Four owner actions that were
  already done (branch ruleset, private vulnerability reporting, the
  corrected portfolio manifest entry, the second release) are struck with the
  evidence; the third release is added as the open one.

- `make sync` installs with `uv sync --locked` rather than `uv sync --frozen`,
  and the README, `CONTRIBUTING.md`, the pull-request template, and the
  provider-markup survey's reproduction steps say `--locked` to match.
  `uv lock --check` already gated drift and still runs first, so the failure
  names its cause; the change removes the second command that would have
  installed a drifted lock and exited 0 if the first were ever dropped.
- `CITATION.cff` now carries `version: 0.2.1` and `date-released: 2026-08-16`,
  matching `pyproject.toml` and the signed tag. Both fields were omitted while
  this was pre-release and were not added when the first release was cut.

### Fixed

- The `[0.2.1]` section below was an empty heading; the release notes from the
  GitHub Release are now under it.
- The README's Standards Conformance table declares all fifteen standards. AI
  Development Measurement, Incident Response, and Data Governance had no row at
  all, and the Accessibility and Performance rows opened in a form that read as
  prose rather than as a state.
- The 2026-08-15 Registry survey said 31 properties declare
  `schema:rangeIncludes: skos:Concept`. That was the count in
  `ctdl/schema.json` alone, while the validator indexes it together with
  `ctdlasn/schema.json`, where the figure is 45. The sentence claimed to
  describe "the same snapshot" the tool reads and did not. Corrected in place,
  with a note; the run's own measurements never depended on it, and the figures
  are now derived from the snapshot in `tests/test_domain_range.py` so they
  cannot drift again.
- Check 5 (inverse consistency) could report `INVERSE_MISMATCH` (ERROR) on a
  document whose two directions actually agreed. The bug: an inverse
  reference written as a full nested object (`{"@id": ..., "@type": ..., ...}`)
  rather than a bare `{"@id": ...}` is parsed into a `NestedRef`, and the
  membership test that decides whether the other direction "points back"
  compared that `NestedRef` against a plain `@id` string with `in` — which is
  never true, since a `NestedRef` never equals a string. A publisher who
  embeds the entity it points at, instead of just citing it, got an ERROR
  reporting the two directions as contradictory when they were not. Fixed in
  two places: `Graph.resolve()` now prefers resolving a nested object by its
  own `@id` (`NestedRef.target_id`) when that identifier is already known
  elsewhere in the payload, so a reference to an entity declared once at the
  top level and embedded again inline resolves to the fully-declared node
  rather than a thinner duplicate; and the inverse check's membership test
  now recognizes a `NestedRef` whose `target_id` matches, instead of doing a
  raw containment check that only a string could pass.


## [0.2.1] - 2026-08-16

This section was an empty heading from the day of the release until
2026-08-21; the notes below are the ones published on the GitHub Release,
moved here so the CHANGELOG is the record it claims to be.

### Fixed

- The package reported a version it was not. `v0.2.0` shipped
  `pyproject.toml` at 0.2.0 while `__init__.py` hard-coded `"0.1.0"`, and
  that constant feeds `--version`, the JSON report stamp, and the fetch
  User-Agent, so every report 0.2.0 produced claimed it came from 0.1.0.
  `__version__` now reads the installed distribution metadata, leaving
  `pyproject.toml` the single source of truth with no literal left to drift.
  `tests/test_version_single_source.py` AST-parses the package and fails if
  any module assigns a version literal; the obvious guard, asserting
  `__version__` equals the manifest, cannot fail because the runner
  reinstalls from the manifest first, and was thrown away for that reason.

## [0.2.0] - 2026-08-16

### Added

- `action.yml`: a composite GitHub Action that runs the CLI over a file, a
  directory, or a glob and annotates each finding on the file it came from.
  Inputs are `path`, `resolve`, and `fail-on`; counts are published as step
  outputs. Nothing is installed and nothing is fetched: the package has no
  runtime dependencies, so the action runs the checked-out source off
  `PYTHONPATH`, and `actions/setup-python` is pinned to a commit SHA. The exit
  codes are the CLI's own, with two additions that refuse to pass silently: a
  `path` matching no file is exit 2, and an unreadable document is exit 2 even
  when every other document is clean. `tests/test_action_runner.py` and a CI
  self-test prove the gate fails on a document with an ERROR finding.
- `--resolve PATH`: hand the validator further CTDL documents, or directories
  of them, so a reference the payload does not define can be settled instead
  of reported as unknowable. A reference resolving in a supplied document
  becomes `REF_RESOLVED_SUPPLIED` (INFO) naming the file and the class it
  found there, and check 4 then judges it against the property's declared
  range exactly as it judges an in-payload reference, up to and including a
  `RANGE_VIOLATION` that gates the exit code. Nothing is fetched: supplied
  documents are read from the local filesystem, and the offline guarantee
  suite proves it by running a resolved validation with `socket` removed.
  Supplied documents are indexed, never validated. A reference that resolves
  nowhere stays UNVERIFIABLE and the message names what was supplied. See
  `docs/adr/0004-resolution-is-additive.md`, including why this stops short of
  the ERROR `oscal-validate` raises in the same situation.
- `docs/findings/2026-08-15-published-registry-survey.md` and its evidence
  JSON: the validator run over 120 documents drawn uniformly at random from
  the 395,878 published in the Credential Registry, with the harness
  (`tools/registry_survey.py`) committed and the sample seeded so the run is
  reproducible. Forty ERROR findings, all of which trace to inconsistencies in
  CTDL's own published schema encoding rather than to a publisher's mistake,
  including a false-positive class in this tool that the write-up documents
  rather than hides. `--resolve` turned 294 of 299 UNVERIFIABLE findings into
  verdicts and surfaced two errors that were unreachable without it.
- `tests/test_findings_evidence.py` now recomputes the Registry survey's
  rollups from its per-document records, and checks the write-up's prose
  numbers against them. Three figures had been typed in and were wrong before
  the test existed: the share of findings that were non-answers (86% of 348,
  not 87%), the 81 documents below the error threshold described as producing
  "only UNVERIFIABLE findings" when 9 of them produced a warning or a note,
  and "46 of the 77 properties" for two range families that overlap on three
  properties and so cover 74 distinct ones.
- `.github/workflows/accessibility.yml` and `web/a11y/audit.mjs`: a
  merge-blocking accessibility gate for the browser playground, which is a
  published human-facing page that nothing had ever checked. axe-core 4.13 at
  `wcag2a,wcag2aa,wcag22aa` in both colour schemes, a 320 CSS px reflow check,
  and a Lighthouse accessibility score that must be 1.00. Measured 2026-08-15:
  0 violations, 25 rules passed, Lighthouse 1.00. `audit.mjs` refuses to score
  a page whose `?a11y-static` report did not render: pointed at a 404 error
  page it used to report "5 passed, 0 violations" and exit 0, and a JS error
  that stopped the static render short would have produced the same green
  check on the empty page this gate exists to stop auditing.
- `ctdl-validate extract <url>`: deterministic extraction of CTDL-shaped
  JSON-LD from the structured markup a page already publishes (JSON-LD,
  microdata, RDFa Lite), with `--validate` running the full extract-then-check
  pipeline in one command and `--from-file` reproducing a run offline. No
  model calls anywhere; a term is mapped onto CTDL only where Credential
  Engine's vendored schema encoding declares an equivalence for it, and every
  note cites the declaration it rests on. See
  `docs/adr/0003-extraction-as-a-separate-command.md`.
- Network posture for the new subcommand, in one module and enforced by tests
  against a server on localhost: robots.txt fetched first and obeyed with no
  override flag, an unreachable robots.txt treated as a complete disallow per
  RFC 9309 2.3.1.4, an identifying User-Agent, at most five redirects with
  robots re-checked at every hop, byte cap, timeout, and per-host rate limit.
- `tests/test_offline_guarantee.py`: the validator's no-network promise is now
  proven by removing `socket` and running it anyway, rather than asserted in
  prose.
- `tests/test_extract_break_the_gate.py`: the extractor's own gate suite,
  asking the opposite question from the validator's, namely that no fact was
  invented.
- `docs/findings/2026-08-14-provider-markup-survey.md` and its evidence JSON:
  `extract` run over 32 real credential provider pages, with the survey
  harness (`tools/survey.py`) and target list committed so the run is
  reproducible. Of 29 pages read, 38% published no structured data at all and
  14% produced a CTDL entity for the credential they were offering.


### Fixed

- **Playground, SC 1.4.10 (reflow):** with findings rendered, the page was 366
  CSS px wide at a 320 px viewport, because the Registry URIs and rule source
  URLs every finding carries are unbreakable strings. Fixed with
  `overflow-wrap: anywhere`; the new gate was broken on purpose to confirm it
  catches the regression. The empty page passed the same check, which is why
  the accessibility audit now renders findings before scanning.
- Playground: the Pyodide runtime is injected by `boot()` rather than declared
  as a `<script src>` in the markup, with the same version pin and Subresource
  Integrity hash. A visitor who reads the page without validating anything now
  makes no CDN request, and the accessibility gate runs entirely offline.
- Playground: an inline `data:` favicon, so the page stops answering every
  visit with a 404 for `/favicon.ico` and a console error.

- `RDFA_BEYOND_LITE` no longer fires on ordinary HTML `rel` attributes. It now
  reports only elements that mix an RDFa 1.1 Core attribute with an RDFa Lite
  one. Found by running the extractor over 30 real pages, none of which used
  RDFa and all of which were flagged.

### Changed

- With no `--resolve`, a `REF_OUTSIDE_PAYLOAD` message now ends "Pass it with
  --resolve to settle this." The code, severity and exit-code behaviour are
  unchanged; only the message text is longer.
- Checks now take a `Session` (payload, schema, supplied documents) rather
  than a `(Graph, SchemaIndex)` pair, so the one input that can change a
  finding's severity is explicit at every use. `validate_document(data)` is
  unchanged for callers; it gained an optional second argument.
- Finding rendering moved from `cli.py` to `findings.py` as
  `render_findings_text` and `render_findings_json`, so both commands share
  one reporter. Output bytes are unchanged; the determinism suite guards this.

## [0.1.0] - 2026-08-08

Released from the signed tag `v0.1.0` on 2026-08-08, with the wheel and sdist
attached to the GitHub Release; published to PyPI on 2026-08-13.

Everything from "Portfolio standards conformance kit" down was filed under
`[Unreleased]` when the tag was cut and stayed there afterwards, so the
release notes generated from this section did not mention that 0.1.0 raises
the Python floor. It does: `ctdl-validate` 0.1.0 on PyPI declares
`Requires-Python: >=3.12`, and installing it on 3.10 or 3.11 fails. Moved here
on 2026-08-15 against the tag's own tree. The published GitHub Release notes
still show the shorter list.

### Added

- Portfolio standards conformance kit: CI running the same `make verify` gate
  as local development, Semgrep and full-history TruffleHog scanning
  workflows, Dependabot updates, a trusted-main release workflow wired ahead
  of the first tag, pre-commit hooks, CODEOWNERS, `SECURITY.md`,
  `CONTRIBUTING.md`, `CITATION.cff`, an ADR log under `docs/adr/`, an i18n
  declaration, responsible-tech audit notes, and a standards and metrics
  ledger (`docs/ROADMAP.md`).
- Initial version of the deterministic CTDL structural validator: CTID
  grammar checks, identifier-kind checks, in-payload reference resolution,
  domain/range validation with `rdfs:subClassOf` closure, inverse-consistency
  checks, and a rule citation with source URL and retrieval date on every
  finding, in both text and JSON output.
- Vendored, unmodified CTDL and CTDL-ASN schema and context snapshots with
  provenance and SHA-256 hashes recorded in
  `src/ctdl_validate/vendor/SOURCES.md` and enforced by
  `tests/test_vendor_integrity.py`.
- Break-the-gate suite (`tests/test_break_the_gate.py`) and byte-level
  determinism suite (`tests/test_determinism.py`).

### Changed

- Python floor raised from 3.10 to 3.12 (portfolio Code Quality floor; there
  were no installed users at the time). Tooling floors raised to ruff >= 0.15
  and mypy >= 1.18; cyclomatic complexity capped at 10; branch coverage gated
  at >= 90%. See `docs/adr/0002-python-312-floor.md`.
- `Severity` now derives from `enum.StrEnum` (Python 3.12 idiom). CLI text
  and JSON output are byte-identical to before; the determinism suite guards
  this.
- `load_schema` internals split into a helper to satisfy the complexity gate;
  no behavior change.
