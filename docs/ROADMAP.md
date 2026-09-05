# Standards and metrics ledger

Last measured: 2026-09-05 (playground performance; everything else 2026-08-29).
Owner: Chelsea Kelly-Reif. Review cadence: per release and quarterly.

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
| Findings write-ups agree with their evidence | Every number in a findings table is recomputed from the committed evidence JSON, and the Registry survey's draw is recomputed from its seed | `tests/test_findings_evidence.py`, `tests/test_findings_registry_at_scale.py` | AUTO | Maintainer |
| Survey evidence holds no record content | Every recorded value in the Registry evidence passes the harness's identifier allow-list; no third-party host appears | `tests/test_findings_registry_at_scale.py` | AUTO | Maintainer |
| Self-description agrees with the release | The README status line, `CITATION.cff`, the `uses:` examples and this ledger carry `pyproject.toml`'s version and the CHANGELOG's dated heading for it | `tests/test_release_state.py` | AUTO | Maintainer |
| Crosswalk freshness | The crosswalk is re-read from the vendored snapshot; a re-vendoring changes it with no code edit | `tests/test_extract_crosswalk.py`; reviewed with the snapshot | AUTO + REVIEW | Maintainer |
| AI evaluation / GenAI telemetry | N/A: deterministic rule engine and deterministic extractor; no model, prompt, retrieval, embedding, or AI ranking path in either command | Dependency and import scan (zero runtime deps) | N/A | Maintainer |
| Accessibility of the playground | 0 axe-core violations of critical/serious/moderate at `wcag2a,wcag2aa,wcag22aa` and `best-practice` (heading order, landmarks, duplicate ids), in both colour schemes and in both static states; no horizontal scroll at 320 CSS px; Lighthouse accessibility 1.00 in each | `.github/workflows/accessibility.yml` (axe-core 4.13 via `web/a11y/audit.mjs`, plus Lighthouse) against `web/index.html?a11y-static` and `?a11y-static=loading` | AUTO | Maintainer |
| Keyboard and screen-reader walkthrough of the playground | Every primary task completable by keyboard; the Pyodide startup state is announced | Human walkthrough, recorded in `docs/RESPONSIBLE-TECH-AUDITS.md` section H. Still open. The startup state is now announced in four stages instead of once, carries a `<progress>` element with an accessible name, and the Validate button stays focusable and says it is not ready rather than being `disabled` and therefore untabbable; a machine can check that those exist and cannot judge whether they are an adequate account of a thirty-second wait | REVIEW | Maintainer |
| Playground performance score | Lighthouse performance >= 0.90 against the page a visitor actually gets, Pyodide boot included. Measured 1.00 on 2026-08-29 (up from 0.70), and 1.00 with 0 ms of blocking time on five runs of the gate itself on 2026-09-05 | `.github/workflows/performance.yml` builds the site the way `pages.yml` does, serves it, and runs Lighthouse against `index.html` with no `?a11y-static`, because the boot is the whole subject and a static page would score 1.00 whatever the boot does | AUTO | Maintainer |
| Playground JavaScript byte budget | N/A: 248,285 B of JavaScript against a < 204,800 B budget, and the overage is the product rather than a defect. The page runs the validator in the visitor's browser through Pyodide, a 5.6 MB WebAssembly Python runtime, because the alternative to running locally is uploading unpublished credential data to a server. No tuning brings that inside the budget and none has been attempted; per `PERFORMANCE-STANDARD` section 3 this is declared rather than run with a threshold nobody intends to meet | Not gated, deliberately. `.github/workflows/performance.yml` prints the figure on every run, counted across every resource type rather than Lighthouse's "script" type alone, so the declared overage stays visible and a further slide is legible in the log | N/A | Maintainer |

### Why the byte budget is not met, and what the score was actually failing on

The playground runs the validator in the visitor's browser through Pyodide,
which is a 5.6 MB WebAssembly Python runtime fetched from a CDN. That is the
whole point of the page: CTDL payloads most need checking while they are still
unpublished, and the alternative to running locally is asking people to upload
unreleased credential and competency data to somebody's server. No amount of
tuning brings a 5.6 MB runtime inside a 204,800 B script budget, and none has
been attempted.

**What the score was failing on was not the bytes.** Measured on 2026-08-29,
one machine, one Chrome, minutes apart:

| | Published page (before) | Local, before | Local, after |
|---|---|---|---|
| Lighthouse performance | 0.70 | 0.70 | **1.00** |
| Total blocking time | 8,020 ms | 7,710 ms | **0 ms** |
| Time to interactive | 9.2 s | 8.7 s | **1.0 s** |
| First contentful paint | 0.9 s | 0.8 s | 1.0 s |
| Cumulative layout shift | 0 | 0 | 0 |
| JavaScript over the network | 248,183 B | 248,154 B | 248,286 B |

Every byte-weight audit scored the same before and after. What scored 0 was
total blocking time: compiling 10 MB of WebAssembly and starting CPython took
about eight seconds, and it took them on the main thread, so for eight seconds
the page could not scroll, could not take a keystroke, and could not repaint
the status line it had just changed. The 0.42 recorded here on 2026-08-15 and
the 0.70 above are the same defect measured on different hardware.

