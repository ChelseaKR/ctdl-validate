# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`repair --draft`: the determined corrections, written out.** The other
  half of #64. `--suggest` names a correction beside a finding; this applies
  the ones the payload determines to a **copy**, re-validates the copy with
  the same engine, and reports what moved.

  Three properties are enforced rather than promised. **The input is never
  written** — an `--out` that is the input or any `--resolve` path is refused
  before anything is opened, compared by resolved path so `./x.json` and
  `x.json` are one file. **Nothing is invented** — every value comes from
  `suggest.py`, which reads a re-spelling out of the run's own input; this
  module adds one refusal and no candidates. **The report is what the
  validator found**, from re-running the checks over the written copy and
  comparing finding sets with `compare.finding_key`, the same identity `diff`
  uses.

  `replace` operations only, and `--patch-out` writes them as an RFC 6902
  patch. These codes are re-spellings of a value already written, so a patch
  cannot change the document's shape.

  **The refusal this adds** is about *position*, not about candidates. A
  finding names its entity by `@id` where it has one, and an `@id` may be
  declared by more than one object — a defect this tool reports
  (`ID_DECLARED_MORE_THAN_ONCE`) rather than refuses to read — so the value a
  finding is about can be written in two places. Patching one is a guess about
  which the finding meant; patching both is a second guess that they are the
  same mistake. Neither is determined, so the finding is skipped and the reason
  is printed with it, as `suggest.py`'s refusals are.

  **A draft can be honest and still read worse**, and the acceptance case for
  it is a real payload rather than a contrived one. A `ceterms:ownedBy` written
  as a bare CTID is `REF_BARE_CTID`/WARNING; the correction is the `@id` of the
  entity declaring that CTID. Once the reference resolves, the range check can
  see what it points at — a `ceterms:Certification` where `ceterms:ownedBy`
  requires an organization — and raises the ERROR the unresolvable reference
  had been hiding. `resolved: 1, introduced: 1`, and the copy is still written.
  That is why `--draft` is required rather than defaulted, and why the exit
  code is 0: the code that gates a publication is the validator's, run over
  whatever a person keeps.

  **Four of the module's own lines were unexecuted on its first complete run,
  and three were gaps rather than untested refusals**: a value inside a nested
  inline object, a bare-array document, and a `replace` on an element of a
  list. All three are shapes `graph.py` handles, and a locator that disagrees
  with the walk fails *silently* — every finding is skipped as "not in the
  source" and the draft is the document. They have tests now, and
  `repair.py` is at 100% line and branch coverage.

  Dispatched by name like `extract` and `diff`, and imported by a literal
  module path for the same reason. `ctdl_validate.__all__` is unchanged: this
  is a CLI surface, not a Python one. The default command's bytes are what they
  were, in every format, and a test asserts it.


- **`test_every_rule_fires.py` now counts the whole package, and says so.** It
  read its universe from `src/ctdl_validate/checks/*.py`, which is **28 of the
  48** finding codes `src/` constructs. The other 20 are extraction notes under
  `extract/`, and one of them — `JSONLD_CONTEXT_UNRESOLVED` — appeared in
  exactly one file in the repository: its own emit site. Deleting its branch
  left the whole suite green.

  There are now two tripwire tables. `EXTRACT_TRIPWIRES` holds **20 HTML
  pages**, one per extraction note, each run through `extract_from_html` and
  asserted to produce that note at its documented severity — the same four
  directions `TRIPWIRES` is held to, including a README table
  (*What extraction reports*) that must name exactly the codes `extract/`
  emits. `test_every_finding_code_in_the_package_is_inside_one_of_these_tables`
  walks `src/ctdl_validate/` whole and fails on any code neither universe
  covers, so a new module that starts emitting findings cannot shrink the
  denominator in silence. A module that builds a code at run time — `compare.py`
  reconstructs one from a report it is handed — carries a written reason in
  `CODE_IS_NOT_A_DECLARATION`, which fails both on an undeclared site and on an
  entry that no longer exempts anything.

  The census (`28 of 28`, `20 of 20`, `48 of 48`) is printed by
  `tests/conftest.py` on every run, passing or failing. A green line that does
  not state its denominator is how this went unnoticed.

