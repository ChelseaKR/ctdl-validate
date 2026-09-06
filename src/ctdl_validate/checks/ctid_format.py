"""Check 1: CTID format.

Values of ceterms:ctid, plus the CTID portion of any Registry resource/graph
URI appearing anywhere in the payload, must match the published grammar. That
includes both @id positions: a node's, and the @graph envelope's own -- the
latter being the only place a Registry *graph* URI appears in a published
Registry document. See ctid.py for the grammar and its source.
"""

from __future__ import annotations

from .. import rules
from ..ctid import EXPECTED_GRAMMAR, classify_ctid, registry_uri_tail
from ..findings import Finding, Severity
from ..graph import Graph
from ..session import Session

CTID_PROP = "ceterms:ctid"

#: Appended to a finding's message when the URI is the ``@graph`` envelope's
#: own ``@id`` rather than a node's, so the report says which position it sits
#: in. A Registry graph URI appears nowhere else in a published document.
_ENVELOPE_WHERE = " This URI is the @graph envelope's own @id ($.@id)."


def _ctid_value_findings(entity: str, value: object) -> list[Finding]:
    if not isinstance(value, str):
        return [
            Finding(
                code="CTID_MALFORMED",
                severity=Severity.ERROR,
                entity=entity,
                prop=CTID_PROP,
                value=repr(value),
                message=f"ceterms:ctid must be a string matching: {EXPECTED_GRAMMAR}.",
                rule=rules.CTID_STRUCTURE,
            )
        ]
    shape = classify_ctid(value)
    findings: list[Finding] = []
    if shape.bare_uuid:
        findings.append(
            Finding(
                code="CTID_BARE_UUID",
                severity=Severity.ERROR,
                entity=entity,
                prop=CTID_PROP,
                value=value,
                message=(
                    "Bare UUID where a CTID belongs: the ce- prefix is missing. "
                    f"Expected grammar: {EXPECTED_GRAMMAR}."
                ),
                rule=rules.CTID_STRUCTURE,
            )
        )
    elif not shape.matches_shape:
        findings.append(
            Finding(
                code="CTID_MALFORMED",
                severity=Severity.ERROR,
                entity=entity,
                prop=CTID_PROP,
                value=value,
                message=f"Value does not match the CTID grammar: {EXPECTED_GRAMMAR}.",
                rule=rules.CTID_STRUCTURE,
            )
        )
    else:
        if not shape.lowercase:
            findings.append(
                Finding(
                    code="CTID_UPPERCASE",
                    severity=Severity.WARNING,
                    entity=entity,
                    prop=CTID_PROP,
                    value=value,
                    message=(
                        "CTID contains upper case hexadecimal digits. UUID text form is "
                        "lower case on output; Registry case handling is not documented, "
                        "so this is a WARNING rather than an ERROR."
                    ),
                    rule=rules.CTID_LOWERCASE,
                )
            )
        if not shape.uuid_v4:
            findings.append(
                Finding(
                    code="CTID_NOT_UUIDV4",
                    severity=Severity.WARNING,
                    entity=entity,
                    prop=CTID_PROP,
                    value=value,
                    message=(
                        "CTID matches the 39-character shape but its UUID version/variant "
                        'bits are not version 4. The published grammar says "a standard '
                        'UUID v4"; Registry enforcement of the version bits is not '
                        "documented, so this is a WARNING rather than an ERROR."
                    ),
                    rule=rules.CTID_STRUCTURE,
                )
            )
    return findings


def _registry_uri_findings(entity: str, prop: str, value: str, where: str = "") -> list[Finding]:
    tail = registry_uri_tail(value)
    if tail is None:
        return []
    shape = classify_ctid(tail)
    if shape.matches_shape:
        return []
    if shape.bare_uuid:
        message = (
            "Registry URI whose CTID portion is a bare UUID: the ce- prefix is "
            f"missing. Expected: {EXPECTED_GRAMMAR}."
        )
    else:
        message = (
            "Registry URI whose tail is not a CTID. Registry resource and graph URIs "
            f"end in the resource's CTID: {EXPECTED_GRAMMAR}."
        )
    message += where
    return [
        Finding(
            code="REGISTRY_URI_MALFORMED",
            severity=Severity.ERROR,
            entity=entity,
            prop=prop,
            value=value,
            message=message,
            rule=rules.CTID_URI_STRUCTURE,
        )
    ]


