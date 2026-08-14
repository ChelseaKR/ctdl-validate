# Contributing to ctdl-validate

Thank you for considering a contribution. The premise of this tool is that
every finding cites a published rule and that the same input always produces
the same output, byte for byte. Contributing here carries two obligations
beyond the usual: never encode a rule from memory (cite and vendor the
source), and never break determinism.

If you have not yet, read [`README.md`](README.md) for what the tool is and
why, and [`SECURITY.md`](SECURITY.md) for how to report a vulnerability.

## Getting set up

ctdl-validate targets Python 3.12 (see `.python-version`) and uses
[`uv`](https://docs.astral.sh/uv/) for a reproducible, locked environment:

```sh
uv sync --frozen
uvx pre-commit install   # optional but recommended: ruff/mypy/gitleaks on commit
```

## The merge gate

A change merges when the full gate is green. Reproduce it locally with:

```sh
make verify
```

`make verify` runs the exact same targets `ci.yml` (and `release.yml`, at a
tag) invoke, on the same locked toolchain, so green locally means green in
CI:

| Gate | Command | What it checks |
| --- | --- | --- |
| Lint | `make lint` | `ruff check`: correctness, import hygiene, modern idioms, cyclomatic complexity (<= 10) |
| Format | `make format` | `ruff format --check` |
| Types | `make typecheck` | `mypy --strict` over `src` and `tests` |
| Tests + coverage | `make test` | pytest with branch coverage >= 90% |
| Dependency audit | `make audit` | pip-audit against the locked environment |

Four invariants are called out separately because they protect the tool's
core promises:

- **Cited rules only.** Every check traces to a vendored schema declaration
  or a quoted prose rule in `src/ctdl_validate/rules.py` with its source URL
  and retrieval date. Updating a rule means updating the vendored snapshot
  and its recorded SHA-256 in `src/ctdl_validate/vendor/SOURCES.md`, not
  editing a constant to match memory.
- **Determinism.** `tests/test_determinism.py` asserts byte-identical output
  across runs and across interpreter processes. No timestamps, no sampling,
  no network at validation time.
- **Validation stays offline.** Nothing under `src/ctdl_validate/checks/` may
  import from `src/ctdl_validate/extract/`, and
  `tests/test_offline_guarantee.py` removes `socket` before running the
  validator. A change that makes validation touch the network is a change to
  what this tool claims to be, and needs an ADR before it needs a review.
- **Extraction never invents.** A term becomes a CTDL term only where the
  vendored schema encoding declares an equivalence for it. No mapping table,
  no heuristic, no model, no generated CTID. Where the declarations do not
  answer, the value is dropped with a cited note saying so.

New checks should come with a break-the-gate case in
`tests/test_break_the_gate.py`: corrupt a proven-clean fixture in exactly the
way the check exists to catch, and assert it is caught. New extraction
behavior should come with a case in `tests/test_extract_break_the_gate.py`,
which asks the opposite question: give it a page that tempts a guess, and
assert no guess was made.

Changes to `src/ctdl_validate/extract/fetch.py` deserve extra care: it is the
only module in the project that opens a socket, its posture is documented in
its own docstring and in the README, and `tests/test_extract_fetch.py` proves
each promise against a server on localhost. Adding a way around the robots.txt
check will not be merged.

## Commit style: Conventional Commits

This repository uses [Conventional Commits](https://www.conventionalcommits.org/):
`<type>[optional scope]: <description>` with types like `feat`, `fix`,
`docs`, `refactor`, `test`, `build`, `ci`, `chore`. A breaking change is
marked with `!` and explained in a `BREAKING CHANGE:` footer.

## ADRs: record significant decisions

Any decision that is hard to reverse or that shapes the rule model, the
severity contract, or the vendoring policy gets an Architecture Decision
Record in [`docs/adr/`](docs/adr/) (`NNNN-short-title.md`; see ADR-0000 for
the format). Superseding an earlier decision means marking the old ADR
superseded, not deleting it.

## Pull requests

Open a PR against `main`. The short version of the checklist:

- `make verify` is green.
- No fixture or test data is copied from an upstream repository or issue
  tracker; fixtures are original, synthetic reproductions.
- No gate or floor is weakened.
- An ADR is added if you made a significant decision.
- [`CHANGELOG.md`](CHANGELOG.md) `[Unreleased]` is updated for user-visible
  changes.

## Reporting bugs and security issues

- **Security, including any false-clean-report path:** do not open a public
  issue; see [`SECURITY.md`](SECURITY.md).
- **Ordinary bugs:** open a GitHub issue with a synthetic payload that
  reproduces the problem.

## License

By contributing, you agree that your contributions are licensed under the
project's [Apache-2.0](LICENSE) license. You must have the right to release
what you contribute, and it must contain no proprietary material.
