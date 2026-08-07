# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Portfolio standards conformance kit: CI running the same `make verify` gate
  as local development, Semgrep and full-history TruffleHog scanning
  workflows, Dependabot updates, a trusted-main release workflow wired ahead
  of the first tag, pre-commit hooks, CODEOWNERS, `SECURITY.md`,
  `CONTRIBUTING.md`, `CITATION.cff`, an ADR log under `docs/adr/`, an i18n
  declaration, responsible-tech audit notes, and a standards and metrics
  ledger (`docs/ROADMAP.md`).

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