def _ctids_declared(graph: Graph) -> set[str]:
    """Every CTID the payload declares, however it declares it.

    Both positions count: a ``ceterms:ctid`` value, and the CTID tail of a
    node's own Registry ``@id``. A graph URI is compared against this set
    rather than against one designated "primary" entity, because the document
    shape does not say which entity is primary and guessing would invent
    findings the payload does not support.
    """
    declared: set[str] = set()
    for node in graph.nodes:
        for value in node.props.get(CTID_PROP, ()):
            if isinstance(value, str) and classify_ctid(value).matches_shape:
                declared.add(value)
        if node.node_id is not None:
            tail = registry_uri_tail(node.node_id)
            if tail is not None and classify_ctid(tail).matches_shape:
                declared.add(tail)
    return declared


def _envelope_findings(graph: Graph) -> list[Finding]:
    """Check 1 against the ``@graph`` envelope's own ``@id``.

    This is the only position in which a Registry *graph* URI appears in a
    published Registry document -- in all five Registry-shaped fixtures here,
    ``/graph/`` occurs exactly once each, always as this key. Until the
    envelope identifier was kept (see ``graph.Graph.envelope_id``) no check
    could see it, so ``REGISTRY_URI_MALFORMED`` could not fire on a real
    Registry payload at all and ``registry_uri_tail``'s graph-prefix branch
    was dead against them.
    """
    envelope_id = graph.envelope_id
    if envelope_id is None:
        return []
    findings = _registry_uri_findings(envelope_id, "@id", envelope_id, where=_ENVELOPE_WHERE)
    tail = registry_uri_tail(envelope_id)
    if tail is None or not classify_ctid(tail).matches_shape:
        return findings
    declared = _ctids_declared(graph)
    if not declared or tail in declared:
        return findings
    findings.append(
        Finding(
            code="CTID_URI_MISMATCH",
            severity=Severity.ERROR,
            entity=envelope_id,
            prop="@id",
            value=envelope_id,
            message=(
                f"The @graph envelope's own @id ($.@id) names CTID {tail}, which no "
                "entity in the payload declares -- neither as ceterms:ctid nor as the "
                "CTID portion of its own Registry @id. Declared here: "
                f"{', '.join(sorted(declared))}."
            ),
            rule=rules.CTID_URI_STRUCTURE,
        )
    )
    return findings


def check(session: Session) -> list[Finding]:
    graph = session.graph
    findings: list[Finding] = _envelope_findings(graph)
    for node in graph.nodes:
        entity = node.label
        for value in node.props.get(CTID_PROP, ()):
            findings.extend(_ctid_value_findings(entity, value))

        if node.node_id is not None:
            findings.extend(_registry_uri_findings(entity, "@id", node.node_id))
            # About the CTID: the ctid property value exactly matches the CTID
            # portion of the resource's URI.
            tail = registry_uri_tail(node.node_id)
            ctids = [v for v in node.props.get(CTID_PROP, ()) if isinstance(v, str)]
            if tail is not None and classify_ctid(tail).matches_shape:
                for ctid_value in ctids:
                    if classify_ctid(ctid_value).matches_shape and ctid_value != tail:
                        findings.append(
                            Finding(
                                code="CTID_URI_MISMATCH",
                                severity=Severity.ERROR,
                                entity=entity,
                                prop=CTID_PROP,
                                value=ctid_value,
                                message=(
                                    f"ceterms:ctid ({ctid_value}) does not match the CTID "
                                    f"portion of the entity's @id ({tail})."
                                ),
                                rule=rules.CTID_URI_STRUCTURE,
                            )
                        )

        for prop, values in sorted(node.props.items()):
            for value in values:
                if isinstance(value, str):
                    findings.extend(_registry_uri_findings(entity, prop, value))
    return findings
