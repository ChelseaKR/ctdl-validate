"""Determined re-spellings for the findings whose correction the payload fixes.

Four of this tool's codes name a defect whose repair is not a search and not a
guess: the corrected value is already written somewhere in the document, or in
a document handed to the run with ``--resolve``, and the only thing missing is
for a person to see it beside the finding.

- ``CTID_UPPERCASE`` -- the same CTID in the lower case the grammar publishes.
- ``CTID_URI_MISMATCH`` -- the entity's ``ceterms:ctid`` disagrees with the
  CTID in its own ``@id``; the ``@id``'s is offered. On the ``@graph``
  envelope's own ``@id``, where there is no second opinion to take, the
  envelope URI re-spelled with the payload's one declared CTID is offered --
  and only when the payload declares exactly one.
- ``REF_BARE_CTID`` -- an entity this run can see declares that CTID, so the
  reference should be that entity's ``@id``.
- ``ISPARTOF_FRAMEWORK_MISMATCH`` -- exactly one ``ceasn:CompetencyFramework``
  is in reach, so there is one identifier the competency could mean.

Nothing here invents a value. No CTID is minted, no language is guessed, no
literal becomes an IRI, and no model is involved. Every suggestion is a string
that is already in the run's input; where the run holds more than one
candidate, or none, this module offers nothing rather than picking.

**What is deliberately never suggested**, and why -- see
:data:`NEVER_SUGGESTED`:

- ``CTID_BARE_UUID`` and ``REF_BARE_UUID``. Prefixing the UUID with ``ce-``
  would produce a well-formed CTID, which is exactly the problem: it asserts
  that the generated UUID names a Registry resource. A bare UUID is evidence
  that something other than a CTID was written, not evidence about which CTID
  was meant.
- ``LANGUAGE_MAP_EXPECTED``. Wrapping a literal needs a language tag, and the
  document does not say which one.
- Every UNVERIFIABLE finding, whatever its code. UNVERIFIABLE means the
  payload alone cannot settle the question; a suggestion computed from that
  same payload cannot settle it either, and offering one would read as though
  it had.

The ``Suggestion`` shape -- ``value`` plus ``difference``, absent from both
renderings when there is none -- is the one ``oscal-validate`` publishes for
the same flag. The two tools derive candidates differently (that one searches
an identifier index within a bounded edit distance; this one reads a
determined re-spelling out of the payload), but a consumer reading both should
not have to learn two report shapes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from collections.abc import Mapping as MappingABC

from .checks.ctid_format import CTID_PROP, ctids_declared
from .checks.identifier_kind import looks_like_iri
from .ctid import classify_ctid, registry_uri_tail
from .findings import Finding, Severity, Suggestion
from .graph import Graph, Node
from .session import Session

#: The codes this module refuses to suggest for, with the reason, so the
#: refusal is a written decision rather than an omission. The module docstring
#: expands each one; ``tests/test_suggest.py`` asserts this set is disjoint
#: from the suggesters below, so a code cannot quietly appear in both.
NEVER_SUGGESTED: MappingABC[str, str] = {
    "CTID_BARE_UUID": (
        "prefixing the UUID with ce- would assert that this generated UUID names a "
        "Registry resource, which is the claim the finding disputes"
    ),
    "REF_BARE_UUID": (
        "same: a bare UUID is evidence that something other than a CTID was written, "
        "not evidence about which CTID was meant"
    ),
    "LANGUAGE_MAP_EXPECTED": (
        "wrapping a literal in a language map needs a language tag, and the document "
        "does not say which one"
    ),
}

#: The `ceasn:CompetencyFramework` class, as `schema.class_matches` wants it.
_FRAMEWORK = frozenset({"ceasn:CompetencyFramework"})


def _ctids_of(node: Node, node_id: str) -> set[str]:
    """Every shape-valid CTID one identified node declares, in either position.

    ``node_id`` is passed in rather than read back off ``node`` because the
    only caller has already established the node has one; re-testing it here
    would be a branch nothing can take.
    """
    declared = {
        value
        for value in node.props.get(CTID_PROP, ())
        if isinstance(value, str) and classify_ctid(value).matches_shape
    }
    tail = registry_uri_tail(node_id)
    if tail is not None and classify_ctid(tail).matches_shape:
        declared.add(tail)
    return declared


def _sole(candidates: set[str], written: str) -> str | None:
    """The one candidate, or ``None`` when there is not exactly one.

    A candidate identical to what was written is not a candidate: it would
    re-offer the value the finding is about.
    """
    distinct = sorted(candidate for candidate in candidates if candidate != written)
    return distinct[0] if len(distinct) == 1 else None


def _uppercase_ctid(session: Session, finding: Finding) -> tuple[Suggestion, ...]:
    lowered = finding.value.lower()
    shape = classify_ctid(lowered)
    if lowered == finding.value or not (shape.matches_shape and shape.lowercase):
        return ()
    return (Suggestion(value=lowered, difference="the same CTID in lower case"),)


def _uri_mismatch(session: Session, finding: Finding) -> tuple[Suggestion, ...]:
    graph = session.graph
    if finding.prop == CTID_PROP:
        node = graph.by_id.get(finding.entity)
        if node is None or node.node_id is None:
            return ()
        tail = registry_uri_tail(node.node_id)
        if tail is None or not classify_ctid(tail).matches_shape or tail == finding.value:
            return ()
        # The @id is the entity's identity and other entities point at it; the
        # ceterms:ctid is the copy. Re-spelling the copy is the smaller change,
        # and it is the value this finding is attached to.
        return (Suggestion(value=tail, difference="the CTID in this entity's own @id"),)
    envelope_id = graph.envelope_id
    if finding.prop == "@id" and envelope_id is not None and finding.entity == envelope_id:
        return _envelope_mismatch(graph, envelope_id)
    return ()


def _envelope_mismatch(graph: Graph, envelope_id: str) -> tuple[Suggestion, ...]:
    """The envelope's own ``@id``, re-spelled with the payload's one CTID.

    Takes the identifier the caller has already established is the envelope's,
    rather than reading it back off the graph and re-checking it for ``None``:
    a guard that cannot fail is worth less than no guard, and the caller's
    equality test is what makes this one unnecessary.
    """
    tail = registry_uri_tail(envelope_id)
    if tail is None or not envelope_id.endswith(tail):
        return ()
    declared = _sole(ctids_declared(graph), tail)
    if declared is None:
        return ()
    return (
        Suggestion(
            value=envelope_id[: len(envelope_id) - len(tail)] + declared,
            difference="the graph URI re-spelled with the one CTID this payload declares",
        ),
    )


def _bare_ctid(session: Session, finding: Finding) -> tuple[Suggestion, ...]:
    written = finding.value.casefold()
    candidates = {
        node_id
        for node in session.graph.nodes
        if (node_id := node.node_id) is not None
        and any(ctid.casefold() == written for ctid in _ctids_of(node, node_id))
    }
    for entity in session.supplied.entities.values():
        tail = registry_uri_tail(entity.node_id)
        if tail is not None and tail.casefold() == written:
            candidates.add(entity.node_id)
    # A candidate that is not itself an IRI would trip the very rule this
    # suggestion answers.
    sole = _sole({c for c in candidates if looks_like_iri(c)}, finding.value)
    if sole is None:
        return ()
    return (
        Suggestion(
            value=sole,
            difference="the @id of the entity in this run that declares that CTID",
        ),
    )


def _framework_ids(session: Session) -> set[str]:
    graph, schema, supplied = session.graph, session.schema, session.supplied
    ids = {
        node.node_id
        for node in graph.nodes
        if node.node_id is not None
        and schema.class_matches(schema.known_types(node.types), _FRAMEWORK)
    }
    ids |= {
        entity.node_id
        for entity in supplied.entities.values()
        if schema.class_matches(schema.known_types(entity.types), _FRAMEWORK)
    }
    return ids


def _framework_mismatch(session: Session, finding: Finding) -> tuple[Suggestion, ...]:
    sole = _sole(_framework_ids(session), finding.value)
    if sole is None:
        return ()
    return (
        Suggestion(
            value=sole,
            difference="the @id of the one CompetencyFramework this run can see",
        ),
    )


#: Code -> the function that derives its candidates. A code absent from here
#: gets nothing; a code in :data:`NEVER_SUGGESTED` may never be added.
SUGGESTERS: MappingABC[str, Callable[[Session, Finding], tuple[Suggestion, ...]]] = {
    "CTID_UPPERCASE": _uppercase_ctid,
    "CTID_URI_MISMATCH": _uri_mismatch,
    "REF_BARE_CTID": _bare_ctid,
    "ISPARTOF_FRAMEWORK_MISMATCH": _framework_mismatch,
}


def suggestions_for(session: Session, finding: Finding) -> tuple[Suggestion, ...]:
    """Every determined re-spelling for one finding, or an empty tuple."""
    if finding.severity is Severity.UNVERIFIABLE:
        return ()
    suggester = SUGGESTERS.get(finding.code)
    return () if suggester is None else suggester(session, finding)


def with_suggestions(session: Session, findings: list[Finding]) -> list[Finding]:
    """The same findings, in the same order, carrying their suggestions.

    Run after ``finalize``: a suggestion is not part of a finding's identity,
    so it must not reach the deduplication or the sort. Findings with no
    candidate come back unchanged, which is why the default path's bytes do
    not move -- a run without ``--suggest`` never calls this at all.
    """
    return [
        dataclasses.replace(finding, suggestions=suggested)
        if (suggested := suggestions_for(session, finding))
        else finding
        for finding in findings
    ]
