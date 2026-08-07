"""Check 3: reference resolution within the payload.

A blank node reference that its own payload does not define is an ERROR:
blank node identifiers have no meaning outside the graph that declares them.
An absolute IRI that does not resolve inside the payload is UNVERIFIABLE, not
a failure: the entity may exist in the Registry or elsewhere, and this tool
does not fetch anything at validation time.
"""

from __future__ import annotations

from .. import rules
from ..findings import Finding, Severity
from ..graph import Graph, NestedRef
from ..schema import SchemaIndex


def check(graph: Graph, schema: SchemaIndex) -> list[Finding]:
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
                    findings.append(
                        Finding(
                            code="REF_OUTSIDE_PAYLOAD",
                            severity=Severity.UNVERIFIABLE,
                            entity=entity,
                            prop=prop,
                            value=value,
                            message=(
                                "Reference does not resolve inside this payload. It may "
                                "exist in the Registry or elsewhere; without fetching it, "
                                "its existence and class cannot be confirmed or denied."
                            ),
                            rule=rules.NO_NETWORK_POLICY,
                        )
                    )
                # Non-IRI strings are already reported by the identifier-kind check.
    return findings
