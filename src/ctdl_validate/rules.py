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
        'UUID v4 prefixed with ce-", and with the prefix "there are a total of 34 '
        'hexadecimal characters and 5 hyphens for a total of 39 characters", in the '
        "form ce- plus 8-4-4-4-12 hexadecimal digits. Example given: "
        "ce-e8a41a52-6ff6-48f0-9872-889c87b093b7."
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
        "reported UNVERIFIABLE, never as a pass or a fail. --resolve widens what the "
        "run can see, using documents the operator already has; it fetches nothing."
    ),
    url="README.md (Methodology)",
    retrieved="-",
)

REPEATED_ID_POLICY = Rule(
    citation=(
        "ctdl-validate policy: one identifier, one entity. A payload may write the "
        "same @id on more than one node object; this tool reads those as a single "
        "entity, taking the union of their @type values and of their properties, and "
        "reports that it did so. It does not keep whichever declaration it parsed "
        "first and drop the rest, because that made a verdict depend on @graph array "
        "order rather than on the document. The report is a disclosure, not a defect: "
        "the tool states what it merged so a reader who did not intend one entity can "
        "see that it read one."
    ),
    url="docs/adr/0005-one-identifier-one-entity.md",
    retrieved="-",
)

RESOLUTION_POLICY = Rule(
    citation=(
        "ctdl-validate policy: --resolve is additive and is reported. A reference that "
        "resolves in a document supplied on the command line is checked against the "
        "property's declared range exactly as an in-payload reference is, and the "
        "document it resolved in is named, because every judgement that follows rests "
        "on that document having been supplied."
    ),
    url="docs/adr/0004-resolution-is-additive.md",
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


def language_map_shape_rule(prop: str) -> Rule:
    """A property the context declares a language map, cited against the context.

    Distinct from ``language_map_rule`` below, which the extractor uses to
    explain why it emitted an untagged literal from a page that declared no
    language. This one is the validator saying a payload wrote a bare literal
    where the context declares a map; the situations differ and so does the
    sentence a reader needs.

    The vendored contexts declare 80 terms with ``{"@container": "@language"}``.
    The validator already reads that declaration -- ``graph.py`` keeps such a
    value as the map it is rather than walking it as a nested node -- so this
    check is that same reading, reported instead of only relied upon.
    """
    return Rule(
        citation=(
            f'CTDL JSON-LD context: {prop} is declared {{"@container": "@language"}}, so its '
            "values are keyed by language tag. A bare literal in that position carries no "
            "language, which is the one thing the declaration exists to record."
        ),
        url=_vocab_context_url(prop),
        retrieved=RETRIEVED,
    )


def concept_scheme_rule(prop: str, scheme: frozenset[str]) -> Rule:
    """A property's meta:targetScheme, cited against the snapshot it comes from.

    The CTDL and CTDL-ASN encodings declare, for 48 properties, the concept
    scheme a value of that property is drawn from, and they declare for each
    concept the scheme it belongs to. Both halves are in the vendored files,
    which is what makes membership checkable without fetching anything.
    """
    named = ", ".join(sorted(scheme))
    return Rule(
        citation=(
            f"CTDL schema encoding: {prop} declares meta:targetScheme {named}. The same "
            "encoding declares each concept's own scheme with skos:inScheme. A value that "
            "the encoding declares in a different scheme is a term from the wrong "
            "vocabulary for this property."
        ),
        url=_vocab_schema_url(prop),
        retrieved=RETRIEVED,
    )


CONCEPT_OUTSIDE_SNAPSHOT = Rule(
    citation=(
        "ctdl-validate policy: a value on a scheme-bound property that the vendored "
        "encoding does not declare is reported UNVERIFIABLE, never as a pass or a fail. "
        "CTDL's alignment objects are built to point at frameworks outside CTDL, and the "
        "Registry's published documents do point at O*NET, CIP and NAICS on these very "
        "properties. This tool has not vendored those frameworks and does not fetch, so "
        "it can say only that it did not check the value, not that the value is wrong."
    ),
    url="README.md (Methodology)",
    retrieved="-",
)


def concept_range_conflict_rule(
    prop: str, scheme: frozenset[str], siblings: tuple[str, ...]
) -> Rule:
    """The concept-range inconsistency, cited against the snapshot it comes from.

    CTDL declares references to terms from its own concept schemes with two
    incompatible ranges. ``prop`` declares skos:Concept; other properties
    naming the same kind of value declare ceterms:CredentialAlignmentObject,
    whose only declared parent is schema:AlignmentObject — no path to
    skos:Concept exists in the encoding. The published corpus encodes both
    families as CredentialAlignmentObject, so the declaration, not the
    document, is what is inconsistent. Reported as INFO, not an error,
    because the sources disagree; see the isChildOf conflict for the same
    disposition applied to the same kind of problem.
    """
    named = ", ".join(sorted(scheme))
    if siblings:
        shown = ", ".join(siblings[:3])
        if len(siblings) > 3:
            shown += f", ... ({len(siblings)} properties total)"
        demonstration = (
            f" The same snapshot declares {shown} over the same concept scheme with "
            f"schema:rangeIncludes ceterms:CredentialAlignmentObject, so the two "
            "declarations describe one kind of value."
        )
    else:
        demonstration = (
            " Across the snapshot, CTDL ranges scheme-bound concept references on "
            "ceterms:CredentialAlignmentObject and on skos:Concept interchangeably; "
            "three concept schemes are named by properties in both families."
        )
    return Rule(
        citation=(
            f"Conflicting declarations inside the schema encoding: {prop} declares "
            f"schema:rangeIncludes skos:Concept and meta:targetScheme [{named}]."
            f"{demonstration} ceterms:CredentialAlignmentObject declares only "
            "rdfs:subClassOf schema:AlignmentObject, so it cannot satisfy a "
            "skos:Concept range on the face of the encoding. Reported as INFO, not "
            "an error, because the encoding and Credential Engine's own published "
            "documents disagree."
        ),
        url=_vocab_schema_url(prop),
        retrieved=RETRIEVED,
    )


def version_range_conflict_rule(prop: str, cls: str, dropped: frozenset[str]) -> Rule:
    """A version property whose own range excludes a class its own domain admits.

    CTDL's three version properties relate a resource to another version of
    the same resource. For each of them the encoding declares
    schema:rangeIncludes as a strict subset of schema:domainIncludes, dropping
    the same classes from all three. For a dropped class the two declarations
    cannot both be satisfied: the domain says an instance of that class may
    have a version, and the range says that version may not be an instance of
    that class, while a version of a thing is a thing of the same kind. The
    document is following the domain declaration, so the disagreement is
    inside the encoding and this is reported as INFO, not an error — the same
    disposition the isChildOf and concept-range conflicts get.
    """
    others = ", ".join(sorted(dropped - {cls}))
    return Rule(
        citation=(
            f"Conflicting declarations inside the schema encoding: {prop} declares "
            f"schema:domainIncludes {cls}, so a {cls} may have a version, and omits "
            f"{cls} from schema:rangeIncludes, so that version may not be a {cls}. "
            f"The declared range of {prop} is a strict subset of its own declared "
            f"domain; besides {cls} it also drops {others}. Reported as INFO, not an "
            "error, because the two declarations disagree with each other and the "
            "document satisfies one of them."
        ),
        url=_vocab_schema_url(prop),
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


# --------------------------------------------------------------------------
# Extraction rules
#
# The `extract` subcommand is the one place this tool touches the network, and
# the one place it reads a vocabulary that is not CTDL's. Both need the same
# citation discipline as validation: every note it emits names the published
# rule it rests on. The sources below were retrieved on the date in
# RETRIEVED_EXTRACTION; the CTDL-side rules reuse the vendored snapshot and its
# earlier retrieval date, because the crosswalk is read out of that snapshot,
# not written by hand.
# --------------------------------------------------------------------------

RETRIEVED_EXTRACTION = "2026-08-14"

ROBOTS_RFC_URL = "https://www.rfc-editor.org/rfc/rfc9309"
MICRODATA_URL = "https://html.spec.whatwg.org/multipage/microdata.html"
RDFA_LITE_URL = "https://www.w3.org/TR/rdfa-lite/"
SCHEMA_ORG_CONTEXT_URL = "https://schema.org/docs/jsonldcontext.json"

EXTRACTION_POLICY = Rule(
    citation=(
        "ctdl-validate policy: extraction reads structured markup a page already "
        "publishes and maps a term onto CTDL only where Credential Engine's own "
        "schema encoding declares an equivalence for it. Nothing is inferred from "
        "prose, from layout, or from a model. A term with no declared equivalence "
        "is reported and dropped, never guessed at and never dropped silently."
    ),
    url="README.md (Extraction)",
    retrieved="-",
)

EXTRACTION_NETWORK_POSTURE = Rule(
    citation=(
        "ctdl-validate policy: `extract` is the only command that opens a network "
        "connection. It fetches robots.txt and then at most the one page it was "
        "given, over http or https only, with an identifying User-Agent, a byte "
        "cap, a timeout, and a minimum interval between requests to a host. "
        "Validation remains offline: same input, same output, byte for byte."
    ),
    url="README.md (Extraction)",
    retrieved="-",
)

ROBOTS_RULES_BINDING = Rule(
    citation=(
        "RFC 9309 (Robots Exclusion Protocol), section 2.3.1.1 Successful Access: "
        '"If the crawler successfully downloads the robots.txt file, the crawler '
        'MUST follow the parseable rules."'
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

ROBOTS_UNAVAILABLE = Rule(
    citation=(
        'RFC 9309 section 2.3.1.3 "Unavailable" Status: "If a server status code '
        "indicates that the robots.txt file is unavailable to the crawler, then the "
        'crawler MAY access any resources on the server." Status codes in the '
        "400-499 range are given as the HTTP example."
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

ROBOTS_UNREACHABLE = Rule(
    citation=(
        'RFC 9309 section 2.3.1.4 "Unreachable" Status: "If the robots.txt file is '
        "unreachable due to server or network errors, this means the robots.txt file "
        'is undefined and the crawler MUST assume complete disallow." Server errors '
        "are identified by status codes in the 500-599 range."
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

ROBOTS_REDIRECT_LIMIT = Rule(
    citation=(
        'RFC 9309 section 2.3.1.2 Redirects: crawlers "SHOULD follow at least five '
        'consecutive redirects, even across authorities"; beyond five, a crawler MAY '
        "assume the robots.txt file is unavailable. This tool applies the same limit "
        "of five to the page fetch, and re-checks robots.txt at every hop that "
        "changes authority."
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

ROBOTS_USER_AGENT = Rule(
    citation=(
        'RFC 9309 section 2.2.1 The User-Agent Line: the product token "SHOULD be a '
        "substring of the identification string that the crawler sends to the "
        'service", and "The identification string SHOULD describe the purpose of the '
        'crawler." This tool sends the product token ctdl-validate inside a '
        "User-Agent that links to its source repository."
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

ROBOTS_CRAWL_DELAY = Rule(
    citation=(
        "RFC 9309 does not define a Crawl-delay directive; it is a widely deployed "
        "non-standard extension that Python's urllib.robotparser reads. Where a "
        "robots.txt declares one, this tool takes the larger of that value and its "
        "own default interval, so honoring the site's request can only slow it down."
    ),
    url=ROBOTS_RFC_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

MICRODATA_NAMES = Rule(
    citation=(
        "HTML Living Standard, section 5.2.3 Names: the itemprop attribute. For a "
        'typed item each token is "a defined property name allowed in this situation '
        "according to the specification that defines the relevant types for the "
        'item", or an absolute URL. On an untyped item a bare name is "used as a '
        'proprietary item property name ... not defined in a public specification", '
        "so it has no vocabulary this tool could resolve it against."
    ),
    url=MICRODATA_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

MICRODATA_VALUES = Rule(
    citation=(
        "HTML Living Standard, section 5.2.4 Values: the value of an itemprop "
        "element is the item it creates when it also carries itemscope; the content "
        "attribute for meta; the src URL for audio, embed, iframe, img, source, "
        "track, and video; the href URL for a, area, and link; the data URL for "
        "object; the value attribute for data and meter; the datetime value for "
        "time; and otherwise the element's descendant text content."
    ),
    url=MICRODATA_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

MICRODATA_ITEMREF = Rule(
    citation=(
        "HTML Living Standard, section 5.2.5 Associating names with items: itemref "
        "lets an item claim properties from elements elsewhere in the document. This "
        "tool does not follow itemref, so properties reached only that way are not "
        "read. Reported rather than silently missing."
    ),
    url=MICRODATA_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

RDFA_LITE_SUBSET = Rule(
    citation=(
        "RDFa Lite 1.1 (Second Edition), W3C Recommendation 17 March 2015, defines "
        'the five attributes vocab, typeof, property, resource, and prefix as "a '
        'minimal subset of RDFa". This tool reads exactly that subset. Attributes '
        "from RDFa 1.1 Core beyond it (about, rel, rev, datatype, inlist) are not "
        "interpreted, and a page using them is told so."
    ),
    url=RDFA_LITE_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

SCHEMA_ORG_VOCAB = Rule(
    citation=(
        'The schema.org JSON-LD context declares {"@vocab": "http://schema.org/"}, so '
        "a bare term under that context is the schema.org term of the same name. "
        "schema.org serves its vocabulary under both http and https IRIs and the "
        'CTDL context declares the schema prefix as "https://schema.org/"; this tool '
        "normalizes both forms to that prefix so the two published files agree."
    ),
    url=SCHEMA_ORG_CONTEXT_URL,
    retrieved=RETRIEVED_EXTRACTION,
)

JSONLD_UNRESOLVED_CONTEXT = Rule(
    citation=(
        "ctdl-validate policy: bare terms in a JSON-LD block mean whatever the "
        "block's active context says they mean. Where the declared @context is not "
        "one this tool can resolve (schema.org, CTDL, CTDL-ASN, or an inline @vocab "
        "or prefix map), its bare terms are left unread; assuming a vocabulary would "
        "be inventing the meaning of the data."
    ),
    url="README.md (Extraction)",
    retrieved="-",
)

CTID_NOT_INVENTED = Rule(
    citation=(
        'About the CTID: a CTID is "a unique identifier for the resource" in the '
        "Credential Registry, and a resource's CTID matches the CTID portion of its "
        "Registry URI. An extract taken from a web page has no CTID unless the page "
        "published one. This tool never generates one: a minted identifier would be "
        "indistinguishable from a real one downstream."
    ),
    url=ABOUT_CTID_URL,
    retrieved=RETRIEVED,
)


def equivalence_rule(ctdl_term: str, foreign_term: str, predicate: str) -> Rule:
    return Rule(
        citation=(
            f"The schema encoding declares {ctdl_term} {predicate} {foreign_term} "
            f"(retrieved {RETRIEVED}). The mapping is Credential Engine's, read out of "
            "the vendored snapshot, not this tool's judgment."
        ),
        url=_vocab_schema_url(ctdl_term),
        retrieved=RETRIEVED,
    )


def no_equivalence_rule(foreign_term: str, predicate: str) -> Rule:
    return Rule(
        citation=(
            f"No CTDL or CTDL-ASN term declares {predicate} {foreign_term} in the "
            f"vendored schema encodings (retrieved {RETRIEVED}). Choosing a CTDL term "
            "for it would be this tool's judgment rather than a published "
            "equivalence, so nothing is asserted."
        ),
        url=CTDL_SCHEMA_URL,
        retrieved=RETRIEVED,
    )


def ambiguous_equivalence_rule(foreign_term: str, candidates: tuple[str, ...]) -> Rule:
    listed = ", ".join(candidates)
    return Rule(
        citation=(
            f"More than one CTDL term declares an equivalence to {foreign_term} "
            f"({listed}), and the subject's class does not appear in exactly one of "
            "their schema:domainIncludes declarations. Picking one would be a guess."
        ),
        url=CTDL_SCHEMA_URL,
        retrieved=RETRIEVED,
    )


def subclass_only_rule(ctdl_term: str, foreign_term: str, predicate: str) -> Rule:
    return Rule(
        citation=(
            f"The schema encoding declares {ctdl_term} {predicate} {foreign_term}. That "
            f"relation runs from CTDL to the other vocabulary: every {ctdl_term} is a "
            f"{foreign_term}, but not every {foreign_term} is a {ctdl_term}. It does not "
            "license the reverse mapping, so the item is reported, not converted."
        ),
        url=_vocab_schema_url(ctdl_term),
        retrieved=RETRIEVED,
    )


def language_map_rule(prop: str) -> Rule:
    return Rule(
        citation=(
            f'The CTDL JSON-LD context declares {prop} with {{"@container": "@language"}}: '
            "its values are language maps keyed by language tag. The page declared no "
            "language for this value, and a language tag cannot be inferred from the "
            "text itself, so the literal is emitted untagged for a human to complete."
        ),
        url=_vocab_context_url(prop),
        retrieved=RETRIEVED,
    )
