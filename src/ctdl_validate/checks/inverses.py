"""Check 5: inverse consistency.

Only pairs the schema itself declares with owl:inverseOf are checked. Where
both directions are present between two in-payload entities, they must agree
(ERROR when they do not). Where only one direction is present, that is INFO,
not an error: publishing one direction is normal.
"""

from __future__ import annotations

from typing import Any

from .. import rules
from ..findings import Finding, Severity
from ..graph import Graph, NestedRef
from ..session import Session


def _references_node(values: tuple[Any, ...], node_id: str, graph: Graph) -> bool:
    """Check if any value in a property references node_id, directly or via NestedRef."""
    for value in values:
        if isinstance(value, str) and value == node_id:
            return True
        if isinstance(value, NestedRef):
            if value.target_id == node_id:
                return True
            target = graph.resolve(value)
            if target is not None and target.node_id == node_id:
                return True
    return False


def check(session: Session) -> list[Finding]:
    graph, schema = session.graph, session.schema
    findings: list[Finding] = []
    for node in graph.nodes:
        if node.node_id is None:
            continue  # an anonymous node cannot be referenced back
        for prop, values in sorted(node.props.items()):
            prop_def = schema.properties.get(prop)
            if prop_def is None or prop_def.inverse is None:
                continue
            inverse = prop_def.inverse
            for value in values:
                if not isinstance(value, (str, NestedRef)):
                    continue
                target = graph.resolve(value)
                if target is None:
                    continue  # outside the payload: check 3 reports it
                value_text = value if isinstance(value, str) else target.label
                if inverse not in target.props:
                    findings.append(
                        Finding(
                            code="INVERSE_ONE_DIRECTION",
                            severity=Severity.INFO,
                            entity=node.label,
                            prop=prop,
                            value=value_text,
                            message=(
                                f"{node.label} asserts {prop} but {target.label} does not "
                                f"assert the declared inverse {inverse}. One direction "
                                "alone is not an error."
                            ),
                            rule=rules.inverse_rule(prop, inverse),
                        )
                    )
                elif not _references_node(target.props[inverse], node.node_id, graph):
                    findings.append(
                        Finding(
                            code="INVERSE_MISMATCH",
                            severity=Severity.ERROR,
                            entity=node.label,
                            prop=prop,
                            value=value_text,
                            message=(
                                f"{node.label} asserts {prop} {value_text}, but "
                                f"{target.label} asserts {inverse} without pointing back "
                                f"at {node.node_id}. Both directions are present and they "
                                "disagree."
                            ),
                            rule=rules.inverse_rule(prop, inverse),
                        )
                    )
    return findings
