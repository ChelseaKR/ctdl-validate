# Responsible-Tech Audits: ctdl-validate

Project-specific findings under the portfolio Responsible-Tech Framework.
This artifact is reviewed on release; generic thresholds remain in the
portfolio standards. Last reviewed: 2026-08-21 (section H re-measured with
axe's best-practice rules added to the gate). Previous: 2026-08-15 (the
playground was measured for the first time; section E rewritten from N/A and
section H added).

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
- **E Accessibility:** applies. This entry read "N/A today; no graphical or
  web surface" from 2026-08-07 until 2026-08-15, while a browser playground
  was published at chelseakr.github.io/ctdl-validate/ and linked from the top
  of the README. The CLI's own surface is still plain text and `--format
  json`; the page is a human-facing HTML surface and is now gated. See
  section H.
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
conflict (`RANGE_DOCS_CONFLICT` and `CONCEPT_RANGE_CONFLICT`, both INFO)
citing both sides rather than silently picking one. The second of those was
added after validating 120 published Registry documents showed the tool
failing 36 of them on a declaration Credential Engine's own documents
contradict: reporting a publisher's correct work as a defect is the same
harm as missing a real one, in the direction that is harder to notice.
Terms outside the CTDL namespaces are explicitly not judged.

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

## H. Accessibility of the playground

**What could go wrong?** Two things, and only one of them is about markup.

The first is the ordinary one: a page that a screen-reader or keyboard user
cannot operate, or that a low-vision user cannot read. The second is specific
to this page. The validator does not exist until a 5.6 MB WebAssembly runtime
finishes downloading, which takes tens of seconds on a cold cache, and during
that time the Validate button is disabled and nothing visibly happens. A
person using a screen reader meets that wait before they meet the tool.

**What was measured, on 2026-08-15.** axe-core 4.13 against
`web/index.html?a11y-static` at `wcag2a,wcag2aa,wcag22aa`, in both
`prefers-color-scheme` settings: **0 violations, 0 incomplete, 25 rules
passed** in each. Lighthouse: **accessibility 1.00**, both locally and against
the published page. Reflow at 320x256: clean, **after a fix**.

**Re-measured on 2026-08-21, with a wider rule set.** The same axe-core 4.13
run with the `best-practice` tag added to the three WCAG tags, in both colour
schemes: **0 violations, 0 incomplete, 39 rules passed** in each. The added
rules are the ones no WCAG success criterion names outright and the issue
that opened this section asked about by name: heading levels that do not skip
(`heading-order`; the page is h1, h2, h2, h3), exactly one `<main>` and one
`<h1>`, all content inside a landmark, no duplicate ids. Because the page
cleared them on first measurement, the gate now requires them rather than
reporting them.

**The one real defect, and how it was missed until now.** With the findings
list rendered, the page was 366 CSS px wide at a 320 px viewport: a horizontal
scrollbar on the whole document, which is SC 1.4.10. The cause was the
unbreakable strings every finding carries, Registry URIs and rule source URLs,
in the `.rule` block. It was fixed with `overflow-wrap: anywhere` and the gate
was then broken on purpose to confirm it catches the regression (it reports
601 px and fails).

The empty page passed the same check. That is the lesson worth keeping: an
accessibility audit of this page that loads it and scans it audits an input
box and three buttons, and misses the part where all the content is. The gate
therefore renders one finding of each severity before scanning, through the
same code path a real run uses, which is also the only way the four severity
colours get their contrast checked at all.

**Controls now in place.** `.github/workflows/accessibility.yml`, merge-blocking,
no advisory mode: axe-core in both colour schemes, the 320 px reflow check, and
a Lighthouse accessibility score that must be 1.00 rather than the standard's
0.90 floor, because the page measured 1.00 and the standard says a repository
clearing a higher bar enforces the higher one. The audit runs against
`?a11y-static`, which fetches nothing, so the gate is deterministic and does
not make a merge depend on a CDN being up.

**REVIEW gate, open.** A keyboard and screen-reader walkthrough by a human,
covering the Pyodide startup state specifically. Nothing automated can judge
whether `role="status"` on a paragraph that says "Loading Python (this takes a
few seconds the first time)" is an adequate account of a thirty-second wait,
and the honest answer is that it probably is not: it announces once, and never
again until the runtime is ready. This is recorded as open rather than
declared passed.

**Residual risk.** Two things the automated gate does not see. The live boot
path is not scanned, by design, because gating it would put jsDelivr in the
merge path; the static mode renders the same markup from the same functions,
so what is unscanned is the loading state and any error state, not the report.
And automated tooling catches something like a third to a half of WCAG
failures; 0 violations means 0 machine-detectable violations, which is not the
same as conformance and is not claimed as one.
