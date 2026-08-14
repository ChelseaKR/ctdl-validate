# Responsible-Tech Audits: ctdl-validate

Project-specific findings under the portfolio Responsible-Tech Framework.
This artifact is reviewed on release; generic thresholds remain in the
portfolio standards. Last reviewed: 2026-08-14 (extraction subcommand added;
sections A, C, F revised and section G added).

## Applicability

- **A Ethics:** applies. Two harm surfaces now: false confidence in the
  validator, and fabrication in the extractor.
- **B Bias:** minimal surface; the tool applies published structural rules
  uniformly to every payload and does not rank, score, or profile. Extraction
  grades markup, never the organization that published it, and the notes name
  the missing declaration rather than the site.
- **C Privacy / DPIA:** applies in a narrow form. Validation processes only
  the local file it is pointed at, entirely in process, with no network
  calls, no telemetry, and no persistence beyond its printed report.
  Credential data can describe real people and organizations; it never leaves
  the machine the publisher runs the tool on. Extraction makes one outbound
  request the operator asked for, which is visible in the fetched site's
  logs; nothing is sent anywhere else, and the extract is written to the
  operator's own stdout.
- **D Transparency:** applies and is the design center: every finding and
  every extraction note carries the rule citation, source URL, and retrieval
  date it enforces.
- **E Accessibility:** N/A today; no graphical or web surface. Output is
  plain text (screen-reader-friendly terminal output) and `--format json`.
- **F Security:** applies; see `SECURITY.md`. Input is untrusted JSON and now
  untrusted HTML; the supply-chain controls (locked toolchain, pinned
  actions, SAST, secret scanning) are in CI.
- **G Effect on third parties:** applies, and is new. The extractor fetches
  other people's servers.
- **AI Evaluation:** N/A; no LLM or model call exists anywhere in the tool,
  in either command. AI-assisted authoring of the code is disclosed in the
  README.

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

### A2. Ethics: fabrication in the extractor

**What could go wrong?** An extractor that fills gaps produces a credential
record that reads exactly like a real one and that no provider ever claimed.
Downstream, nothing distinguishes it: a minted CTID looks like a CTID, an
inferred class looks like a declared one, and the Registry is a public record.
The failure is invisible at the point where it would matter.

**Controls.** No model call exists in the code path, so there is no
free-text generation step to review. A class or property is mapped only where
the vendored schema encoding declares an equivalence, and the note for every
unmapped term names the declaration that was looked for and not found.
`ceterms:ctid` is never generated. A literal where CTDL expects an identifier
is dropped rather than promoted. A language tag is never inferred from text.
`tests/test_extract_break_the_gate.py` feeds the extractor pages that tempt
each of these and asserts none happened, including one case that removes an
equivalence from the crosswalk and requires the mapping to disappear with it.

**Accepted cost.** Coverage is low, and on pages without structured markup it
is zero. That is stated in the README's boundary section rather than softened:
under-reporting is visible in the notes, and a fabricated credential is not.

**Review gate.** Any change that widens what extraction will assert, in
particular any inference not backed by a published declaration, requires an
ADR and a README scope update in the same PR.

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

Extraction adds exactly one outbound flow, and it runs the other way: a GET
for robots.txt and a GET for the page the operator named, carrying nothing but
the tool's own User-Agent. No payload, no telemetry, no identifier of the
operator beyond what any HTTP request carries. The site sees a request; the
operator sees the extract. Nothing is stored between the two.

## D. Transparency

The methodology, severity definitions, scope limits, and known upstream
spec conflicts are documented in the README. The vendored sources and their
hashes are in `src/ctdl_validate/vendor/SOURCES.md`. A finding without a
citation cannot be constructed in the code path: the `Finding` model
requires a `Rule`.

## F. Security

See `SECURITY.md` for the threat cases (crash outside the exit-code
contract, false clean report, snapshot tampering, a robots.txt bypass, a
fabricated assertion) and the commitments. Validation runs offline by design,
which removes the largest attack classes, and that is now enforced by a test
that removes `socket` rather than by prose. The residual surface is the JSON
parser, the HTML parser, one outbound HTTP request the operator asked for, and
the supply chain of the dev toolchain. The HTML path executes nothing and
resolves no external context or schema; nesting past 200 elements is refused
rather than absorbed.

## G. Effect on the sites the extractor fetches

**What could go wrong?** A tool that fetches provider websites can cost other
people money and attention: ignoring robots.txt, hammering a small college's
CMS, hiding behind a browser's User-Agent so an operator cannot tell who is
asking, or wandering off the page it was pointed at.

**Controls.** robots.txt is fetched before anything else and obeyed, with a
Disallow as a hard stop and no flag to override it; an unreachable robots.txt
is treated as a complete disallow per RFC 9309 2.3.1.4 rather than as
permission. The User-Agent carries the product token and a link to this
repository, so a site operator reading a log can see who called and why, and
`--contact` only adds to it. One invocation fetches robots.txt plus at most
one page, with a per-host minimum interval that a declared `Crawl-delay` can
lengthen. Redirects are followed manually, capped at five, with robots.txt
re-checked at every hop so a redirect cannot deliver the fetch to a host that
said no. Every one of these is tested against a server on localhost in
`tests/test_extract_fetch.py`, including the case where the page is never
requested at all because robots.txt said not to.

**Residual risk.** The operator chooses the URL, and a tool cannot know
whether they had a reason to. What it can do is behave the same way whoever is
driving it, and leave a log entry that says who it was.
