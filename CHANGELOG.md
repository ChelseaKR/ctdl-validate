# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

- Portfolio standards conformance kit: CI running the same `make verify` gate
  as local development, Semgrep and full-history TruffleHog scanning
  workflows, Dependabot updates, a trusted-main release workflow wired ahead
  of the first tag, pre-commit hooks, CODEOWNERS, `SECURITY.md`,
  `CONTRIBUTING.md`, `CITATION.cff`, an ADR log under `docs/adr/`, an i18n
  declaration, responsible-tech audit notes, and a standards and metrics
  ledger (`docs/ROADMAP.md`).

### Fixed

- `RDFA_BEYOND_LITE` no longer fires on ordinary HTML `rel` attributes. It now
  reports only elements that mix an RDFa 1.1 Core attribute with an RDFa Lite
  one. Found by running the extractor over 30 real pages, none of which used
  RDFa and all of which were flagged.

### Changed

- Python floor raised from 3.10 to 3.12 (portfolio Code Quality floor; the
  package is unreleased, so no installed users are affected). Tooling floors
  raised to ruff >= 0.15 and mypy >= 1.18; cyclomatic complexity capped at
  10; branch coverage gated at >= 90%. See
  `docs/adr/0002-python-312-floor.md`.
- `Severity` now derives from `enum.StrEnum` (Python 3.12 idiom). CLI text
  and JSON output are byte-identical to before; the determinism suite guards
  this.
- `load_schema` internals split into a helper to satisfy the complexity gate;
  no behavior change.
- Finding rendering moved from `cli.py` to `findings.py` as
  `render_findings_text` and `render_findings_json`, so both commands share
  one reporter. Output bytes are unchanged; the determinism suite guards this.

## [0.1.0] - 2026-08-06

### Added

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
