# Standards and metrics ledger

Last measured: 2026-08-21. Owner: Chelsea Kelly-Reif. Review cadence: per
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
| Findings write-ups agree with their evidence | Every number in a findings table is recomputed from the committed evidence JSON, and the Registry survey's draw is recomputed from its seed | `tests/test_findings_evidence.py` | AUTO | Maintainer |
| Survey evidence holds no record content | Every recorded value in the Registry evidence passes an identifier allow-list; no third-party host appears | `tests/test_findings_evidence.py` | AUTO | Maintainer |
| Self-description agrees with the release | The README status line, `CITATION.cff`, the `uses:` examples and this ledger carry `pyproject.toml`'s version and the CHANGELOG's dated heading for it | `tests/test_release_state.py` | AUTO | Maintainer |
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

Three releases exist, each a signed tag, a GitHub Release with the wheel and
sdist attached, and a PyPI upload: `v0.1.0` (2026-08-08), `v0.2.0` and
`v0.2.1` (both 2026-08-16). The rows below were measured on 2026-08-21 from
the tag and commit timestamps in this repository's history.
`tests/test_release_state.py` checks that the releases named here are exactly
the ones `CHANGELOG.md` dates, and that the two arithmetic figures follow from
the timestamps stated beside them; the lead-time figures are not re-derived in
CI, whose checkout is too shallow to see the tags.

| DORA signal | Value | Basis |
|---|---|---|
| Deployment frequency | 3 releases in the 8 days from the first tag to the latest (2026-08-08 to 2026-08-16) | tag dates, which are the CHANGELOG's heading dates |
| Change lead time | `v0.2.0`: 24 first-parent commits on `main` after `v0.1.0`, median 31.7 h from commit to tag, longest 185.3 h. `v0.2.1`: one commit, tagged 2 s after it landed | `git log --first-parent v0.1.0..v0.2.0` against the tag timestamp, measured locally |
| Change-fail rate | 1 of 3. `v0.2.0` reported itself as 0.1.0 in `--version`, in every JSON report, and in the fetch User-Agent, and was superseded the same morning | `v0.2.1`'s release notes and `tests/test_version_single_source.py` |
| Time to restore | 27 minutes: `v0.2.0` tagged 2026-08-16T14:58:39Z, `v0.2.1` tagged 2026-08-16T15:25:14Z | tag timestamps |

Three releases support facts, not trends. One failed release in three is not
a 33% rate in any predictive sense, and a median over the 24 commits of one
window describes that window. The rows will carry rates when there are
enough tags for a rate to mean something, and not before.

## Open review and owner actions

- (Done.) A ruleset named `protect-main` is active on `main` and blocks
  non-fast-forward pushes and deletion; verified through the repository API
  on 2026-08-21.
- (Done 2026-08-15.) This repository's entry in the portfolio
  `STANDARDS/applicability.yml` was corrected on that repository's `main`
  (commit `36747be`): `html: true`, `hosted: true`, tier `B+C`, `A11Y:
  applies`, `PERF: applies`. From 2026-08-07 until then the entry had
  declared no human-facing HTML while a Pages playground was live, which
  switched the accessibility and performance standards off for a public
  page. The gate wired here never depended on that entry, and the manifest
  now agrees with it.
- (Done.) GitHub private vulnerability reporting is enabled, so the channel
  `SECURITY.md` prefers is on; verified through the repository API on
  2026-08-21.
- (Done 2026-08-16.) Second release: `v0.2.0` carried `extract`,
  `--resolve`, the GitHub Action and both findings runs; `v0.2.1` followed
  27 minutes later, for the reason in the table above.
- Third release. `main` carries the `CONCEPT_RANGE_CONFLICT` disposition
  that turned 36 of 120 published Registry documents from failing to passing,
  and a `pip install ctdl-validate` does not: every published release still
  reports that false-positive class as ERROR. The CHANGELOG's *Unreleased*
  section is the release note; a tag is what is missing.
- Decide whether to vendor schema.org's class hierarchy. Today a
  `schema:CollegeOrUniversity` maps to nothing because CTDL declares an
  equivalence for `schema:Organization` only, and resolving the subclass chain
  would need schema.org's own vocabulary file (several megabytes) vendored
  unmodified under the existing hashing policy. It is the largest single
  coverage limit in `extract`, and taking it on is a scope and packaging
  decision, not a code one. REVIEW, owner: maintainer.
- Re-check the three documented spec conflicts (README "Conflicts found in
  the published spec") against upstream before each re-vendoring.
