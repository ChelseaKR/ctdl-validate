# 5. One identifier, one entity: repeated `@id`s are merged, and the merge is reported

## Status

Accepted

## Context

`Graph.by_id` was populated with `if node_id not in self.by_id`. The first
node object to claim an identifier kept it; every later declaration of the
same `@id` was appended to `nodes` and `by_path` and never reached `by_id`.
Since `Graph.resolve()` looks every reference up through `by_id`, each
reference to a repeated identifier was judged against whichever declaration
the walk happened to reach first.

That order is not meaningful. It is `@graph` array position interleaved with
JSON object key order, because `_Builder.walk` recurses into a node's
properties in `obj.items()` order.

Repeating an `@id` is not a malformed payload. It is a normal CTDL idiom: an
entity is declared at the top level and embedded again, inline and partially,
where something refers to it and wants to carry its class or its name. Issue
[#33](https://github.com/ChelseaKR/ctdl-validate/issues/33) has the worked
case. A `ceterms:Place` declared correctly at the top of a `@graph` is also
embedded, earlier in the file, as a `ceterms:parentOrganization` stub typed
`ceterms:Organization`. The stub won `by_id`, so a third entity's
`ceterms:address` -- whose declared range is `ceterms:Place` and which pointed
at exactly the right resource -- was reported `RANGE_VIOLATION` / ERROR.
Moving the real declaration to the front of the array made the ERROR vanish
with no change to what the document meant.

Both directions are reachable. A first-seen stub whose incidental type happens
to be *in* range hides a real violation just as easily as one out of range
manufactures a false one. Which way it goes is decided by array order.

The tool's determinism tests could not see any of this. Byte-identical output
for identical input is exactly what a stable wrong answer produces. As the
issue puts it: "the ERROR is stable, not correct."

## Decision

The parser merges node objects that declare the same `@id` into one node,
before any check runs: the union of their `@type` values and the union of
their properties. This is what a JSON-LD processor does with a repeated node
identifier, and it is the second of the two fixes the issue proposes.

Three consequences are deliberate.

1. **A merged `@type` tuple is sorted.** A single declaration's types keep the
   order the document wrote them in. Between two declarations there is no
   document order to keep, and type names reach the reader inside messages
   (`domain_range` renders `[{', '.join(types)}]`), so an encounter-ordered
   union would make the same document produce different bytes when its
   entities were rearranged. Sorting is what makes the fix hold, rather than
   moving the order-dependence from the verdict into the message.

2. **Within one declaration, values are untouched.** Repeats inside a single
   property array are kept exactly as written. Only the cross-declaration
   union dedupes, and only for the values already present.

3. **The merge is reported, at INFO.** `ID_DECLARED_MORE_THAN_ONCE` names
   every path that declared the identifier and the merged type list. It is a
   disclosure, not a defect, and it is the reason this ADR exists rather than
   a one-line parser change: a silent merge would replace one invisible
   behavior with another. A reader who did not intend one entity would
   otherwise see a finding against a type list that no single line of their
   document contains, with nothing to explain where it came from.

## Alternatives considered

**Keep first-wins and report the disagreement.** The issue's minimum
suggestion: detect two declarations of one `@id` with different `@type`
tuples and raise a finding. Rejected because it leaves the wrong verdict in
place. The false `RANGE_VIOLATION` would still be reported; it would simply be
accompanied by a note. A tool whose answer is wrong does not become right by
also being talkative.

**Refuse to resolve a repeated identifier**, so downstream references become
UNVERIFIABLE. Rejected because it is not true. UNVERIFIABLE is reserved for
what the run cannot determine from what it was given
([ADR-0004](0004-resolution-is-additive.md)), and the payload does determine
this: both declarations are in front of the tool and JSON-LD says what they
mean together. Spending UNVERIFIABLE on a question the document answers would
weaken the severity that carries the most weight in this tool.

**Report the repetition as an ERROR.** Rejected because no published source
says a payload may not do it, and the Registry's own documents do it.
Reporting an error at something the publisher does routinely is the failure
the README's severity section is written against.

## Consequences

`Graph` gains `declarations` (identifier to every path that declared it) and
`repeated_ids()`. Check 6 (`checks/identity.py`) reads them and returns INFO
findings only; it can never gate an exit code.

One guard was written and then removed rather than kept. The declaration
paths in the message were sorted, by analogy with the merged `@type` tuple.
The analogy does not hold and the sort was wrong twice over: no test in the
suite could fail it, because below ten entities walk order already is lexical
order, and above ten it is incorrect, since `$.@graph[10]` sorts before
`$.@graph[9]` and the message would list the second declaration first. Paths
are positions in the reader's file and are reported in the order the file puts
them. `test_declaration_paths_are_listed_in_document_order_past_index_nine`
is the case that separates the two orders, so re-adding the sort fails.

Documents with no repeated identifier are unaffected: the merge branch is not
reached, types keep document order, and property tuples are built exactly as
before.

A document that *does* repeat an identifier can change verdict, in either
direction, and that is the point.
`tests/test_repeated_identifiers.py` carries the issue's payload in both array
orders and asserts that every finding which judges the document is identical,
in the text rendering and in the JSON one.

One finding is deliberately outside that guarantee, and writing the test is
what made it visible. `ID_DECLARED_MORE_THAN_ONCE` names the paths the
declarations sit at, and rearranging a `@graph` moves them, so its message
cannot be byte-identical across a rearrangement without dropping the locator
that makes it useful. The honest scope is therefore: nothing that says the
document is wrong follows array order, and the one finding that reports *where
things are* does. Its subject, severity and merged type list are asserted
identical from either order.

Issue #33 also predicts that merging restores a violation in the
false-negative direction, where the stub walked first is in range and the
authoritative declaration is not. It does not, and should not: after the merge
the document asserts the resource is both classes and the property admits one
of them, so there is no violation to report. What the fix owes there is that
the answer is the same either way round, and
`test_one_declaration_in_range_settles_it_from_either_order` is that claim.
