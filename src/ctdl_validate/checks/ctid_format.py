"""Check 1: CTID format.

Values of ceterms:ctid, plus the CTID portion of any Registry resource/graph
URI appearing anywhere in the payload (including @id), must match the
published grammar. See ctid.py for the grammar and its source.
"""

from __future__ import annotations

from .. import rules
from ..ctid import EXPECTED_GRAMMAR, classify_ctid, registry_uri_tail
from ..findings import Finding, Severity
from ..graph import Graph
from ..schema import SchemaIndex

CTID_PROP = "ceterms:ctid"


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


def _registry_uri_findings(entity: str, prop: str, value: str) -> list[Finding]:
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


def check(graph: Graph, schema: SchemaIndex) -> list[Finding]:
    findings: list[Finding] = []
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
