# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

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

- The README's Standards Conformance table declares all fifteen standards. AI
  Development Measurement, Incident Response, and Data Governance had no row at
  all, and the Accessibility and Performance rows opened in a form that read as
  prose rather than as a state.


## [0.2.1] - 2026-08-16

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
