"""Check 2: identifier kind.

For properties the CTDL context declares as identifier-valued ({"@type":
"@id"}) whose schema range includes entity classes, each string value must be
an identifier of the right kind: an IRI or a blank node identifier. A bare
UUID (the ce- prefix missing entirely) is the exact bug class of writing a
generated UUID where a CTID-based identifier belongs; a bare CTID is the
right kind but not yet an IRI.
"""

from __future__ import annotations

from .. import rules
from ..ctid import BARE_UUID_ANY_CASE_RE, CTID_ANY_CASE_RE, REGISTRY_RESOURCE_PREFIX
from ..findings import Finding, Severity
from ..graph import NestedRef
from ..session import Session


def _looks_like_iri(value: str) -> bool:
    # An IRI here means: has a scheme, or is a blank node identifier. This is
    # deliberately loose; the point is to catch values that are plainly not
    # identifiers, not to fully validate IRIs.
    return value.startswith("_:") or ":" in value


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
                if isinstance(value, NestedRef) or not isinstance(value, str):
                    continue
                if BARE_UUID_ANY_CASE_RE.match(value):
                    findings.append(
                        Finding(
                            code="REF_BARE_UUID",
                            severity=Severity.ERROR,
                            entity=entity,
                            prop=prop,
                            value=value,
                            message=(
                                "Bare UUID where an entity identifier belongs. This "
                                "property takes an IRI; for Registry resources that is "
                                f"{REGISTRY_RESOURCE_PREFIX}<CTID>."
                            ),
                            rule=rules.id_coercion_rule(prop),
                        )
                    )
                elif CTID_ANY_CASE_RE.match(value):
                    findings.append(
                        Finding(
                            code="REF_BARE_CTID",
                            severity=Severity.WARNING,
                            entity=entity,
                            prop=prop,
                            value=value,
                            message=(
                                "Bare CTID where an IRI belongs: right identifier kind, "
                                "wrong form. Registry references use the CTID-based URI "
                                f"{REGISTRY_RESOURCE_PREFIX}<CTID>."
                            ),
                            rule=rules.CTID_URI_STRUCTURE,
                        )
                    )
                elif not _looks_like_iri(value):
                    findings.append(
                        Finding(
                            code="REF_NOT_IRI",
                            severity=Severity.WARNING,
                            entity=entity,
                            prop=prop,
                            value=value,
                            message=(
                                "Value of an identifier-valued property is neither an IRI "
                                "nor a blank node identifier."
                            ),
                            rule=rules.id_coercion_rule(prop),
                        )
                    )
    return findings
