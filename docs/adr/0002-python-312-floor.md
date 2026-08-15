# 2. Raise the Python floor to 3.12

## Status

Accepted

## Context

The initial commit shipped with `requires-python = ">=3.10"`. The portfolio
Code Quality standard sets a 3.12 floor (CQ-01) for repos without an
accepted exception. The package is unreleased: it is not on PyPI, the
repository has no tags and no GitHub releases, so there are no installed
users whose environment a floor raise could break.

*(Context as of the decision. `v0.1.0` shipped on 2026-08-08 and reached PyPI
on 2026-08-13, carrying `Requires-Python: >=3.12`, so the floor is now a
published constraint and lowering it later is the SemVer question the
Consequences section anticipated. Noted 2026-08-15; the paragraph above is
left as written, because an ADR records the context a decision was taken in.)*

## Decision

Set `requires-python = ">=3.12"`, pin `.python-version` to 3.12, and target
`py312` in ruff and mypy configuration. Adopt 3.12 idioms where the linter
recommends them (for example `enum.StrEnum` for `Severity`), with the
determinism test suite guarding that output bytes do not change.

## Consequences

- Environments on Python 3.10 or 3.11 can no longer install the package.
  Accepted while the user count is zero; lowering the floor later would be a
  breaking-change discussion with an ADR of its own.
- The codebase can rely on 3.12 standard library behavior without
  compatibility shims, which matters for a stdlib-only tool.
- The CI toolchain, the lockfile, and local development all pin the same
  interpreter line, so "works locally" and "works in CI" stay the same
  claim.
