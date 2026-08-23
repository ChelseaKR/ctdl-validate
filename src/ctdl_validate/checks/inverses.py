"""Check 5: inverse consistency.

Only pairs the schema itself declares with owl:inverseOf are checked. Where
both directions are present between two in-payload entities, they must agree
(ERROR when they do not). Where only one direction is present, that is INFO,
not an error: publishing one direction is normal.
"""

from __future__ import annotations

from .. import rules
from ..findings import Finding, Severity
from ..graph import NestedRef
from ..session import Session


def _asserts_back(values: tuple[object, ...], node_id: str) -> bool:
    """Whether any raw property value identifies the node ``node_id`` names.

    A value is either the plain IRI/blank-node-id string a reference is
    normally written as, or a ``NestedRef`` for a value that was a nested
    object -- which carries the nested object's own ``@id`` (``target_id``)
    when it declared one. Checking only the string case (a plain ``in`` test
    against the raw tuple) misses a reference written as a full nested object
    instead of a bare ``{"@id": ...}``: a ``NestedRef`` never equals the
    string it was pointing at, so a target that legitimately points back --
    just spelled as an inline object -- was reported as not pointing back at
    all.
    """
    return any(
        value == node_id
        if isinstance(value, str)
        else isinstance(value, NestedRef) and value.target_id == node_id
        for value in values
    )


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
                elif not _asserts_back(target.props[inverse], node.node_id):
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
