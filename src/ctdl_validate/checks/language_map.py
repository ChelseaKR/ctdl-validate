"""Check 8: a language-map property carries a language map.

The vendored contexts declare 80 terms with ``{"@container": "@language"}``,
67 of which the schema encodings also declare as properties. The validator
already reads that declaration: ``graph.py`` keeps such a value as the map it
is instead of walking it as a nested node object. This check reports the same
reading rather than only relying on it.

**The other half of this subject is not here, and is not coming without a new
vendored file.** The contexts also declare 87 datatype coercions --
``{"@type": "xsd:date"}`` on 11 properties, ``xsd:duration`` and
``schema:Duration`` on 7, ``xsd:boolean`` on 8, and so on. Checking that a
value coerced to ``xsd:date`` *is* a date means knowing the lexical space of
``xsd:date``, and nothing in ``src/ctdl_validate/vendor/`` defines it: the
only keys the four vendored files carry are the RDF, SKOS, OWL, ``meta:`` and
``vs:`` terms, with no pattern, format or lexical constraint among them.
Writing the grammar of an ISO 8601 date from memory is the rule-from-memory
the first invariant forbids, and it is not a small risk in this instance --
``xsd:date`` admits a timezone offset and a negative year, which a regexp
written from recollection reliably gets wrong. That half is blocked on
vendoring the XML Schema datatypes specification under the existing hashing
policy, and is recorded as blocked rather than approximated.

A language map is checkable without any of that, because the declaration
being violated is the one in the vendored context itself: the value is not a
map at all.
"""

from __future__ import annotations

from ..findings import Finding, Severity
from ..rules import language_map_shape_rule
from ..session import Session


def check(session: Session) -> list[Finding]:
    findings: list[Finding] = []
    for node in session.graph.nodes:
        for prop, values in node.props.items():
            prop_def = session.schema.properties.get(prop)
            if prop_def is None or not prop_def.language_map:
                continue
            for value in values:
                if isinstance(value, dict):
                    continue
                findings.append(
                    Finding(
                        code="LANGUAGE_MAP_EXPECTED",
                        severity=Severity.WARNING,
                        entity=node.label,
                        prop=prop,
                        value=str(value),
                        message=(
                            f"The context declares {prop} a language map, and this value is "
                            "a bare literal, so the text it carries states no language. "
                            'Writing it as {"en-US": ...} records the language the '
                            "declaration exists to record. Reported as a warning, not an "
                            "error, because a plain literal is still well-formed JSON-LD "
                            "and no published Credential Engine document says the Registry "
                            "rejects one here."
                        ),
                        rule=language_map_shape_rule(prop),
                    )
                )
    return findings
