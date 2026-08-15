# 4. --resolve is additive: it can settle an unknown, never manufacture a failure

## Status

Accepted

## Context

Check 3 reports a reference the payload does not define as
`REF_OUTSIDE_PAYLOAD` / UNVERIFIABLE, and the README defends the severity
well: "never punish what you cannot see, and never bless it either." What the
tool had no answer for was the second half of that sentence. There was no way
for an operator to make a reference visible, so UNVERIFIABLE was not a prompt;
it was the end of the conversation.

That is not a corner case in this vocabulary. Registry documents reference
other Registry documents by URI as a matter of routine: a credential names the
organization that owns it, a competency names its framework, a condition
profile names the learning opportunity it requires. Validating one real
published Registry document on 2026-08-15
(`credentialengineregistry.org/graph/ce-e8a41a52-6ff6-48f0-9872-889c87b093b7`)
produced exactly three findings: three `REF_OUTSIDE_PAYLOAD`, all pointing at
the same neighbouring resource. The tool's whole report on a real document was
"I cannot tell", three times, about one document nobody had asked for.

`ChelseaKR/oscal-validate` had already met the same problem and named the
idea. NIST defines the "effective data model" of an OSCAL document as the
document plus everything it directly or transitively imports, and
`oscal-validate` takes `--resolve` to supply those imports as local files. It
then draws a line CTDL cannot draw: because an OSCAL document *declares* what
it imports, a reference that misses inside a complete effective data model is
an ERROR, and only an incomplete one yields UNVERIFIABLE.

## Decision

Add `ctdl-validate <file.json> --resolve <path>`, repeatable, accepting files
or directories of `.json`. Four constraints:

1. **Nothing is fetched.** `--resolve` reads local files. The validator opens
   no socket in any code path, with or without it, and
   `tests/test_offline_guarantee.py` proves it by removing `socket.socket`,
   `socket.create_connection` and `socket.getaddrinfo` and running a resolved
   validation anyway. Whoever obtained the neighbouring documents made that
   choice outside the validator, the same way `extract` is a separate command
   with its own posture.
2. **Supplied documents are indexed, never validated.** They populate a side
   index of `@id` to declared class in `ctdl_validate.session`. They are not
   merged into the graph being checked, so adding a neighbour cannot change
   how many entities the report is about and cannot put someone else's
   document's defects in your report.
3. **An unresolved reference stays UNVERIFIABLE.** This is where the tool
   deliberately stops short of `oscal-validate`. CTDL has no `imports`
   declaration, so a CTDL payload never states which documents its effective
   data model is supposed to contain, and this tool therefore has no basis for
   the claim "you gave me everything, so this reference is wrong." Supplying a
   document can convert a non-answer into an answer. It can never convert a
   non-answer into a failure.
4. **Every resolution is reported.** A reference that resolves in a supplied
   document produces `REF_RESOLVED_SUPPLIED` (INFO) naming the file and the
   class it found, because every subsequent judgement about that target rests
   on that file having been supplied. An UNVERIFIABLE finding in a run that
   supplied documents names them too, so a reader can tell "you did not give
   me the document" from "the documents you gave me do not contain it."

Resolution feeds check 4 exactly as in-payload resolution does: a reference
whose supplied target is outside the property's declared `schema:rangeIncludes`
is `RANGE_VIOLATION` / ERROR, and it gates the exit code. A supplied
`ceasn:CompetencyFramework` also joins the candidate set for the
wrong-framework `isPartOf` pattern, because the question that check asks is
whether the identifier names a framework the run can see, not which file that
framework arrived in.

Where two supplied documents declare the same `@id`, the first in sorted path
order wins. That is a determinism rule rather than a considered one: two
documents disagreeing about what an `@id` is are a dispute this tool does not
adjudicate, and naming the source file in every finding keeps the
disagreement visible rather than silent.

## Consequences

- The severity contract is unchanged. UNVERIFIABLE still never gates the exit
  code, and the set of things that can produce an ERROR is the same set as
  before; only the set of references those checks can reach has grown.
- Default behaviour changes in one visible way: with no `--resolve`, a
  `REF_OUTSIDE_PAYLOAD` message now ends "Pass it with --resolve to settle
  this." The finding, code and severity are identical.
- A survey of published Registry records stops being bounded by the tool. Run
  document by document, the answer is a large UNVERIFIABLE count and little
  else; run with the sample supplied to itself, the cross-references inside
  the sample become real verdicts. That is the measurement `oscal-validate`
  was built to make possible and this tool could not make.
- `Check` now takes a `Session` (payload, schema, supplied) rather than a
  `(Graph, SchemaIndex)` pair, matching `oscal-validate`, so the one input
  that can change a finding's severity is explicit at every use.
- If CTDL ever gains a way for a document to declare the documents it depends
  on, point 3 should be revisited: that declaration is exactly the missing
  premise for the ERROR this tool currently declines to raise.
