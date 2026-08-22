"""Check 4: domain and range, from the schema's own declarations.

A property used on a class outside its schema:domainIncludes (including
subclasses) is an ERROR, as is a reference resolving to an in-payload entity
whose class is outside schema:rangeIncludes. Terms in the ceterms/ceasn
namespaces that the vendored schema snapshot does not declare are WARNINGs
(they may be typos or newer than the snapshot). This check also carries the
generic form of the wrong-framework-identifier bug: a Competency whose
isPartOf matches no CompetencyFramework in its own payload even though the
payload contains one.

Two range disagreements are dispositions rather than errors, because the
published sources contradict each other rather than the document contradicting
a source: ``RANGE_DOCS_CONFLICT`` for ceasn:isChildOf, and
``CONCEPT_RANGE_CONFLICT`` for the properties CTDL ranges on skos:Concept
while ranging the same kind of value on ceterms:CredentialAlignmentObject
elsewhere. Both are INFO and neither gates the exit code.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import rules
from ..findings import Finding, Severity
from ..graph import NestedRef, Node
from ..schema import ALIGNMENT_RANGE_TERM, SchemaIndex, is_checked_term, vocab_prefix
from ..session import Session

#: Documented conflicts between the schema encoding and Credential Engine's
#: own usage guidance. See rules.ISCHILDOF_RANGE_CONFLICT.
DOCUMENTED_RANGE_CONFLICTS = frozenset({("ceasn:isChildOf", "ceasn:CompetencyFramework")})

#: Classes that satisfy a declared skos:Concept range in practice even though
#: the encoding gives them no path to it. See rules.concept_range_conflict_rule.
ALIGNMENT_RANGE = frozenset({ALIGNMENT_RANGE_TERM})

#: CTDL's three version properties: each relates a resource to another version
#: of the same resource, and each declares a range that is a strict subset of
#: its own domain. Named here rather than derived because the disposition
#: rests on what a *version* is, which no part of the encoding states; the
#: classes it applies to are derived (SchemaIndex.domain_only_classes).
#: See rules.version_range_conflict_rule.
VERSION_PROPERTIES = frozenset(
    {
        "ceterms:latestVersion",
        "ceterms:nextVersion",
        "ceterms:previousVersion",
    }
)


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


@dataclass(frozen=True)
class _Target:
    """The entity a reference names, once the run has found it and typed it."""

    label: str
    types: tuple[str, ...]
    #: Empty for an in-payload target; names the supplied file otherwise, so
    #: every judgement says which document it rests on.
    origin: str
    #: What to print as the finding's value: the reference as written where
    #: there is one, the target's own label for a nested node.
    text: str


def _resolve_target(value: object, session: Session) -> _Target | None:
    """The reference's target and declared classes, or None if it cannot be judged.

    Returns None for a value that is not a reference, for one the run cannot
    see (check 3 reports that as UNVERIFIABLE, and it is not this check's job),
    and for one whose target declares no class the snapshot knows -- an
    undeclared or untyped target is not evidence of anything.
    """
    if not isinstance(value, (str, NestedRef)):
        return None
    target = session.graph.resolve(value)
    # A reference the payload does not contain is judged against the documents
    # supplied with --resolve, and only against those.
    external = session.supplied.get(value) if target is None else None
    if target is not None:
        label, declared, origin = target.label, target.types, ""
    elif external is not None:
        label, declared = external.node_id, external.types
        origin = f" That entity was read from {external.source}, supplied with --resolve."
    else:
        return None
    types = session.schema.known_types(declared)
    if not types:
        return None
    return _Target(
        label=label,
        types=types,
        origin=origin,
        text=value if isinstance(value, str) else label,
    )


def _concept_conflict(node: Node, prop: str, hit: _Target, schema: SchemaIndex) -> Finding | None:
    """A scheme-bound concept reference encoded the way the Registry encodes it.

    CTDL ranges a reference to a term from one of its own concept schemes on
    skos:Concept for some properties and on CredentialAlignmentObject for
    others, with nothing about the value to tell the families apart, and its
    published documents use CredentialAlignmentObject for both. An ERROR here
    would report Credential Engine's dominant encoding as a defect.
    """
    prop_def = schema.properties[prop]
    if not prop_def.is_scheme_bound_concept:
        return None
    if not schema.class_matches(hit.types, ALIGNMENT_RANGE):
        return None
    return Finding(
        code="CONCEPT_RANGE_CONFLICT",
        severity=Severity.INFO,
        entity=node.label,
        prop=prop,
        value=hit.text,
        message=(
            f"{prop} declares its range as skos:Concept, and this value is a "
            f"{ALIGNMENT_RANGE_TERM}. That is how the Registry's published documents "
            "encode it, and how CTDL declares the range of other properties drawing on "
            f"the same concept scheme ({', '.join(sorted(prop_def.target_scheme))}), so "
            "this is very likely correct as written. Nothing to fix unless you meant to "
            "reference a skos:Concept directly." + hit.origin
        ),
        rule=rules.concept_range_conflict_rule(
            prop, prop_def.target_scheme, schema.alignment_ranged_siblings(prop)
        ),
    )


def _version_conflict(node: Node, prop: str, hit: _Target, schema: SchemaIndex) -> Finding | None:
    """A version link the encoding admits as a subject and refuses as an object.

    CTDL's version properties declare a range that is a strict subset of their
    own domain. Where a document versions an entity with another entity of the
    same class, and that class is one the encoding dropped from the range, the
    two declarations contradict each other and the document satisfies the one
    that says this class may be versioned at all. Narrowed to a link between
    two entities of the same class, because that is the only reading under
    which the range omission is certainly the mistake: a version of a thing is
    a thing of the same kind.
    """
    if prop not in VERSION_PROPERTIES:
        return None
    dropped = schema.domain_only_classes(prop)
    asymmetric = frozenset(schema.known_types(node.types)) & frozenset(hit.types) & dropped
    if not asymmetric:
        return None
    cls = sorted(asymmetric)[0]
    return Finding(
        code="VERSION_RANGE_CONFLICT",
        severity=Severity.INFO,
        entity=node.label,
        prop=prop,
        value=hit.text,
        message=(
            f"{prop} declares {cls} in its domain and omits it from its range, so CTDL "
            f"says a {cls} may have a version while saying that version may not itself "
            f"be a {cls}. One of those two declarations is wrong, and this tool cannot "
            f"tell you which. It does not gate on it, because every class the range "
            f"does admit would make a {cls}'s version something other than a {cls}, and "
            "there is no third option to point you at." + hit.origin
        ),
        rule=rules.version_range_conflict_rule(prop, cls, dropped),
    )


def _docs_conflict(node: Node, prop: str, hit: _Target) -> Finding | None:
    """A range the encoding excludes and Credential Engine's own examples use."""
    conflict = next((t for t in hit.types if (prop, t) in DOCUMENTED_RANGE_CONFLICTS), None)
    if conflict is None:
        return None
    return Finding(
        code="RANGE_DOCS_CONFLICT",
        severity=Severity.INFO,
        entity=node.label,
        prop=prop,
        value=hit.text,
        message=(
            f"Referenced entity is a {conflict}, which the declared range of {prop} does "
            "not include, but Credential Engine's own guidance and examples use exactly "
            "this pattern." + hit.origin
        ),
        rule=rules.ISCHILDOF_RANGE_CONFLICT,
    )


def _range_violation(node: Node, prop: str, hit: _Target, schema: SchemaIndex) -> Finding:
    """No published source excuses this one: the reference is out of range."""
    return Finding(
        code="RANGE_VIOLATION",
        severity=Severity.ERROR,
        entity=node.label,
        prop=prop,
        value=hit.text,
        message=(
            f"Referenced entity {hit.label} is typed [{', '.join(hit.types)}], which is "
            f"outside the declared range of {prop}." + hit.origin
        ),
        rule=rules.range_rule(prop, schema.properties[prop].range),
    )


def _range_findings(
    node: Node, prop: str, values: tuple[object, ...], session: Session
) -> list[Finding]:
    schema = session.schema
    prop_def = schema.properties[prop]
    if not prop_def.range_has_entities:
        return []
    # A range of rdfs:Resource admits every entity there is, so nothing can
    # fall outside it. Checking a target's classes against it would invert the
    # declaration and reject everything, because no CTDL class reaches
    # rdfs:Resource by rdfs:subClassOf. See schema.UNIVERSAL_RANGE_TERMS.
    if prop_def.range_is_universal:
        return []
    findings: list[Finding] = []
    for value in values:
        hit = _resolve_target(value, session)
        if hit is None or schema.class_matches(hit.types, prop_def.range):
            continue
        # Three published sources excuse a range the encoding excludes; where
        # none of them applies, the reference is an ERROR and gates the exit
        # code. Order is immaterial: no two can match the same reference.
        findings.append(
            _concept_conflict(node, prop, hit, schema)
            or _version_conflict(node, prop, hit, schema)
            or _docs_conflict(node, prop, hit)
            or _range_violation(node, prop, hit, schema)
        )
    return findings


def _ispartof_framework_findings(node: Node, session: Session) -> list[Finding]:
    """The generic wrong-framework-identifier bug (competency extracts)."""
    graph, schema, supplied = session.graph, session.schema, session.supplied
    if not schema.class_matches(schema.known_types(node.types), frozenset({"ceasn:Competency"})):
        return []
    values = node.props.get("ceasn:isPartOf", ())
    if not values:
        return []
    framework = frozenset({"ceasn:CompetencyFramework"})
    in_payload = {
        n.node_id
        for n in graph.nodes
        if n.node_id is not None and schema.class_matches(schema.known_types(n.types), framework)
    }
    # A framework handed to the run with --resolve is as much a candidate as
    # one in the payload: the question this check asks is whether the
    # identifier names a framework the run can see, not where it came from.
    from_supplied = {
        entity.node_id
        for entity in supplied.entities.values()
        if schema.class_matches(schema.known_types(entity.types), framework)
    }
    framework_ids = in_payload | from_supplied
    if not framework_ids:
        return []  # no framework anywhere in reach: nothing to compare against
    where = "this payload" if not from_supplied else "this payload or the documents supplied"
    findings: list[Finding] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value in framework_ids:
            continue
        if graph.resolve(value) is not None or supplied.get(value) is not None:
            continue  # resolves to a non-framework: RANGE_VIOLATION covers it
        findings.append(
            Finding(
                code="ISPARTOF_FRAMEWORK_MISMATCH",
                severity=Severity.WARNING,
                entity=node.label,
                prop="ceasn:isPartOf",
                value=value,
                message=(
                    "This competency's isPartOf identifier matches no "
                    f"CompetencyFramework in {where}, although this run can see "
                    f"one ({', '.join(sorted(framework_ids))}). If this competency "
                    "belongs to that framework, this identifier is the wrong one."
                ),
                rule=rules.SAME_GRAPH_FRAMEWORK,
            )
        )
    return findings


def check(session: Session) -> list[Finding]:
    graph, schema = session.graph, session.schema
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
            findings.extend(_range_findings(node, prop, values, session))
        findings.extend(_ispartof_framework_findings(node, session))
    return findings
