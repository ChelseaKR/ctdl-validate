# Standards and metrics ledger

Last measured: 2026-08-14. Owner: Chelsea Kelly-Reif. Review cadence: per
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
| Validation stays offline | 0 sockets opened during validation | `tests/test_offline_guarantee.py` removes `socket` and runs the validator anyway | AUTO | Maintainer |
| robots.txt enforcement | A Disallow stops the fetch before the page is requested; an unreachable robots.txt stops it too; no override flag exists | `tests/test_extract_fetch.py` against a server on localhost | AUTO | Maintainer |
| Extractor invents nothing | 0 CTDL assertions without a declared equivalence; 0 generated CTIDs | `tests/test_extract_break_the_gate.py`, `tests/test_extract_crosswalk.py` (index checked against the vendored files, not a copy) | AUTO | Maintainer |
| Extraction determinism | Same page bytes, byte-identical document and notes, across interpreter processes | `tests/test_determinism.py` | AUTO | Maintainer |
| Crosswalk freshness | The crosswalk is re-read from the vendored snapshot; a re-vendoring changes it with no code edit | `tests/test_extract_crosswalk.py`; reviewed with the snapshot | AUTO + REVIEW | Maintainer |
| AI evaluation / GenAI telemetry | N/A: deterministic rule engine and deterministic extractor; no model, prompt, retrieval, embedding, or AI ranking path in either command | Dependency and import scan (zero runtime deps) | N/A | Maintainer |
| Accessibility of the playground | 0 axe-core violations of critical/serious/moderate at `wcag2a,wcag2aa,wcag22aa`, in both colour schemes; no horizontal scroll at 320 CSS px; Lighthouse accessibility 1.00 | `.github/workflows/accessibility.yml` (axe-core 4.13 via `web/a11y/audit.mjs`, plus Lighthouse) against `web/index.html?a11y-static` | AUTO | Maintainer |
| Keyboard and screen-reader walkthrough of the playground | Every primary task completable by keyboard; the Pyodide startup state is announced | Human walkthrough, recorded in `docs/RESPONSIBLE-TECH-AUDITS.md` section H | REVIEW | Maintainer |
| Playground performance | **Not met and declared.** Lighthouse performance 0.42 against a >= 0.90 budget and 248,147 B of script against a < 204,800 B budget, measured on the published page 2026-08-15 | Lighthouse against `https://chelseakr.github.io/ctdl-validate/`; re-measure per release | REVIEW | Maintainer |

### Why the performance budget is not met

The playground runs the validator in the visitor's browser through Pyodide,
which is a 5.6 MB WebAssembly Python runtime fetched from a CDN. That is the
whole point of the page: CTDL payloads most need checking while they are still
unpublished, and the alternative to running locally is asking people to upload
unreleased credential and competency data to somebody's server. No amount of
tuning brings a 5.6 MB runtime inside a 204,800 B script budget.

What has been done instead:

- The runtime is injected by `boot()` rather than written as a `<script src>`
  in the markup, so a visitor who reads the page without validating anything,
  and the accessibility gate, make no CDN request at all.
- The numbers are measured and published rather than waived quietly, and they
  are re-measured per release. Layout stability (CLS 0) and accessibility
  (1.00) are both clean; what fails is exactly the byte cost, and it is a
  fixed cost of the Pyodide version.
- No advisory-mode gate is wired. `PERFORMANCE-STANDARD` section 3 is explicit
  that a gate that cannot pass is declared N/A-with-reason, not run with
  `continue-on-error`.

The option not taken: deferring the runtime download to the first Validate
click would move 5.6 MB off the critical path and would very likely clear the
score, at the cost of making the first validation take tens of seconds with no
warning. Starting the download on load is a deliberate choice in the user's
favour, and `loadPyodideRuntime()` is a single call site if that judgement
changes.

## Delivery health

One release exists: `v0.1.0`, a signed tag dated 2026-08-08, published as a
GitHub Release the same day with the wheel and sdist attached, and to PyPI on
2026-08-13.

| DORA signal | Value | Basis |
|---|---|---|
| Deployment frequency | 1 release in the 8 days since the first tag | `v0.1.0`, 2026-08-08 |
| Change lead time | Not yet measurable | The first release carried the whole repository; there is no merge-to-release interval to measure until a second tag exists |
| Change-fail rate | 0 of 1 | No release has been yanked, patched, or rolled back. One data point is a fact, not a rate; it becomes a rate at n=3 or so |
| Time to restore | N/A | Nothing has needed restoring |

These stay honest by being small. A single release does not support a
frequency trend or a lead-time distribution, and filling those rows with
invented zeroes would be worse than the empty ones they replaced.

## Open review and owner actions

- Enable a branch protection ruleset on `main` (block force-push and
  deletion). This is a GitHub settings change; it cannot be made from inside
  the repository.
- Correct this repository's entry in the portfolio `STANDARDS/applicability.yml`.
  As of 2026-08-15 the entry on that repository's `main` still reads
  `flags: { html: false, ..., hosted: false }` with `A11Y: { na: "offline
  CLI/library with no human-facing HTML" }` and `PERF: { na: "pure
  library/CLI, no hosted route or shipped HTML" }`, which is false: a Pages
  playground has been live at chelseakr.github.io/ctdl-validate/ since
  2026-08-08 and is linked from the top of this repository's README. The
  accessibility gate wired here does not depend on that entry -- scope comes
  from `ACCESSIBILITY-STANDARD` section 0, which puts a published HTML surface
  in scope on its own -- but the manifest is the portfolio's scoping registry
  and it is currently wrong about this repo.
- (Done 2026-08-07.) The repo is registered in the portfolio
  `applicability.yml` with `publication: cleared`. What that entry says about
  the HTML surface is still wrong; see the correction item above.
- Enable GitHub private vulnerability reporting in repository settings so
  the channel `SECURITY.md` prefers is actually on.
- Second release. The `extract` subcommand, `--resolve`, and the two findings
  runs are all on `main` and in none of the published artifacts, so the
  version a `pip install ctdl-validate` gets is materially smaller than what
  this README describes. The README's Status paragraph says so; a tag would
  say it better.
- Decide whether to vendor schema.org's class hierarchy. Today a
  `schema:CollegeOrUniversity` maps to nothing because CTDL declares an
  equivalence for `schema:Organization` only, and resolving the subclass chain
  would need schema.org's own vocabulary file (several megabytes) vendored
  unmodified under the existing hashing policy. It is the largest single
  coverage limit in `extract`, and taking it on is a scope and packaging
  decision, not a code one. REVIEW, owner: maintainer.
- Re-check the three documented spec conflicts (README "Conflicts found in
  the published spec") against upstream before each re-vendoring.
