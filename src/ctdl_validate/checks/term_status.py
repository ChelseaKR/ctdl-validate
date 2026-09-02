"""Check 9: terms the published encoding marks unstable, disclosed.

Both vendored encodings carry ``vs:term_status`` on every term they declare:
675 are ``vs:stable`` and 478 are ``vs:unstable``. Nothing read either. A
payload could be built entirely from terms the vocabulary itself flags as not
settled, and this tool would have said nothing about it.

What this check must not do is say what that means. The vendored files carry
no prose defining ``vs:unstable``, and the vocabulary-status specification is
not vendored. So the finding states the declaration and stops: it does not
say the term will be withdrawn, that the Registry will reject it, or that the
payload should change. Each of those would be a rule encoded from memory, and
the first of them is not even obviously true -- an unstable term may simply be
newer than the rest of the vocabulary.

Severity is INFO for the same reason. The README defines INFO as "worth a
human look, not a defect", which is exactly the size of the claim the
evidence supports. A publisher who knows the term is unstable and wants it
anyway has not made a mistake.

Every term a payload names is covered, in whichever role it appears: as a
class on ``@type``, as a property key, or as a concept a scheme-bound property
points at.
"""

from __future__ import annotations

from ..findings import Finding, Severity
from ..graph import NestedRef
from ..rules import term_status_rule
from ..session import Session

#: The property an alignment object carries its term identifier on.
TARGET_NODE = "ceterms:targetNode"

#: Role -> the sentence naming where the term was found.
ROLES = {
    "class": "as a class on @type",
    "property": "as a property",
    "concept": "as a concept value",
}


def _finding(entity: str, prop: str, term: str, role: str) -> Finding:
    return Finding(
        code="TERM_UNSTABLE",
        severity=Severity.INFO,
        entity=entity,
        prop=prop,
        value=term,
        message=(
            f"The published encoding declares {term} vs:term_status vs:unstable, and this "
            f"payload uses it {ROLES[role]}. That is a fact about the vocabulary, not a "
            "defect in the document: the encoding does not say what an unstable term "
            "obliges a publisher to do, and this tool does not guess. Worth knowing "
            "before you build on it."
        ),
        rule=term_status_rule(term),
    )


def _concept_terms(value: object, session: Session) -> list[str]:
    """Concept identifiers a scheme-bound value states, directly or wrapped."""
    if isinstance(value, str):
        return [value]
    if not isinstance(value, NestedRef):
        return []
    target = session.graph.by_path.get(value.target_path)
    if target is None:  # pragma: no cover - every NestedRef is registered by the builder
        return []
    return [item for item in target.props.get(TARGET_NODE, ()) if isinstance(item, str)]


def check(session: Session) -> list[Finding]:
    unstable = session.schema.unstable
    findings: list[Finding] = []
    for node in session.graph.nodes:
        for declared in node.types:
            if declared in unstable:
                findings.append(_finding(node.label, "@type", declared, "class"))
        for prop, values in node.props.items():
            if prop in unstable:
                findings.append(_finding(node.label, prop, prop, "property"))
            prop_def = session.schema.properties.get(prop)
            if prop_def is None or not prop_def.target_scheme:
                continue
            for value in values:
                for term in _concept_terms(value, session):
                    if term in unstable:
                        findings.append(_finding(node.label, prop, term, "concept"))
    return findings