- **`--suggest`: the correction, where the payload determines it.** Four codes
  name a defect whose repair is not a search — the corrected value is already
  written in the run's own input. `CTID_UPPERCASE` offers the same CTID in
  lower case; `CTID_URI_MISMATCH` offers the CTID this entity's own `@id`
  already carries, or, on the `@graph` envelope's own `@id`, the envelope URI
  re-spelled with the payload's one declared CTID; `REF_BARE_CTID` offers the
  `@id` of the entity in this run that declares that CTID; and
  `ISPARTOF_FRAMEWORK_MISMATCH` offers the `@id` of the one
  `ceasn:CompetencyFramework` in reach. Candidates come from the payload or
  from a `--resolve` document. No CTID is minted, no language is guessed, no
  literal becomes an IRI, and no model is involved.

  **What is refused matters more than what is offered**, so the refusals are
  data with a written reason rather than an omission. `CTID_BARE_UUID` and
  `REF_BARE_UUID` are never suggested for: prefixing the UUID with `ce-` would
  produce a well-formed CTID, which is precisely the claim the finding
  disputes. `LANGUAGE_MAP_EXPECTED` is never suggested for, because wrapping a
  literal needs a language tag the document does not supply. And no
  UNVERIFIABLE finding of any code is, because a candidate computed from the
  payload cannot settle what the payload cannot settle. `suggest.py`'s
  `NEVER_SUGGESTED` carries each reason, the suite asserts that set is disjoint
  from the suggesters and that both name codes the check modules can still
  emit, and `docs/API.md` states every entry.

  Where the run holds **more than one** candidate — two declared CTIDs under a
  graph URI, two frameworks in reach — nothing is offered. A guess dressed as a
  determination is worse than silence, because a suggestion is the one part of
  a validator's output a reader is inclined to apply without re-reading the
  finding.

  Off by default, and additive when on: it runs after `finalize`, so it cannot
  change which findings there are, their order or their identity, and with the
  flag absent the text, JSON and SARIF bytes are what they were. In SARIF the
  candidates ride in each result's `properties` bag rather than in `fixes`,
  which wants a source region this tool does not yet report (#66) — a `fixes`
  entry with no region would be a repair a consumer cannot apply.

  Part of #64; `repair --draft`, the other half of that issue, is not in this
  change and the issue stays open for it.

### Changed

- **Report schema 1.1.0 → 1.2.0**, a minor bump: a finding may now carry a
  `suggestions` array, which an existing consumer may ignore. It is written
  **only** when `--suggest` derived at least one, and the schema declares
  `minItems: 1` so an empty array is unwritable rather than merely unwritten —
  "nothing was derived" and "nothing was asked" are both the absence of the
  key, and neither is ever spelled as a list of none. `tests/schema_check.py`
  gained `minItems` enforcement, because a subset checker that skipped it would
  have been a gate that could not fail on the half of the constraint that
  matters.

- **`docs/API.md`**: `validate_document` gains a keyword-only `suggest`
  parameter defaulting to `False`, and `Finding` gains a `suggestions` field
  with a default. Both are backwards compatible and both are pinned in
  `tests/test_public_api.py`, where `suggestions` is now the single named
  exemption from "no field of a Finding is optional" — it is derived rather
  than reported, no check ever constructs it, and a second exemption has to be
  as deliberate as this one.

### Fixed

- **`diff`'s text report announced a change it could not show.** A finding is
  the same finding across two runs when its code, entity, property and rule
  citation match, so what a `changed` pair differs on is its severity, its
  value or its **message** — and the README says so in terms. The text report
  printed one line about a changed pair, `was: <value> / <severity>`, and
  `_line` deliberately omits the message. A pair that differed **only in its
  wording** therefore rendered as a heading saying something changed followed
  by two identical strings, with neither message anywhere on the page.

  That is the ordinary case for this verb rather than an exotic one. The
  header note beside it says a finding "may have appeared or disappeared
  because the tool changed", and a reworded message under an unchanged
  identity is what a tool-version bump most often produces. Reproduced against
  `origin/main` before the fix, on two saved reports differing in one
  message: `changed: ... (1)`, then `was: ce-B55F88E3-… / WARNING`, with the
  new wording and the old both absent.

  The report now names each field that actually differs, on both sides
  (`message now:` / `message was:`), and names only those, so the reader no
  longer has to work out which half of `a / b` moved. The set of fields it can
  name is **derived from the `Finding` dataclass** rather than listed:
  `message` was the field this report could not show, `suggestions` was added
  to `Finding` later and would have been the next one, and
  `test_every_field_a_changed_pair_can_differ_on_is_named_by_the_report`
  fails if the identity fields and the reported fields ever stop accounting
  for the whole record between them.

  The whole `changed` and `moved` rendering had **never executed** — 0 of the
  branch, in a module at 87% — which is how a report that shows nothing sat
  beside a test file asserting the comparison in detail.

- **`provenance_notes` carried a snapshot guard that could not fire.** A side
  is stamped either "not recorded in a saved report" or the running process's
  own `rules.RETRIEVED`, so two *known* snapshots were one module constant
  read twice and `before.snapshot != after.snapshot` was unreachable. It read
  as a provenance check and was a dead branch. Removed, with the reason in the
  docstring and the condition that would bring it back written as a test:
  `test_a_validated_side_is_always_stamped_with_the_running_snapshot` fails on
  the day a saved report carries its own snapshot — `snapshot.identity()` is
  already in every SARIF log and is what a `--format json` report would have
  to grow — which is the day the note has a real question to answer.

- **The Action treated a severity it did not know as a count of zero, and
  annotated it as a notice.** `docs/API.md` permits `Severity` to gain a member
  within a major version and says a consumer "must not treat an unknown
  severity as a pass". `tools/action_runner.py` did exactly that, in two places
  at once: `validate_one` folds only the four names in `SEVERITIES` into
  `totals`, so findings of a fifth would have been counted by **no** `fail-on`
  threshold and the run would have exited 0 with them in the report; and
  `report_findings` mapped it through `LEVELS.get(severity, "notice")` — the
  mildest level GitHub has — so a severity possibly graver than ERROR would
  have rendered as an informational annotation.

  Both were reachable without any change this script would otherwise have
  noticed, because adding a severity is a minor bump and the runner accepts
  later minors of the same major on purpose.

  This is the same defect as the `summary.get(severity, 0)` fold removed on
  2026-09-06, said the other way round: a count that is not there is not a
  count of none, and **a count this action does not know how to gate on is not
  a count of zero either.** `describe_unreadable` now refuses a report carrying
  an unrecognised severity — in a finding or as a summary key — and the run
  exits 2 rather than gating on a subset of what was reported. The annotator's
  fallback level moved from `notice` to `error`.

  Not live: the tool has emitted exactly four severities in every release. The
  hole was in what would happen the first time it did not. The identical hole
  was in `oscal-validate` and is fixed there in its own pull request.

- **A document with nothing in it this tool checks reported as a clean
  payload.** `ctdl-validate` reads terms in the `ceterms:` and `ceasn:`
  namespaces. A document declaring none of them trips no rule, which is
  correct — and the report of such a run was **byte-identical** to the report
  of a clean CTDL payload: `0 finding(s): 0 ERROR, 0 WARNING, 0 INFO, 0
  UNVERIFIABLE`, exit 0.

  Measured 2026-09-07 against this repository's own files: `package.json`,
  `tsconfig.json`, `{}`, `[]`, `src/ctdl_validate/report.schema.json` and the
  vendored `vendor/ctdl/context.json` each produced exactly that report. The
  sibling tool disagrees — `oscal-validate` exits 2 on the same input with "no
  OSCAL model root found" — so the two validators did different things with a
  file that is not theirs.

  It matters most where issue #63 wants to put this tool. A `pre-commit` hook
  declaring `types: [json]` hands the validator every JSON file in a
  repository, and a wall of clean reports over files that are not CTDL reads
  as a passing gate. A `files:` pattern narrow enough to avoid that can just as
  easily match nothing in a user's repository, which is the same failure
  wearing the opposite coat. Neither is fixable by choosing a better pattern;
  the report had to be able to say it checked nothing.

  So it does. The JSON report gains `document`, with `entities` and
  `checked_entities`, and the text report says in words that nothing was
  checked when that is the case. `report_schema_version` moves **1.0.0 →
  1.1.0**: a key was added that an existing consumer may ignore.

  Two decisions inside that are deliberate. The **exit code does not move** —
  `docs/API.md` pins exit 2 for input that could not be read, and a document
  that parses is not that. And the counts are `integer` **or `null`**, because
  a caller rendering findings it assembled by hand has no document to measure;
  writing `0` there would be this same defect pointing the other way, an
  unmeasured scope reading as "nothing was checked". `null` is not zero and
  the schema says so.

  `tests/schema_check.py` gained support for a `type` union to enforce that,
  and still raises on a type name it does not implement: the union is a union
  of names it knows, not an escape from having to know them.

- **The full-history secret scan could not fail on a credential that had been
  revoked.** `trufflehog.yml` ran `--only-verified`, which reports a finding
  only when TruffleHog authenticates the credential against the live service.
  A credential that leaked and was then revoked -- the normal end state of a
  real incident, and the exact case a scheduled history sweep exists to catch
  -- answers "no", and TruffleHog files that answer under `unverified`. So the
  sweep was structurally incapable of failing on the thing it exists for, and
  it went green for it. Measured on a throwaway clone with a real-shaped AWS
  key planted in one commit and deleted in the next: `--only-verified`,
  `--results=verified` and `--results=verified,unknown` all exited 0 reporting
  nothing; `--results=verified,unknown,unverified` exited 183 reporting it.

  The scan now runs `--results=verified,unknown,unverified`. This repository's
  entire history was re-scanned under the widened tier before the change and
  reported nothing, so no allowlist was needed and no false positive was
  traded in. The existing `--exclude-detectors=Lob` exclusion is kept: it was
  re-measured and still suppresses only pytest function names.

  The step also had no `version:` input. That input is what selects the
  scanning binary (`ghcr.io/trufflesecurity/trufflehog:${VERSION}`) and
  defaults to `latest`, so the SHA pin on `uses:` pinned only the wrapper and
  the sweep silently tracked whatever upstream published last. It is now
  pinned to 3.97.1, the release the `uses:` SHA names.

  `tests/test_secret_scan_tiers.py` fails if any lane drops the `unverified`
  tier, reintroduces `--only-verified`, loses `fetch-depth: 0` or `path: ./`,
  or lets the pinned ref and the `version:` input name different releases.

### Added

- **A `pre-commit` hook**, which completes issue #63. `.pre-commit-hooks.yaml`
  offers one hook, `ctdl-validate`, entered through a new
  `ctdl-validate-pre-commit` console script.

  A separate script rather than a flag on `ctdl-validate`, because pre-commit
  appends **every** matching staged path to one invocation and the CLI
  validates exactly one document -- `entry: ctdl-validate` would have exited 2
  with `unrecognized arguments` the first time a contributor staged two
  payloads. That is the same division `tools/action_runner.py` states for
  GitHub Actions: the CLI is the gate over one document, and expanding a set
  and collapsing its exit codes is somebody else's job. A test pins the CLI's
  refusal of a second file, so folding the two together stays a deliberate
  act.

  The hook declares `types: [json]` and **no** default `files:` pattern. Both
  halves are deliberate, and the reason is the entry below this one: pre-commit
  hands the hook every staged JSON file, most repositories hold a lot of JSON
  that is not CTDL, and until 2026-09-07 a run over `package.json` was
  byte-identical to a run over a clean payload. Shipping a narrow default
  pattern instead only trades that for a pattern that can match nothing in a
  user's repository, and a gate that ran over zero files reports success
  exactly as loudly. Neither is fixable by choosing a better pattern, so the
  hook counts three outcomes apart and prints all three -- **checked**, **not
  CTDL**, **unreadable** -- names every file in the second group without
  giving it a report of its own, and, when the first group is empty, says in a
  sentence that the run is not evidence about any payload. It still exits 0
  there: failing every commit in a repository that merely holds JSON would be
  absurd, and the sentence is the honest thing, not the exit code.

  An unreadable staged file exits 2 even when every other file is clean, which
  is the posture the Action already takes -- a gate that could not read its
  input is not a gate that passed. `--resolve` works as it does everywhere
  else.

  CI runs `pre-commit try-repo` against this repository's own fixtures in all
  three directions, because neither the unit tests nor the assertions over
  `.pre-commit-hooks.yaml` can tell you that pre-commit itself can build the
  environment, find the console script and select the files.

- **SARIF 2.1.0 output, and a `sarif-file` input on the Action** (part of
  issue #63; the pre-commit hook it also asks for is not in this change),
  ported from `oscal-validate`'s renderer.

  `ctdl-validate <file> --format sarif` writes a SARIF 2.1.0 log of the same
  findings the JSON report carries, in the same order, with the same citation
  on each. The severity contract survives the conversion, which is the part
  worth stating: ERROR and WARNING are `kind: fail`, INFO is
  `informational`, and UNVERIFIABLE is `kind: open` -- SARIF's own word for
  "evaluated and not settled" -- at `level: note`. No result is ever
  `kind: pass`. The specification's prose would put a non-`fail` result at
  `level: none`; GitHub code scanning renders only `note`, `warning` and
  `error`, so `level: none` would make every UNVERIFIABLE finding vanish from
  the place the format is most often read, which is the absence-as-pass this
  tool exists to refuse. The reasoning is in `src/ctdl_validate/sarif.py`.

  `tool.driver.properties.vendoredSnapshot` carries the snapshot's retrieval
  date and the SHA-256 of all four vendored files, computed at run time from
  the bytes the run actually read rather than transcribed from `SOURCES.md`.
  A code-scanning alert outlives the checkout that produced it, and
  "ctdl-validate 0.2.1 said so" does not identify the encoding a verdict was
  made against -- which matters here more than most places, because
  `TERM_UNSTABLE` and `CONCEPT_OUTSIDE_SNAPSHOT` exist precisely because CTDL
  moves. `tests/test_sarif.py` asserts the identity covers every file under
  `vendor/`, and that altering a vendored file's bytes moves its digest.

  `action.yml` gains `sarif-file`, and `tools/action_runner.py` merges the
  documents into **one** SARIF run rather than one run each, because GitHub
  accepts at most twenty runs per uploaded file and a publication set of
  twenty-one payloads is an ordinary set. The merge is
  `ctdl_validate.sarif.merge_logs`, not a second implementation in the
  runner: merging rules re-decides a code's `helpUri` when two payloads cite
  it from different encodings, and that is a rendering decision.

  The file is written only when every document produced a SARIF run whose
  result count equals its own JSON summary; otherwise the run exits 2 and
  writes nothing. `upload-sarif` treats an upload as the complete picture and
  resolves any alert missing from it, so a SARIF file that had lost a
  document's findings would not merely under-report -- it would close real
  alerts as fixed. That is the same absence-published-as-a-measurement the
  report-shape check added on 2026-09-06 was written for, one layer out.

  Also pinned: `action.yml` and the runner must read the same `CTDL_*`
  environment. A renamed input does not fail -- it arrives as an empty string
  and the feature it controls silently does nothing.

  `jsonschema` joins the development group, used by the SARIF suite alone to
  validate the log against the vendored OASIS schema offline. The report
  schema is still checked by `tests/schema_check.py`; the SARIF schema is
  draft-04 and far outside the subset that file enforces by hand, and a
  checker that skipped the keywords it does not implement would be the very
  thing `schema_check.py` exists to refuse.

- **`ctdl-validate diff`: what changed between two runs** (issue #61), in
  `src/ctdl_validate/compare.py` and `diff.py` (both new), `cli.py`,
  `tests/test_diff.py` (new) and the README. Each side is a CTDL payload,
  validated on the spot with its own resolve set, or a saved `--format json`
  report. `--format json`; exit 0 either way, with `--fail-on-new` to gate on
  an ERROR that is present after and absent before.

  This repository already computed this by hand every time a rule changed --
  the README's "36 of 120 documents failing became 0, as all 38
  `RANGE_VIOLATION` findings became `CONCEPT_RANGE_CONFLICT`" is a diff
  between two runs, produced once and then typed.

  **A removed finding is not called a resolved one, anywhere in this verb.**
  Two finding lists cannot tell a repair from a run that read a different
  payload, used a different resolve set, or could not get far enough to report
  anything -- an empty second side is exactly what a truncated or failed run
  produces. The verb says *removed*, and prints what that is worth beneath the
  summary. `Comparison` has no field named `resolved`, and a test holds that.

  Displacement is reported rather than buried: a re-minted CTID or a
  renumbered blank node shifts every entity identifier under it, and reporting
  that as a wall of removals and additions hides whatever really changed. A
  finding matching on code, property, value and rule at a different entity is
  *moved* -- but only where exactly one was removed and exactly one added
  under that key. Where several were, the pairing is declined and the key is
  printed so the reader knows it was declined rather than missed.

  A saved report records the tool version and the report schema version and
  nothing about which vendored CTDL snapshot produced it, so the header says
  that rather than letting the silence read as agreement.

  The design is `oscal-validate`'s `compare` module, which shipped there in
  its PR #78. The two validators publish one report shape and now describe a
  change to it the same way; what differs is this tool's own -- a finding is
  located by its entity rather than by a JSON pointer.

- **ADR-0004's additive property is now checkable in one line.** A diff
  between an unresolved and a resolved run must contain no ERROR about
  something the unresolved run had no target for, and
  `test_resolution_is_additive_a_resolved_run_introduces_no_error_the_other_lacked`
  asserts exactly that, with a control alongside it: a fabricated
  non-additive run fails the same check, so a green result is not just the
  fixture happening to add nothing.

### Changed

- **The default path no longer loads the code that fetches.** `cli.py`
  imported `ctdl_validate.extract.command` at module scope, so every
  validation run loaded the extraction and fetching modules on its way past.
  Nothing was ever fetched -- `tests/test_offline_guarantee.py` takes the
  socket away and the validator still runs -- but "the default path does not
  load the code that fetches" is a stronger and more checkable claim than "the
  code that fetches was not called". `extract` and `diff` are now both
  dispatched by name and imported only then, by a literal module path, and a
  fresh-process test asserts that running `diff` loads no `extract` module.

- **A versioned, published schema for the JSON report, and a named public
  library API** (issue #65), in `src/ctdl_validate/report.schema.json` (new,
  shipped as package data), `report.py` (new), `findings.py`, `cli.py`,
  `__init__.py`, `tools/action_runner.py`, `docs/API.md` (new),
  `tests/schema_check.py`, `tests/test_report_schema.py` and
  `tests/test_public_api.py` (all new). `--format json` is parsed by the
  Action, by the playground through Pyodide, and by the Registry survey
  harness, and its shape was defined only by the function that wrote it.

  Every report now carries `report_schema_version`, and
  `ctdl-validate --report-schema` prints the JSON Schema (draft 2020-12) it
  conforms to. The schema version moves independently of the tool version, and
  `docs/API.md` says which kind of change moves which part of it. Every report
  the suite produces is validated against the shipped schema, including the
  CLI's own output over a fixture that fails.

  **The Action was reading an absent count as zero.**
  `tools/action_runner.py` folded its totals with
  `int(summary.get(severity, 0))`, so a summary that had lost a key -- renamed
  in a later version, or truncated -- contributed nothing and the gate passed
  clean. That is an absence published as a measurement, in the tool whose
  purpose is to refuse exactly that. It now checks the shape it is about to
  read, including the report's declared schema major, and exits 2 with an
  annotation saying what was missing rather than gating on a partial report.
  Five tests hand it a deliberately incomplete report through a stub CLI; all
  five go red against the previous reading, and a sixth passes a whole report
  through the same stub so the harness cannot pass for the wrong reason.

  The conformance checker is `tests/schema_check.py`, about 130 lines of
  stdlib, because the default path has no runtime dependency and the check
  should not add one. It **raises on any JSON Schema keyword it does not
  implement** rather than skipping it: a subset checker that ignores what it
  does not know is a gate that cannot fail on the part of the contract it
  never learned, which is the same defect one level up.

  The playground is the second consumer of this shape in a second runtime. It
  builds no report of its own -- its Download button hands over the output of
  the same `render_findings_json` -- and two tests parse the page's embedded
  Python to hold that property, so the download carries
  `report_schema_version` for the same reason the CLI does.

  `docs/API.md` names the seven public symbols with their exact signatures and
  a SemVer stability promise; `tests/test_public_api.py` pins those signatures
  and the fields of `Finding` and `Rule`. No version was bumped: this is
  additive, and the release itself is issue #52's, which is the owner's.

- **`pypi-publish.yml` verifies the release tag's signature before anything
  runs.** `release.yml` has verified tags since it was written, through the
  shared `ChelseaKR/.github` release-authorize workflow. `pypi-publish.yml`,
  the path an actual PyPI upload goes through, did not: a published Release or
  a `workflow_dispatch` handed it a ref and it built and uploaded that ref. The
  version check it did run compared the ref's `pyproject.toml` against the
  ref's own tag name, which two arbitrary refs can agree about perfectly well.

  A `verify-tag` job now runs first. It resolves the tag from the event,
  requires an annotated tag object whose SSH signature verifies against the
  committed `.github/allowed_signers`, and requires that tag to name the commit
  the run is building. `verify`, `publish` and `verify-published` all wait for
  it, and the first two check out the verified commit rather than re-resolving
  the event ref. release-authorize could not simply be reused: it requires its
  caller to be dispatched from `main`, and a published Release is dispatched
  from a tag, so this runs the same check as a committed script against the
  same allowed-signers file.

  Nothing is grandfathered. `v0.1.0`, `v0.2.0` and `v0.2.1` are all signed
  annotated tags that verify against the committed key today, so
  `GRANDFATHERED_TAGS` is empty and no release is exempt. The exemption path is
  still exercised against a throwaway tag, because an empty list nothing runs
  is indistinguishable from a feature that stopped working, and the list may
  hold only literal `vX.Y.Z` names: `v*` fails the gate rather than exempting
  every release that has not happened yet.

  `tests/test_release_tag_gate.py` applies `tests/test_break_the_gate.py`'s
  discipline to the workflow. It builds a throwaway repository with throwaway
  keys and runs the committed script against tags that are unsigned,
  lightweight, signed by a key nobody trusts, absent, and correct but naming a
  different commit than the one being built. Replacing the script with
  `exit 0` fails twelve of its cases.

- **The playground lists every rule this build can report, and states nothing
  about any of them.** For a tool whose whole argument is that every finding
  cites published text, the page never showed the rule set: three samples, one
  textarea, one button. It now derives the list. One document per finding code
  ships in the page, the validator is run over each in the browser, and each
  row is that run's own output, so the severity, the wording and the citation
  are this build's rather than a description of it. The list of codes is not
  written down anywhere on the page either: the embedded Python walks the AST
  of the check modules inside the wheel it just unpacked, which is the same
  scan `tests/test_every_rule_fires.py` uses. Every row carries a button that
  loads the payload that produced it, which is also the answer to three
  samples being too few to explore twenty-three rules.

  `tests/test_playground_catalogue.py` is what keeps it derived. It reads the
  page's two data blocks, *executes the page's own Python* rather than a
  second copy of the same logic, and fails in five directions: a code with no
  document, a document filed under a code the source no longer emits, a
  document that stops producing its code, the page's scan disagreeing with the
  suite's, and the static accessibility fixture naming a rule the page ships
  no payload for. Each was broken on purpose and watched go red.

- The playground reaches `--resolve`. A second payload box supplies documents
  a run can resolve references against, which is the difference between "this
  reference points at something I cannot check" and "this reference points at
  an entity of the wrong class". Until now the page could not reach that
  distinction at all, and `REF_RESOLVED_SUPPLIED` was a rule the browser had
  no way to produce.

- The report can leave the page. Copy it in the layout the command line
  prints, download it as the JSON `--format json` writes, or copy a link that
  carries the payload. The first two call `render_findings_text` and
  `render_findings_json` through Pyodide rather than reformatting anything in
  JavaScript, so what you get is byte for byte what the CLI would have
  printed. The link puts the payload in the URL fragment, which browsers never
  send to a server -- the only encoding that keeps this page's promise -- and
  the confirmation says in as many words that the link is therefore a copy of
  the payload. It refuses above 8,000 characters and gives the number.

- A short lede for people who have not met CTDL, and what the four severities
  mean, on the page rather than only in the repository README.

- `?a11y-static=loading` renders the startup state for the accessibility gate,
  which now audits it. `docs/RESPONSIBLE-TECH-AUDITS.md` section H recorded the
  loading state as unscanned residual risk while the page spends tens of
  seconds in it.

- **Something now catches the playground's performance score regressing.**
  Moving the Pyodide boot to a worker took the score from 0.70 to 1.00 and
  total blocking time from 8,020 ms to 0 ms, and nothing held the result:
  `docs/ROADMAP.md` said so itself, and the row stayed REVIEW because a score
  that is met is not a score something would catch sliding back.
  `.github/workflows/performance.yml` runs Lighthouse against the real page --
  no `?a11y-static`, because the boot is the whole subject and a page that
  boots nothing would score 1.00 however the boot behaves -- and fails below
  0.90.

  The threshold was measured rather than assumed. Five unmodified runs on
  2026-09-05 scored 1.00 with 0 ms of blocking time; forcing the boot back onto
  the main thread with a single edit scored **0.70 with 10,210 ms**, so the gate
  was watched failing for the reason it exists before it was trusted to pass.

  The floor stays at the standard's 0.90 rather than the 1.00 those runs clear,
  which is the one place this departs from the accessibility gate. That one
  enforces the 1.00 it measures because Lighthouse's accessibility score is a
  discrete rule set — 1.00 means no rule failed, and the same page scores the
  same every time. Performance is a weighted function of continuous timings on
  a shared runner, so a 1.00 floor would fail the merge on any audit slipping
  out of its perfect band, and on a page compiling 10 MB of WebAssembly that
  audit is blocking time. The timing audits are printed rather than gated for
  the same reason.

  This job depends on cdn.jsdelivr.net, where `accessibility.yml` deliberately
  does not, and pays for it openly: a preflight reaches for the runtime first
  and fails naming the CDN, so an outage is never read as the page having got
  slower.

### Changed

- **The Pyodide runtime boots on a worker thread.** It used to boot on the
  main thread, so for about eight seconds the page could not scroll, could not
  take a keystroke, and could not repaint the status line it had just changed.
  Lighthouse on the published page: total blocking time 8,020 ms, time to
  interactive 9.2 s, performance 0.70. After: **0 ms, 1.0 s, 1.00**, measured
  on one machine minutes apart. The download still starts on load; deferring it
  behind the Validate button would have cleared the score too and would have
  replaced a wait you were told about with one you were not.

  Subresource Integrity is not defined on a worker's top-level script, so the
  page fetches `pyodide.js`, hashes it with SubtleCrypto, compares it to the
  same pinned `sha384-` digest the `<script>` tag carried, and builds the
  worker only from matching bytes. The policy still has no `'unsafe-eval'`.
  Where `crypto.subtle` does not exist, meaning any origin that is not a
  secure context, the page falls back to the original main-thread load with
  the `integrity` attribute and says so in the status line and the footer.

  The script *byte* budget is still not met and still declared. Lighthouse's
  "script" resource type now sums to less only because a worker requested most
  of the runtime; `docs/ROADMAP.md` counts every JavaScript byte crossing the
  network by hand, 248,286 B against a 204,800 B budget, so the figure stays
  comparable to the one it published before.

- The startup announces four named stages instead of one sentence, and carries
  a `<progress>` element with an accessible name. The Validate button is no
  longer `disabled`: a disabled button is not focusable, so a keyboard user
  tabbing the page during the wait never met the control at all. It stays
  focusable, says `aria-disabled`, and queues -- pressing it during startup
  runs the validation the moment the runtime is ready.

- `web/a11y/audit.mjs` audits both static states, checks the rule catalogue
  renders at all four severities as well as the report, and fails when a
  control the post-run state adds is missing or invisible. That last one is
  not an accessibility rule; it is the gate refusing to grade a page missing
  the parts it was extended to grade. Measured after the change: 0 violations,
  0 incomplete, 42 rules passed in the post-run state and 39 in the startup
  state, in both colour schemes, Lighthouse accessibility 1.00 in each.

- `tests/test_playground_catalogue.py` also holds the page's network posture,
  which nothing checked before: the Content-Security-Policy directive by
  directive, the absence of `'unsafe-eval'`, and the absence of `sendBeacon`,
  `XMLHttpRequest`, `WebSocket`, `EventSource` and `<form` anywhere in the
  page. The policy is the control that keeps a payload in the browser, and a
  control nothing checks is a comment.

### Fixed

- **Four places said CTDL ranges `ceterms:isSimilarTo` on `rdfs:Resource`
  alone. It declares 83 range terms.**
  ([#60](https://github.com/ChelseaKR/ctdl-validate/issues/60)) The README's
  conflict 6, the `[Unreleased]` "Changed" entry for the universal-range fix,
  `schema.py`'s `UNIVERSAL_RANGE_TERMS` comment and the 2026-08-21 survey
  finding all stated that `ceterms:hasMember`, `ceterms:isSimilarTo` and
  `owl:sameAs` declare `rdfs:Resource` as their **whole** range. That is true
  of two of them. `ceterms:isSimilarTo` declares 84 `schema:rangeIncludes`
  entries -- 83 distinct, CTDL listing `ceterms:CredentialType` twice -- of
  which `rdfs:Resource` is one and the other **82 are real classes** (76
  `ceterms:`, 3 `ceasn:`, plus `qdata:Metric`, `skos:ConceptScheme` and
  `xsd:anyURI`). All four statements are corrected, in place and dated.

  The consequence is real: `range_is_universal` tests whether `rdfs:Resource`
  appears *anywhere* in a range, and `checks/domain_range.py` consumes that as
  an unconditional early return, so `isSimilarTo` is exempted too and CTDL's
  published 82-term union is never enforced. All four dispositions
  `_range_findings` can reach sit after that return.

  **Whether that is right is left open, deliberately, as the maintainer's
  call.** Both readings are defensible -- a `schema:rangeIncludes` union
  containing "the class of everything" arguably admits everything, or the
  "only `rdfs:Resource`" rule the docs describe is the intended one. What is
  not mechanical is the consequence of flipping it: enforcing the 82 terms
  would raise `RANGE_VIOLATION`, an ERROR worded as a publisher's mistake, on
  the strength of an ambiguity inside CTDL's own encoding -- and that union
  reads arbitrarily from inside, admitting `ceasn:CompetencyFramework`,
  `ceasn:Rubric` and `ceasn:RubricCriterion` while excluding
  `ceasn:Competency`. This project's standing finding is that its ERRORs trace
  to the schema encoding rather than to publishers, so no check was changed
  and no finding count moved.

  What did change is that the choice can no longer move unnoticed. The string
  `isSimilarTo` appeared in no test file, and the suite passed identically
  under both candidate rules -- a gate that could not fail. Three tests now
  pin it: that exactly two properties range on `rdfs:Resource` alone and
  exactly three mention it; that `isSimilarTo` has 83 range terms with the
  `ceasn:Competency` asymmetry spelled out; and a characterisation test,
  explicitly not an endorsement, that fails if the disposition changes. The
  last was watched fail under the flipped rule.

- **A nested item that was not a property value was dropped from the extract
  with no note.** ([#57](https://github.com/ChelseaKR/ctdl-validate/issues/57))
  `microdata._top_level_elements` appended an item and stopped walking there,
  and `_properties` refuses to descend into an element carrying `itemscope`.
  So an `itemscope` *without* `itemprop`, nested anywhere inside another item,
  was reached by neither path: not a property value, so the property walk
  skipped it; inside an item, so the top-level walk never got to it.
  `rdfa.scan` had the identical shape against `typeof`/`property`.

  Per the HTML Living Standard the top-level microdata items of a document are
  exactly the item elements with no `itemprop`, *at any depth*; in RDFa 1.1,
  `typeof` without `property`/`rel` establishes a new subject wherever it
  appears. `_top_level_elements`' own docstring stated the contract -- "Item
  elements that are not themselves property values" -- and the function did
  not deliver it.

  The drop was silent in three places at once: the document lost the entity,
  the notes said nothing, and the block inventory undercounted the items it
  claimed to have found -- against `report.py`'s "notes saying what was read,
  what was dropped, and why" and README's "Under-reporting is visible in the
  notes". It was on no "Cannot, by construction" list and in no ADR, roadmap
  or expansion-plan entry.

  Both walks now continue into an item's own subtree. Nothing is read twice:
  `itemprop`/`property` decides which walk reads an element and the two
  conditions are mutually exclusive, and `_report_beyond_lite` latches after
  its first note. `<body itemscope itemtype="WebPage">` around a separately
  scoped `Course` -- an ordinary publishing pattern -- now yields both items,
  the `Course`'s properties, and the `PROPERTY_NOT_MAPPED` note its
  `courseCode` earns; measured before the fix, nesting cost a real, mappable
  CTDL entity plus that note.

  Eight tests cover both formats: a nested item, a nested item at depth inside
  a *property-value* item, a nested item read through plain wrappers, the
  block inventory's count, and a nested-versus-sibling equivalence test. Two
  are regression guards that an `itemprop`/`property`-bearing nested item is
  still a property value and not a second entity. The two coverage misses the
  issue named, `microdata.py:144-145` and `rdfa.py:173-174`, are now executed.
  Five of the eight were watched fail with the old walk restored.

  `docs/findings/2026-08-14-provider-markup-survey.md` carries a dated note
  that its item and entity counts are lower bounds for any page that nested an
  item, and have not been recomputed.

- **Check 1 never saw the `@graph` envelope's own `@id`, so a malformed
  Registry graph URI passed clean on a real Registry document.**
  ([#58](https://github.com/ChelseaKR/ctdl-validate/issues/58))
  `parse_document` took `data["@graph"]` and discarded every other top-level
  key. The envelope's `@id` never became a node, `Session` holds only the
  graph, and every check iterates `graph.nodes` -- so no check, not just
  check 1, could reach it.

  That `@id` is the one position in which a Registry *graph* URI actually
  appears in a published Registry document: in all five Registry-shaped
  fixtures in this repository, `/graph/` occurs exactly once each, always as
  the envelope `@id`. `REGISTRY_GRAPH_PREFIX` was therefore referenced only by
  `registry_uri_tail` itself, and that branch was dead against real Registry
  payloads. Two documented claims said otherwise -- README's check-1 row
  ("the tail of every Registry resource/**graph** URI") and
  `checks/ctid_format.py`'s own module docstring -- and the exclusion appeared
  in no ADR, roadmap or "not covered in v0" list.

  The envelope identifier is now kept on the `Graph` (`envelope_id`,
  `envelope_path`) and read by check 1. It is deliberately *not* added to
  `nodes`: nothing is asserted about it, so putting it there would submit an
  identifier to every check that reads types and properties.
  `REGISTRY_URI_MALFORMED` now fires on a malformed graph URI, and
  `CTID_URI_MISMATCH` fires when the graph URI names a CTID that no entity in
  the payload declares -- in either position, `ceterms:ctid` or the CTID tail
  of the entity's own Registry `@id`, since requiring `ceterms:ctid`
  specifically would report documents that are correct. Both messages name the
  envelope rather than a `@graph` index.

  The comparison is against every CTID the payload declares rather than
  against one designated "primary" entity, because the document shape does not
  say which entity is primary and guessing would invent findings the payload
  does not support. Seven tests pin it, including a guard that the fixture
  under test is still a Registry envelope and still clean unmodified; the two
  positive cases were watched fail with the envelope dropped again.

  Both published Registry surveys carry a dated coverage note: their harness
  feeds `envelope["decoded_resource"]` straight into `parse_document`, so
  their `REGISTRY_URI_MALFORMED` and `CTID_URI_MISMATCH` counts cover resource
  URIs only and have not been recomputed against this check.

- **`extract --from-file` decoded saved pages differently from fetched ones,
  and crashed on any page that was not UTF-8.**
  ([#59](https://github.com/ChelseaKR/ctdl-validate/issues/59)) The flag exists
  to make a run reproducible offline -- README's "Same *page bytes*, same
  output, byte for byte" -- but it hard-coded `read_text(encoding="utf-8")`
  while the fetch path honoured the `Content-Type` charset, then the page's
  own `<meta charset>`, then fell back to `errors="replace"` labelled
  `(undecodable, replaced)`. The same bytes therefore produced two different
  documents depending only on which path read them.

  Worse, `UnicodeDecodeError` is a `ValueError`, so the `except OSError`
  around the read did not catch it and neither did `main`'s
  `(FetchError, MarkupError, RecursionError)` handler. A saved page in any
  other encoding escaped as an unhandled traceback on Python's default exit 1
  -- which this command documents as "the page was read and produced no CTDL
  entities. Not an error; on the open web it is the common case." A harness
  reading exit codes recorded "no CTDL markup here" for a page that was never
  opened. The code for "nothing could be read" is 2.

  `--from-file` now reads bytes and decodes them through the same function the
  fetch path uses, so the markup's declared charset decides on both paths and
  undecodable bytes are replaced-and-labelled rather than fatal. The reported
  `bytes` is now the bytes read rather than the decoded text re-encoded, and
  the report names the encoding used. Every remaining unreadable-file case is
  an `OSError`, so it raises `FetchError` and exits 2.

  Six tests pin it: a `windows-1252` page read end to end, a page whose
  declared charset cannot decode its own bytes, an unreadable path exiting 2,
  and a four-way parametrized parity test asserting `--from-file` and `fetch`
  emit the identical document, blocks, notes and encoding for the identical
  bytes -- with the declared charset right, wrong, and unusable. All but the
  exit-2 guard were watched fail against the previous implementation.

- The half of the check 5 fix in [#35](https://github.com/ChelseaKR/ctdl-validate/pull/35)
  that no test held. `_asserts_back` accepts an inverse written as a nested
  object because of the identifier the object carries -- and replacing that
  comparison with "any nested object will do" left the entire suite green.
  Both directions of the same defect were therefore live: the false positive
  [#32](https://github.com/ChelseaKR/ctdl-validate/issues/32) reported was
  fixed, and the false negative that the obvious over-correction produces was
  ungated. Two cases now pin it -- a nested back-reference naming a different
  entity, and one carrying no `@id` at all -- and both fail against that
  mutation and pass against the code as written. Behaviour is unchanged; what
  changed is that the behaviour can no longer be removed silently.

- `Graph.resolve`'s docstring described its identity preference as what keeps
  a reference reached through an embedded copy off a thinner duplicate node.
  Since ADR-0005 that is no longer true: the builder merges the declarations
  and registers the nested path against the merged node, so the path fallback
  reaches the same object. The docstring now says so, and
  `test_an_embedded_copy_and_its_top_level_declaration_are_one_node` fails if
  the two ever stop agreeing.

- The `CTID_STRUCTURE` citation and the `ctid.py` module docstring put
  quotation marks around words the cited page does not say in that order.
  Both quoted "a total of 39 characters (34 hexadecimal characters and 5
  hyphens)"; the "About the CTID" page's sentence is "there are a total of
  34 hexadecimal characters and 5 hyphens for a total of 39 characters".
  Same facts, but a paraphrase was dressed as a quotation, in the one part
  of a finding that promises to be verbatim. Both now quote the sentence as
  published, re-verified against the live page on 2026-08-29 (the page still
  carries its 5/10/2024 date). The grammar itself, and every finding
  message, were already consistent with the source and are unchanged.

### Added

- The playground's head says what the page is and where it is. `web/index.html`
  carried a title and no description, no canonical, and no Open Graph or
  Twitter tags, so a search result or a share preview had one word of it. All
  of them are there now, and the description repeats the lede rather than
  claiming anything the page does not: no rule count, no conformance level, no
  coverage figure, and nothing suggesting Credential Engine has endorsed or
  published this. Every absolute URL carries `/ctdl-validate/`, because this
  page is served at a path on an origin five sibling projects share and
  `https://chelseakr.github.io/` is itself a 404.

  `web/a11y/audit.mjs` is where the check lives, extended rather than joined by
  a second workflow: it is the only merge-blocking gate pointed at this file,
  it already has the page open, and a head defect fails the same way an
  accessibility one does, invisibly. It fails on an address that drops the
  project path, on a missing description or card, on any root-relative `href`
  or `src`, on a description containing a word like "official", "endorsed" or
  "conformance", and on a description containing a figure.

- Check 9, term status: `TERM_UNSTABLE` (INFO). Both encodings carry
  `vs:term_status` on every term they declare -- 675 `vs:stable`, 478
  `vs:unstable` -- and nothing read either. A payload could have been built
  entirely from terms the vocabulary itself flags as unsettled and this tool
  would have said nothing. Terms are covered in whichever role they appear:
  as a class on `@type`, as a property key, or as a concept a scheme-bound
  property points at.

  The finding states the declaration and stops. Nothing in the four vendored
  files defines what `vs:unstable` obliges a publisher to do, so the message
  does not say the term will be withdrawn, that the Registry will reject it,
  or that the payload should change. `test_the_finding_does_not_say_what_unstable_means`
  holds the claim to that size.

  Measured against the 1,200 published Registry documents of the 2026-08-21
  survey, re-validated offline from that run's cache: 1,540 findings added
  across 710 documents, none removed, and ERROR and WARNING counts unchanged
  at 159 and 42. Two thirds of published documents use at least one term the
  vocabulary marks unstable, which is the reason this was worth reading.

  Those three roles reach 461 of the 478 unstable terms, and the README's rule
  table row says so rather than leaving 478 to be inferred. The other 17 are
  `skos:ConceptScheme` declarations (`ceterms:LifeCycleStatus`,
  `ceterms:SupportServiceCategory`, fifteen more), and a payload never names a
  scheme directly, so no document can trip them.

  Landing this found a decorative test. `test_expansion_plan.py`'s term-status
  probe was built from `ceterms:audienceLevelType` and
  `audLevel:BeginnerLevel`, neither of which the vendored encoding declares
  `vs:unstable`, so it could never have produced the finding it stood for.
  Nothing noticed, because a probe for a row claiming zero is only ever
  asserted *not* to fire: a payload that cannot fire and one the validator
  correctly ignores look identical. The probe now uses `ceterms:Collection`
  and `ceterms:lifeCycleStatusType`, and a new test reads the snapshot to
  confirm both are still declared unstable, so a re-vendoring that stabilises
  either fails loudly instead of quietly returning the probe to decoration.


- Check 8, language-map shape: `LANGUAGE_MAP_EXPECTED` (WARNING). The vendored
  contexts declare 80 terms with `{"@container": "@language"}`, 67 of which the
  schema encodings also declare as properties. The validator already read that
  declaration -- `graph.py` keeps such a value as the map it is rather than
  walking it as a nested node -- and now reports a bare literal in that
  position instead of only relying on it.

  The other half of the README's "literal datatype validation" line is
  **blocked, not deferred**, and the README now says so. The contexts declare
  87 datatype coercions, but nothing in the four vendored files defines the
  lexical space of `xsd:date`, `xsd:duration` or any other datatype: their
  only keys are RDF, SKOS, OWL, `meta:` and `vs:` terms, with no pattern or
  format among them. Writing that grammar from memory is the rule-from-memory
  the first invariant forbids, and `xsd:date` admits a timezone offset and a
  negative year, which recollection reliably gets wrong. It needs the XML
  Schema datatypes specification vendored under the existing hashing policy.

  Measured against the 1,200 published Registry documents of the 2026-08-21
  survey, re-validated offline from that run's cache: zero findings added. No
  published document puts a bare literal on a language-map property.

  The check covers 67 of the 80 declarations, not all 80, and the README's
  rule table says so on the row. It tests the property index, which carries
  the flag only for a term the *schema* encodings also declare as a property;
  the other 13 are declared in a context and nowhere else (`dct:description`,
  `meta:objectText`, `rdfs:comment`, `rdfs:label`, `skos:historyNote`,
  `vann:usageNote` and seven `qdata:` terms), and a bare literal on one of
  those is not reported. `docs/EXPANSION-PLAN.md` moves that row's "read by a
  check today" column to 67 rather than 80.


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

  The README's "not covered in v0" list did not lose its concept-scheme line;
  it was narrowed to the half the vendored bytes cannot decide. Membership is
  decided for the 456 concepts the encodings declare and for nothing else, and
  four of the 40 schemes those 48 properties name are not declared as a
  `skos:ConceptScheme` anywhere in the snapshot
  (`ceterms:IndustryClassification`,
  `ceterms:InstructionalProgramClassification`,
  `ceterms:OccupationClassification`, `qdata:CollectionMethod`), so a value
  drawn from one of them can never be more than unverifiable here.
  `docs/EXPANSION-PLAN.md` moves its first three "read by a check today" rows
  off zero and says what each of those numbers does and does not cover.

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
- `tests/test_every_rule_fires.py`, a gate that counts rules rather than lines.
  It reads every finding code out of `src/ctdl_validate/checks/` by AST, holds
  a document that trips each one, and fails in four independent directions: a
  code the source emits with no document that reaches it; a listed code the
  source no longer emits, so a stale entry cannot outlive a deleted rule; a
  code whose document does not actually produce it at the documented severity;
  and any disagreement between the source and the README's rule table. The
  third is the one that matters, because it is behavioural: every entry is a
  payload the validator is run over, not a string compared against another
  string.

  Reading the codes is by AST rather than by regex on purpose. A `[A-Z_]+` scan
  silently omits `CTID_NOT_UUIDV4`, because that code carries a digit, which is
  exactly how a rule goes missing from a list of rules.

  Broken deliberately in eight directions before being trusted, including one
  first attempt that stayed green because it corrupted the wrong one of two
  `CTID_MALFORMED` sites. `src/ctdl_validate/checks/ctid_format.py` and
  `identifier_kind.py` are now at 100% line and branch coverage.

### Changed

- A declared range naming only `rdfs:Resource` is now treated as
  unconstraining and raises nothing. RDF Schema 1.1 section 3.1 makes
  `rdfs:Resource` "the class of everything", so it excludes no entity — but no
  CTDL class reaches it by `rdfs:subClassOf`, so matching a target's declared
  classes against it rejected *every* entity instead of accepting every one.
  This affected `ceterms:hasMember`, `ceterms:isSimilarTo` and `owl:sameAs`;
  in the 1,200-document survey it produced 47 spurious range errors against a
  single published collection that listed 47 licences.

  *Correction, 2026-09-06 ([#60](https://github.com/ChelseaKR/ctdl-validate/issues/60)):
  "a declared range naming only `rdfs:Resource`" describes `ceterms:hasMember`
  and `owl:sameAs`, which name it alone, but not `ceterms:isSimilarTo`, which
  names it among 82 other real classes (84 entries, 83 distinct). The shipped
  test is membership rather than "only", so `isSimilarTo` was exempted as
  well; the corpus evidence quoted above was entirely `hasMember`. Whether
  `isSimilarTo`'s 82 terms should be enforced is open and unsettled.*

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
- Three rules fired against nothing. `CTID_MALFORMED` (ERROR),
  `REF_BARE_CTID` (WARNING) and `REF_NOT_IRI` (WARNING) were emitted by the
  check modules, named in the README's rule table, and asserted by no test in
  the suite: any one of them could have been deleted without turning a single
  gate red. The 90% coverage floor could not see it, because three missing
  rules are four missing lines out of eighteen hundred. All three were verified
  to fire correctly, so they were untested rather than broken, and each now has
  a corruption in `tests/test_break_the_gate.py`.
- `VERSION_RANGE_CONFLICT` shipped implemented and missing from the README's
  rule table, which listed twenty-one of the twenty-two codes the source can
  emit. Added, and the omission is now impossible to repeat: see
  `tests/test_every_rule_fires.py` under Added.


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
