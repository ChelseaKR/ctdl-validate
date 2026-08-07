"""Check 4: domain and range, from the schema's own declarations.

A property used on a class outside its schema:domainIncludes (including
subclasses) is an ERROR, as is a reference resolving to an in-payload entity
whose class is outside schema:rangeIncludes. Terms in the ceterms/ceasn
namespaces that the vendored schema snapshot does not declare are WARNINGs
(they may be typos or newer than the snapshot). This check also carries the
generic form of the wrong-framework-identifier bug: a Competency whose
isPartOf matches no CompetencyFramework in its own payload even though the
payload contains one.
"""

from __future__ import annotations

from .. import rules
from ..findings import Finding, Severity
from ..graph import Graph, NestedRef, Node
from ..schema import SchemaIndex, is_checked_term, vocab_prefix

#: Documented conflicts between the schema encoding and Credential Engine's
#: own usage guidance. See rules.ISCHILDOF_RANGE_CONFLICT.
DOCUMENTED_RANGE_CONFLICTS = frozenset({("ceasn:isChildOf", "ceasn:CompetencyFramework")})


def _unknown_type_findings(node: Node, schema: SchemaIndex) -> list[Finding]:
    findings: list[Finding] = []
    for node_type in node.types:
        if is_checked_term(node_type) and node_type not in schema.classes:
            findings.append(
                Finding(
                    code="UNKNOWN_CLASS",
                    severity=Severity.WARNING,
                    entity=node.label,
                    prop="@type",
                    value=node_type,
                    message="Class is not declared in the vendored schema snapshot.",
                    rule=rules.unknown_term_rule("class", vocab_prefix(node_type)),
                )
            )
    return findings


def _range_findings(
    node: Node, prop: str, values: tuple[object, ...], graph: Graph, schema: SchemaIndex
) -> list[Finding]:
    prop_def = schema.properties[prop]
    if not prop_def.range_has_entities:
        return []
    findings: list[Finding] = []
    for value in values:
        if not isinstance(value, (str, NestedRef)):
            continue
        target = graph.resolve(value)
        if target is None:
            continue  # resolution is check 3's job
        target_types = schema.known_types(target.types)
        if not target_types:
            continue  # cannot judge an undeclared or untyped target
        if schema.class_matches(target_types, prop_def.range):
            continue
        value_text = value if isinstance(value, str) else target.label
        conflict = next((t for t in target_types if (prop, t) in DOCUMENTED_RANGE_CONFLICTS), None)
        if conflict is not None:
            findings.append(
                Finding(
                    code="RANGE_DOCS_CONFLICT",
                    severity=Severity.INFO,
                    entity=node.label,
                    prop=prop,
                    value=value_text,
                    message=(
                        f"Referenced entity is a {conflict}, which the declared range of "
                        f"{prop} does not include, but Credential Engine's own guidance "
                        "and examples use exactly this pattern."
                    ),
                    rule=rules.ISCHILDOF_RANGE_CONFLICT,
                )
            )
        else:
            findings.append(
                Finding(
                    code="RANGE_VIOLATION",
                    severity=Severity.ERROR,
                    entity=node.label,
                    prop=prop,
                    value=value_text,
                    message=(
                        f"Referenced entity {target.label} is typed "
                        f"[{', '.join(target_types)}], which is outside the declared "
                        f"range of {prop}."
                    ),
                    rule=rules.range_rule(prop, prop_def.range),
                )
            )
    return findings


def _ispartof_framework_findings(node: Node, graph: Graph, schema: SchemaIndex) -> list[Finding]:
    """The generic wrong-framework-identifier bug (competency extracts)."""
    if not schema.class_matches(schema.known_types(node.types), frozenset({"ceasn:Competency"})):
        return []
    values = node.props.get("ceasn:isPartOf", ())
    if not values:
        return []
    framework_ids = {
        n.node_id
        for n in graph.nodes
        if n.node_id is not None
        and schema.class_matches(
            schema.known_types(n.types), frozenset({"ceasn:CompetencyFramework"})
        )
    }
    if not framework_ids:
        return []  # no framework in the payload: nothing to compare against
    findings: list[Finding] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value in framework_ids:
            continue
        if graph.resolve(value) is not None:
            continue  # resolves in-payload to a non-framework: RANGE_VIOLATION covers it
        findings.append(
            Finding(
                code="ISPARTOF_FRAMEWORK_MISMATCH",
                severity=Severity.WARNING,
                entity=node.label,
                prop="ceasn:isPartOf",
                value=value,
                message=(
                    "This competency's isPartOf identifier matches no "
                    "CompetencyFramework in this payload, although the payload contains "
                    f"one ({', '.join(sorted(framework_ids))}). If this competency "
                    "belongs to that framework, this identifier is the wrong one."
                ),
                rule=rules.SAME_GRAPH_FRAMEWORK,
            )
        )
    return findings


def check(graph: Graph, schema: SchemaIndex) -> list[Finding]:
    findings: list[Finding] = []
    for node in graph.nodes:
        findings.extend(_unknown_type_findings(node, schema))
        node_types = schema.known_types(node.types)
        for prop, values in sorted(node.props.items()):
            prop_def = schema.properties.get(prop)
            if prop_def is None:
                if is_checked_term(prop):
                    findings.append(
                        Finding(
                            code="UNKNOWN_PROPERTY",
                            severity=Severity.WARNING,
                            entity=node.label,
                            prop=prop,
                            value="-",
                            message=("Property is not declared in the vendored schema snapshot."),
                            rule=rules.unknown_term_rule("property", vocab_prefix(prop)),
                        )
                    )
                continue
            if (
                node_types
                and prop_def.domain
                and not schema.class_matches(node_types, prop_def.domain)
            ):
                findings.append(
                    Finding(
                        code="DOMAIN_VIOLATION",
                        severity=Severity.ERROR,
                        entity=node.label,
                        prop=prop,
                        value=f"@type=[{', '.join(node_types)}]",
                        message=(
                            f"{prop} is not declared for class(es) [{', '.join(node_types)}]."
                        ),
                        rule=rules.domain_rule(prop, prop_def.domain),
                    )
                )
            findings.extend(_range_findings(node, prop, values, graph, schema))
        findings.extend(_ispartof_framework_findings(node, graph, schema))
    return findings