The runtime now boots on a worker thread. The download still starts on load;
what changed is where the work happens.

- **The informed wait is intact.** Deferring the download behind the Validate
  button would move 5.6 MB off the critical path and clear the score too, at
  the cost of making the first validation take tens of seconds with no
  warning. That trade is still refused. The page starts fetching immediately,
  says what it is fetching and how big it is, and shows a `<progress>` element
  that advances through four named stages.
- **The integrity pin survived the move.** Subresource Integrity is not
  defined on a worker's top-level script, so the page fetches `pyodide.js`,
  hashes it with SubtleCrypto, compares the digest to the same pinned
  `sha384-` value the `<script>` tag used to carry, and refuses to build the
  worker if they differ. `tests/test_playground_catalogue.py` fails if that
  check is removed. The policy still has no `'unsafe-eval'`: the worker is
  built from verified bytes, not from a string handed to `eval`.
- **There is still a main-thread path.** `crypto.subtle` does not exist outside
  a secure context, so a page served over plain http to another machine cannot
  hash anything and has no business building a worker out of unchecked bytes.
  That case falls back to the original `<script integrity=...>` load on the
  main thread and says so in the status line and the footer.

**The byte budget is still not met, and reporting it as met would be a lie of
classification.** Lighthouse's "script" resource type now sums to a smaller
number only because `pyodide.asm.js` is requested by a worker and lands under
a different type; the same 241 kB is still downloaded. The figure in the table
above is every JavaScript byte the page causes to cross the network, counted
by hand from the request list, so that it stays comparable to the number this
file published before.

- No advisory-mode gate is wired. `PERFORMANCE-STANDARD` section 3 is explicit
  that a gate that cannot pass is declared N/A-with-reason, not run with
  `continue-on-error`. The ledger row above is that declaration, made
  formally rather than left as a REVIEW row nobody intends to clear.
- The figure is not left to a hand count either. `performance.yml` prints it
  on every run, summed over every resource type rather than Lighthouse's
  "script" type alone. Run against the assembled site on 2026-09-05 it printed
  **248,285 B** and **248,277 B** on two runs, within nine bytes of the 248,286 B
  counted by hand on 2026-08-29. That is the first independent confirmation
  that the hand count was right, and the mechanism that will show a slide
  rather than leave one to be noticed.
- The numbers above are local measurements against a local server, except the
  runner row, which is the gate's own first run. The published page still has
  to be re-measured after this deploys; the blocking-time figure should carry
  over, since it is main-thread work rather than latency, and the paint figures
  will not.

### The score is gated now, and the threshold is measured rather than assumed

`.github/workflows/performance.yml` runs Lighthouse against the real page --
no `?a11y-static` -- and fails below 0.90. Three things about that were settled
by measurement rather than by argument, on 2026-09-05, one machine, one Chrome:

| Build | Performance | Total blocking time |
|---|---|---|
| Unmodified, five runs | 1.00 every time | 0 ms every time |
| Boot forced back onto the main thread | **0.70** | **10,210 ms** |
| Unmodified, on the GitHub runner | 1.00 | 20 ms |

- **The gate catches the regression it exists for.** The second row is one edit
  (`if (false && window.Worker && ...)`) and nothing else, and it is the
  failure this whole section is about. It fails a 0.90 floor by a wide margin,
  and it was watched failing before the gate was trusted to pass.
- **The threshold stays at the standard's 0.90 rather than the 1.00 those five
  runs clear.** The accessibility row enforces the higher bar it clears, on the
  principle that a repository clearing a higher bar should hold it, and that
  principle does not transfer — not because this page is worse, but because the
  two scores are different kinds of number. Lighthouse's accessibility score is
  a discrete rule set: 1.00 means no rule failed, and the same page scores the
  same every time. Performance is a weighted function of continuous timings
  measured on a shared runner, so a 1.00 floor means any single audit slipping
  out of its perfect band fails the merge — and on a page that compiles 10 MB
  of WebAssembly, blocking time is exactly the audit that will. Two figures say
  so rather than one assertion: a sixth local run, against a build of this page
  differing only by four `<meta>` tags in the head, scored 0.99 on 105 ms of
  blocking time; and the third row above is the gate's own first run on a
  GitHub runner, which read 20 ms where an idle ten-core laptop read 0 ms
  five times in a row. Both scored 1.00. Neither would have been safe under a
  ceiling tight enough to be worth setting.
- **The timing audits are printed, not gated,** for the same reason and one
  more. Blocking time read 0 ms five times and 105 ms once, against a
  regression mode of 10,210 ms: a tight ceiling would fail for reasons that
  have nothing to do with the page, and a loose one would say nothing the score
  does not, since the score collapses to 0.70 exactly when blocking time blows
  up.
- **This job depends on cdn.jsdelivr.net, and `accessibility.yml` deliberately
  does not.** The static states exist so that an accessibility merge does not
  wait on a CDN, and the boot adds no markup a scanner has not seen. For
  performance the boot is the subject: `?a11y-static` fetches nothing and would
  score 1.00 however the boot behaves, which is a green check that cannot fail.
  The cost is paid openly instead -- a preflight reaches for the runtime first
  and, if jsDelivr does not answer, fails saying so, so that an outage is never
  read as the page having got slower.

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
