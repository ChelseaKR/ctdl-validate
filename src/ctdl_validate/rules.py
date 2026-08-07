"""Rule citations.

Every check in this tool cites one of these rules, and every rule quotes or
paraphrases a specific published source with its URL and retrieval date. No
grammar or constraint is encoded from memory. The vendored copies of the two
machine-readable sources live in ``ctdl_validate/vendor/`` (see SOURCES.md
there for hashes).
"""

from __future__ import annotations

from .findings import Rule

RETRIEVED = "2026-08-06"

CTDL_SCHEMA_URL = "https://credreg.net/ctdl/schema/encoding/json"
CTDLASN_SCHEMA_URL = "https://credreg.net/ctdlasn/schema/encoding/json"
CTDL_CONTEXT_URL = "https://credreg.net/ctdl/schema/context/json"
CTDLASN_CONTEXT_URL = "https://credreg.net/ctdlasn/schema/context/json"
ABOUT_CTID_URL = "https://credreg.net/ctdl/ctid"
HANDBOOK_URL = "https://credreg.net/ctdl/handbook"
RFC_4122_URL = "https://www.rfc-editor.org/rfc/rfc4122"


def _vocab_schema_url(term: str) -> str:
    return CTDLASN_SCHEMA_URL if term.startswith("ceasn:") else CTDL_SCHEMA_URL


def _vocab_context_url(term: str) -> str:
    return CTDLASN_CONTEXT_URL if term.startswith("ceasn:") else CTDL_CONTEXT_URL


CTID_STRUCTURE = Rule(
    citation=(
        'About the CTID, section "CTID Structure": "Each CTID is made up of a standard '
        'UUID v4 prefixed with ce-" for "a total of 39 characters (34 hexadecimal '
        'characters and 5 hyphens)", in the form ce- plus 8-4-4-4-12 hexadecimal digits. '
        "Example given: ce-e8a41a52-6ff6-48f0-9872-889c87b093b7."
    ),
    url=ABOUT_CTID_URL,
    retrieved=RETRIEVED,
)

CTID_URI_STRUCTURE = Rule(
    citation=(
        'About the CTID, section "CTID-Based URI Structure": Registry URIs are constructed '
        "from https://credentialengineregistry.org plus /resources/ or /graph/ plus the "
        "CTID itself, and \"the value of a resource's CTID property will exactly match the "
        "CTID portion of that resource's URI\"."
    ),
    url=ABOUT_CTID_URL,
    retrieved=RETRIEVED,
)

CTID_LOWERCASE = Rule(
    citation=(
        'RFC 4122 section 3 defines UUID text form with hexadecimal digits "output as lower '
        'case characters and ... case insensitive on input"; every CTID example published '
        "on the About the CTID page is lower case."
    ),
    url=RFC_4122_URL,
    retrieved=RETRIEVED,
)

BNODE_SCOPE = Rule(
    citation=(
        'CTDL All Schemas Handbook, "Blank Node Identifier": a blank node "is only '
        "identified, referenced, or retrievable in the context of the graph in which it "
        'is found". A blank node identifier that its own payload does not define '
        "identifies nothing."
    ),
    url=HANDBOOK_URL,
    retrieved=RETRIEVED,
)

SAME_GRAPH_FRAMEWORK = Rule(
    citation=(
        'ceasn:isPartOf is defined as "Competency framework that this competency is a part '
        'of" (CTDL-ASN schema), and the CTDL Handbook states: "In the Registry, Competency '
        "Frameworks and their member Competencies are published in the same JSON-LD "
        'Graph". A member competency whose isPartOf identifier matches no framework in '
        "its own payload very likely carries the wrong identifier."
    ),
    url=HANDBOOK_URL,
    retrieved=RETRIEVED,
)

NO_NETWORK_POLICY = Rule(
    citation=(
        "ctdl-validate policy: no network access at validation time. A reference that "
        "points outside the submitted payload cannot be confirmed or denied, so it is "
        "reported UNVERIFIABLE, never as a pass or a fail."
    ),
    url="README.md (Methodology)",
    retrieved="-",
)

ISCHILDOF_RANGE_CONFLICT = Rule(
    citation=(
        "Conflicting authoritative sources: the CTDL-ASN schema encoding does not list "
        "ceasn:CompetencyFramework in schema:rangeIncludes of ceasn:isChildOf, but the "
        "ceasn:isPartOf usage note instructs top-level statements to use isChildOf, and "
        "the CTDL Handbook's own examples point isChildOf at the framework. Reported as "
        "INFO, not an error, because the sources disagree."
    ),
    url=CTDLASN_SCHEMA_URL,
    retrieved=RETRIEVED,
)


def id_coercion_rule(prop: str) -> Rule:
    return Rule(
        citation=(
            f'The CTDL JSON-LD context declares {prop} with {{"@type": "@id"}}: its values '
            "are IRIs that identify entities, not literals. For Registry resources the "
            "IRI form is the CTID-based URI (see About the CTID)."
        ),
        url=_vocab_context_url(prop),
        retrieved=RETRIEVED,
    )


def _abbreviate(terms: frozenset[str], limit: int = 6) -> str:
    ordered = sorted(terms)
    shown = ", ".join(ordered[:limit])
    if len(ordered) > limit:
        shown += f", ... ({len(ordered)} classes total)"
    return shown


def domain_rule(prop: str, domain: frozenset[str]) -> Rule:
    return Rule(
        citation=(
            f"{prop} declares schema:domainIncludes [{_abbreviate(domain)}] in the schema "
            "encoding; the subject's class is not among them or their subclasses."
        ),
        url=_vocab_schema_url(prop),
        retrieved=RETRIEVED,
    )


def range_rule(prop: str, rng: frozenset[str]) -> Rule:
    return Rule(
        citation=(
            f"{prop} declares schema:rangeIncludes [{_abbreviate(rng)}] in the schema "
            "encoding; the referenced entity's class is not among them or their subclasses."
        ),
        url=_vocab_schema_url(prop),
        retrieved=RETRIEVED,
    )


def inverse_rule(prop: str, inverse: str) -> Rule:
    return Rule(
        citation=(
            f"{prop} declares owl:inverseOf {inverse} in the schema encoding: if A {prop} B "
            f"is asserted, then B {inverse} A must hold wherever both directions are stated."
        ),
        url=_vocab_schema_url(prop),
        retrieved=RETRIEVED,
    )


def unknown_term_rule(kind: str, vocab_prefix: str) -> Rule:
    url = CTDLASN_SCHEMA_URL if vocab_prefix == "ceasn" else CTDL_SCHEMA_URL
    return Rule(
        citation=(
            f"The {kind} is not declared in the vendored {vocab_prefix} schema encoding "
            f"snapshot (retrieved {RETRIEVED}). Either a typo or a term newer than the "
            "snapshot; refresh the vendored schema to rule out the latter."
        ),
        url=url,
        retrieved=RETRIEVED,
    )
