# 3. Extraction is a separate command, with a declared network posture and no model

## Status

Accepted

## Context

Validation only ever sees a payload that already exists. The payload usually
starts on a provider's website, so a publisher's real question is wider than
the one the tool answered: not only "is this document valid" but "what can I
honestly get out of this page in the first place". Answering it means fetching
a page, which collides head-on with ADR-0001's decision that the tool performs
no network calls and with the README's promise of the same.

Two ways to answer it were available and both are worse:

- **A model.** Hand a page to an LLM and ask for CTDL. Coverage would go up
  sharply, and so would the number of well-formed credentials that no page
  ever claimed. A publisher cannot tell those apart by looking at the output,
  and neither can the Registry.
- **A hand-written crosswalk.** Encode "schema.org's `Course` is CTDL's
  `Course`" and a few hundred more like it. That is a rule encoded from
  memory, which the project's first invariant forbids.

## Decision

Add `ctdl-validate extract <url>` as a separate subcommand under
`ctdl_validate.extract`, with four constraints:

1. **The validator's promise is untouched and now enforced.** Nothing under
   `ctdl_validate.checks` imports anything from `ctdl_validate.extract`.
   `tests/test_offline_guarantee.py` removes `socket.socket`,
   `socket.create_connection`, and `socket.getaddrinfo`, then runs the
   validator over the fixtures. The claim is tested, not repeated.
2. **No model, in either command.** Extraction reads the structured markup a
   page already publishes: JSON-LD, microdata, and RDFa Lite. It cannot read a
   credential out of prose, and pages without markup yield nothing.
3. **The crosswalk is read out of the vendored snapshot, not written.**
   Credential Engine's schema encodings declare `owl:equivalentClass` and
   `owl:equivalentProperty` for terms in other vocabularies;
   `extract/crosswalk.py` indexes those declarations from the same
   hash-checked files the validator's rules come from. Specializations
   (`rdfs:subClassOf` toward another vocabulary) are indexed separately and
   never produce an assertion, because they point the wrong way. Where two
   CTDL terms claim one foreign term, the subject's class must appear in
   exactly one of their declared domains or the value is dropped.
4. **One module holds every socket, with a written posture.**
   `extract/fetch.py` fetches robots.txt and obeys it (a Disallow is a hard
   stop with no override flag; an unreachable robots.txt is also a stop, per
   RFC 9309 2.3.1.4), identifies itself with a product token and a link to
   this repository, follows at most five redirects and re-checks robots.txt at
   every hop, caps bytes, sets a timeout, and rate limits per host with a
   floor a site's `Crawl-delay` can raise. Everything downstream of it is a
   pure function of the fetched bytes.

Exit codes are the subcommand's own: 0 when at least one CTDL entity came out,
1 when the page was read and produced none, 2 when nothing could be read.

## Consequences

- Coverage is low by construction and honest about it. Six schema.org classes
  and 56 schema.org properties carry declared CTDL equivalences in the
  2026-08-06 snapshot; the types most credential providers publish
  (`EducationalOccupationalProgram`, `EducationalOccupationalCredential`,
  `CollegeOrUniversity`) are not among them. The tool reports each miss with
  the declaration it looked for.
- Refreshing the vendored snapshot refreshes the crosswalk. A new equivalence
  upstream becomes a new mapping here with no code change, which is the same
  property the validator's rules already have.
- The determinism claim is narrower for extraction and stated that way: same
  page bytes, same output. The extraction report carries no timestamp, so the
  narrower claim is testable.
- The browser playground stays validation-only. A page fetched from a browser
  tab cannot honestly promise a robots.txt check or a per-host rate limit
  against the site's real origin.
- An extract can be faithful and still fail validation, because a term-by-term
  crosswalk does not compose: `schema:address` pointing at a
  `schema:PostalAddress` maps through two declared equivalences into a
  `ceterms:address` whose declared range is `ceterms:Place`. Surfacing that is
  the point of the pipeline, not a defect in either half of it.
