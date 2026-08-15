"""Check 3: reference resolution across this run's effective data model.

A blank node reference that its own payload does not define is an ERROR:
blank node identifiers have no meaning outside the graph that declares them.

An absolute IRI is judged against everything the run has in hand. Resolving
inside the payload is silent, and check 4 goes on to judge the target's class.
Resolving inside a document supplied with ``--resolve`` is an INFO note naming
the file, because every claim check 4 then makes about that target rests on
that file having been supplied. Resolving nowhere is UNVERIFIABLE, not a
failure: the entity may exist in the Registry or elsewhere, and this tool
fetches nothing at validation time.
"""

from __future__ import annotations

from .. import rules
from ..findings import Finding, Severity
from ..graph import NestedRef
from ..session import Session


def _absolute_iri_finding(entity: str, prop: str, value: str, session: Session) -> Finding:
    """What to say about an IRI the payload itself does not define."""
    supplied, schema = session.supplied, session.schema
    external = supplied.get(value)
    if external is not None:
        declared = schema.known_types(external.types)
        as_what = (
            f"typed [{', '.join(declared)}]"
            if declared
            else "carrying no class this schema snapshot declares"
        )
        return Finding(
            code="REF_RESOLVED_SUPPLIED",
            severity=Severity.INFO,
            entity=entity,
            prop=prop,
            value=value,
            message=(
                f"Reference resolves in {external.source}, supplied with --resolve, "
                f"{as_what}. Anything this report says about the referenced entity "
                "rests on that document."
            ),
            rule=rules.RESOLUTION_POLICY,
        )
    detail = (
        f" {supplied.shortfall()}"
        if supplied.any_documents
        else " Pass it with --resolve to settle this."
    )
    return Finding(
        code="REF_OUTSIDE_PAYLOAD",
        severity=Severity.UNVERIFIABLE,
        entity=entity,
        prop=prop,
        value=value,
        message=(
            "Reference does not resolve inside this payload. It may exist in the "
            "Registry or elsewhere; without fetching it, its existence and class "
            "cannot be confirmed or denied." + detail
        ),
        rule=rules.NO_NETWORK_POLICY,
    )


def check(session: Session) -> list[Finding]:
    graph, schema = session.graph, session.schema
    findings: list[Finding] = []
    for node in graph.nodes:
        entity = node.label
        for prop, values in sorted(node.props.items()):
            prop_def = schema.properties.get(prop)
            if prop_def is None or not prop_def.id_coerced or not prop_def.range_has_entities:
                continue
            for value in values:
                if isinstance(value, NestedRef):
                    continue  # inline containment: trivially resolved
                if not isinstance(value, str):
                    continue
                if graph.resolve(value) is not None:
                    continue
                if value.startswith("_:"):
                    findings.append(
                        Finding(
                            code="REF_UNRESOLVED_BNODE",
                            severity=Severity.ERROR,
                            entity=entity,
                            prop=prop,
                            value=value,
                            message=(
                                "Blank node reference is not defined anywhere in this "
                                "payload. A blank node identifier only has meaning inside "
                                "the graph that declares it, so this reference cannot "
                                "identify anything."
                            ),
                            rule=rules.BNODE_SCOPE,
                        )
                    )
                elif ":" in value:
                    findings.append(_absolute_iri_finding(entity, prop, value, session))
                # Non-IRI strings are already reported by the identifier-kind check.
    return findings
