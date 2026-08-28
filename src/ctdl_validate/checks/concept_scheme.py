"""Check 7: a controlled-vocabulary value belongs to the vocabulary named for it.

48 properties in the vendored encodings declare ``meta:targetScheme``: the
concept scheme a value of that property is drawn from. The same encodings
declare, for each of 456 concepts, the scheme it belongs to. Both halves are
already vendored and hash-pinned, which is what makes this checkable with no
network access and no new source.

The check classifies every value on a scheme-bound property into exactly one
of four outcomes, and says which. Nothing is skipped silently:

- the encoding declares it, in a scheme the property names: no finding;
- the encoding declares it, in some other scheme: WARNING;
- the encoding does not declare it: UNVERIFIABLE;
- the value is an alignment object that names no target at all: UNVERIFIABLE.

The third outcome is the common one in published documents and is the reason
this check does not report ERRORs. CTDL's alignment objects exist partly to
point *outside* CTDL, and the Registry's own documents use these properties to
reference O*NET occupations, CIP program codes and NAICS industry codes. This
tool has not vendored those frameworks, so the honest report is that it did not
check the value.
"""

from __future__ import annotations

from ..findings import Finding, Severity
from ..graph import Graph, NestedRef
from ..rules import CONCEPT_OUTSIDE_SNAPSHOT, concept_scheme_rule
from ..schema import SchemaIndex
from ..session import Session

#: The property an alignment object carries its term identifier on.
TARGET_NODE = "ceterms:targetNode"

#: What an alignment object carries when it names its term in words instead.
TARGET_NODE_NAME = "ceterms:targetNodeName"


def _terms(value: object, graph: Graph) -> tuple[list[str], bool]:
    """The term identifiers a value states, and whether it named none at all.

    A scheme-bound value is written either as the term itself or as an
    alignment object carrying it on ``ceterms:targetNode``. The second element
    is True for an alignment object that carries no target: it states a term
    by label, which is not something membership can be decided from.
    """
    if isinstance(value, str):
        return [value], False
    if not isinstance(value, NestedRef):
        return [], False
    target = graph.by_path.get(value.target_path)
    if target is None:  # pragma: no cover - every NestedRef is registered by the builder
        return [], False
    stated = [item for item in target.props.get(TARGET_NODE, ()) if isinstance(item, str)]
    return stated, not stated


def _wrong_scheme(
    entity: str, prop: str, term: str, declared: frozenset[str], schema: SchemaIndex
) -> Finding:
    wanted = schema.properties[prop].target_scheme
    return Finding(
        code="CONCEPT_OUTSIDE_SCHEME",
        severity=Severity.WARNING,
        entity=entity,
        prop=prop,
        value=term,
        message=(
            f"{term} is a concept the encoding declares in {', '.join(sorted(declared))}, "
            f"and {prop} draws from {', '.join(sorted(wanted))}. Both declarations are in "
            "the vendored snapshot, so this is a term from the wrong vocabulary for this "
            "property rather than a term the tool does not recognise. Reported as a "
            "warning, not an error, because no published Credential Engine document says "
            "the Registry enforces meta:targetScheme on ingest."
        ),
        rule=concept_scheme_rule(prop, wanted),
    )


def _not_in_snapshot(entity: str, prop: str, term: str, schema: SchemaIndex) -> Finding:
    wanted = ", ".join(sorted(schema.properties[prop].target_scheme))
    return Finding(
        code="CONCEPT_OUTSIDE_SNAPSHOT",
        severity=Severity.UNVERIFIABLE,
        entity=entity,
        prop=prop,
        value=term,
        message=(
            f"{prop} draws from {wanted}, and the vendored encoding does not declare "
            f"{term} as a concept in any scheme. That is normal on this property: CTDL's "
            "alignment objects reference frameworks outside CTDL, and published Registry "
            "documents point these properties at O*NET, CIP and NAICS. This tool has not "
            "vendored those frameworks and fetches nothing, so it did not check the "
            "value. It is not reporting that the value is wrong."
        ),
        rule=CONCEPT_OUTSIDE_SNAPSHOT,
    )


def _no_target(entity: str, prop: str, schema: SchemaIndex) -> Finding:
    wanted = ", ".join(sorted(schema.properties[prop].target_scheme))
    return Finding(
        code="CONCEPT_NOT_IDENTIFIED",
        severity=Severity.UNVERIFIABLE,
        entity=entity,
        prop=prop,
        value=f"(alignment object with no {TARGET_NODE})",
        message=(
            f"This value of {prop} names its term in words rather than by identifier, so "
            f"there is nothing to match against {wanted}. Adding {TARGET_NODE} with the "
            f"concept's identifier would make it checkable; {TARGET_NODE_NAME} alone "
            "cannot be."
        ),
        rule=CONCEPT_OUTSIDE_SNAPSHOT,
    )


def check(session: Session) -> list[Finding]:
    schema = session.schema
    graph = session.graph
    findings: list[Finding] = []
    for node in graph.nodes:
        for prop, values in node.props.items():
            prop_def = schema.properties.get(prop)
            if prop_def is None or not prop_def.target_scheme:
                continue
            for value in values:
                stated, named_nothing = _terms(value, graph)
                if named_nothing:
                    findings.append(_no_target(node.label, prop, schema))
                    continue
                for term in stated:
                    declared = schema.concepts.get(term)
                    if declared is None:
                        findings.append(_not_in_snapshot(node.label, prop, term, schema))
                    elif not declared & prop_def.target_scheme:
                        findings.append(_wrong_scheme(node.label, prop, term, declared, schema))
    return findings
