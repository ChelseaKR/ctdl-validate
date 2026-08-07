# Standards and metrics ledger

Last measured: 2026-08-07. Owner: Chelsea Kelly-Reif. Review cadence: per
release and quarterly.

This file is the enforcement ledger required by the portfolio Quality &
Metrics standard. A row is an AUTO-GATE, a concrete REVIEW-GATE with an
evidence artifact, or an explicit N/A with a reason, never an unowned
aspiration. Feature scope (what v0 deliberately does not check) lives in the
README's "Scope, honestly" section.

## Metrics

| Metric | Target | Measured by | Gate | Owner |
|---|---|---|---|---|
| Branch coverage | >= 90% | `make test` (pytest-cov; `fail_under = 90` in pyproject) | AUTO | Maintainer |
| Tests | 100% green on Python 3.12 | CI `verify` job (`make verify`) | AUTO | Maintainer |
| Lint / format / types | 0 errors | `make lint`, `make format`, `make typecheck` (`mypy --strict`) | AUTO | Maintainer |
| Cyclomatic complexity | <= 10 per function | ruff mccabe in `make lint` | AUTO | Maintainer |
| Determinism | Byte-identical output across runs and interpreter processes | `tests/test_determinism.py` | AUTO | Maintainer |
| Vendored snapshot integrity | SHA-256 of every vendored file matches `vendor/SOURCES.md` | `tests/test_vendor_integrity.py` | AUTO | Maintainer |
| Gate self-test | Every seeded corruption of a clean fixture is caught | `tests/test_break_the_gate.py` | AUTO | Maintainer |
| Dependency vulnerabilities | 0 known in the locked toolchain | `make audit` (pip-audit) in verify and CI; Dependabot weekly | AUTO | Maintainer |
| Secret and SAST scanning | 0 verified secrets; 0 unresolved Semgrep findings | trufflehog.yml (push, PR, weekly), semgrep.yml (push, PR) | AUTO | Maintainer |
| SHA-pinned workflow actions | 100% | portfolio conformance checker; review on workflow diffs | AUTO | Maintainer |
| Spec snapshot freshness | Re-vendor and re-hash when upstream CTDL encodings change | Manual check against credreg.net before a release | REVIEW | Maintainer |
| Severity contract accuracy | UNVERIFIABLE never gates the exit code; ERROR always does | `tests/test_cli.py` plus release review of any severity change | AUTO + REVIEW | Maintainer |
| AI evaluation / GenAI telemetry | N/A: deterministic rule engine only; no model, prompt, retrieval, embedding, or AI ranking path | Dependency and import scan (zero runtime deps) | N/A | Maintainer |

## Delivery health

For this unreleased library, deployment frequency and change lead time are
the applicable DORA signals once releases begin. Change-fail rate and
recovery time become meaningful only after a tagged release exists; they
must remain N/A rather than be filled with invented zeroes.

## Open review and owner actions

- Enable a branch protection ruleset on `main` (block force-push and
  deletion). This is a GitHub settings change; it cannot be made from inside
  the repository.
- Register this repo in the portfolio `applicability.yml` (archetype, tier,
  flags, per-standard applies/na, `publication: cleared`); the repo is
  already public, so the manifest must say so.
- Enable GitHub private vulnerability reporting in repository settings so
  the channel `SECURITY.md` prefers is actually on.
- First tagged release via the trusted-main release workflow; decide on PyPI
  publication (Trusted Publishing) at that point. Nothing is published
  anywhere today.
- Re-check the three documented spec conflicts (README "Conflicts found in
  the published spec") against upstream before each re-vendoring.
