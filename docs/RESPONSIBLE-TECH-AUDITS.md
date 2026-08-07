# Responsible-Tech Audits: ctdl-validate

Project-specific findings under the portfolio Responsible-Tech Framework.
This artifact is reviewed on release; generic thresholds remain in the
portfolio standards. Last reviewed: 2026-08-07 (initial version).

## Applicability

- **A Ethics:** applies. The harm surface is false confidence.
- **B Bias:** minimal surface; the tool applies published structural rules
  uniformly to every payload and does not rank, score, or profile.
- **C Privacy / DPIA:** applies in a narrow form. The tool processes only
  the local file it is pointed at, entirely in process, with no network
  calls, no telemetry, and no persistence beyond its printed report.
  Credential data can describe real people and organizations; it never
  leaves the machine the publisher runs the tool on.
- **D Transparency:** applies and is the design center: every finding
  carries the rule citation, source URL, and retrieval date it enforces.
- **E Accessibility:** N/A today; no graphical or web surface. Output is
  plain text (screen-reader-friendly terminal output) and `--format json`.
- **F Security:** applies; see `SECURITY.md`. Input is untrusted JSON; the
  supply-chain controls (locked toolchain, pinned actions, SAST, secret
  scanning) are in CI.
- **AI Evaluation:** N/A; no LLM or model call exists anywhere in the tool.
  AI-assisted authoring of the code is disclosed in the README.

## A. Ethics: false confidence and false alarm

**What could go wrong?** (a) A publisher reads a clean run as "the Registry
will accept this" when the tool only checks the structural rules it lists;
(b) a spurious ERROR blocks a legitimate publication; (c) a stale vendored
snapshot silently enforces outdated rules.

**Controls.** The README's "Scope, honestly" section enumerates what v0
does not check; the severity contract reserves ERROR for violations of
cited absolute rules, WARNING for cited-but-not-absolute signals, and
UNVERIFIABLE (never gating) for anything the payload alone cannot answer;
`tests/test_break_the_gate.py` proves each claimed check actually catches
its target; vendored snapshots carry retrieval dates that appear in every
finding, so staleness is visible in the output itself, and hash tests catch
silent edits.

**Review gate.** Any change to severity semantics or to what a check claims
requires an ADR and a README scope update in the same PR.

## B. Bias and fairness

The rules come verbatim from Credential Engine's published schema encodings
and documentation; the tool adds no discretionary judgment per payload.
Where the published sources disagree with each other, the tool reports the
conflict (`RANGE_DOCS_CONFLICT`, INFO) citing both sides rather than
silently picking one. Terms outside the CTDL namespaces are explicitly not
judged.

## C. Privacy

No collection, no transmission, no retention. The DPIA-style answer is
short because the data flow is short: file in, findings out, process ends.
Findings quote payload values back to the operator (necessary for a usable
report); operators handling sensitive payloads should treat the report with
the same care as the payload. The JSON report contains nothing that was not
in the input plus the cited rules.

## D. Transparency

The methodology, severity definitions, scope limits, and known upstream
spec conflicts are documented in the README. The vendored sources and their
hashes are in `src/ctdl_validate/vendor/SOURCES.md`. A finding without a
citation cannot be constructed in the code path: the `Finding` model
requires a `Rule`.

## F. Security

See `SECURITY.md` for the threat cases (crash outside the exit-code
contract, false clean report, snapshot tampering) and the commitments. The
tool runs offline by design, which removes the largest attack classes; the
residual surface is the JSON parser and the supply chain of the dev
toolchain, both gated in CI.
