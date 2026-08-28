"""Load and index the vendored CTDL and CTDL-ASN schema and context files.

The schema encodings supply class declarations (with rdfs:subClassOf),
property declarations (schema:domainIncludes, schema:rangeIncludes,
owl:inverseOf), and the JSON-LD contexts supply per-property value coercions
({"@type": "@id"} marks identifier-valued properties; {"@container":
"@language"} marks language maps). See vendor/SOURCES.md for provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

from . import rules

#: Range terms that denote literals rather than entities. Taken from the set
#: of schema:rangeIncludes values in the vendored encodings that are not
#: declared classes (xsd datatypes, rdf/rdfs literal types, schema.org
#: datatypes used by CTDL).
LITERAL_RANGE_TERMS = frozenset(
    {
        "xsd:anyURI",
        "xsd:boolean",
        "xsd:date",
        "xsd:dateTime",
        "xsd:decimal",
        "xsd:duration",
        "xsd:float",
        "xsd:integer",
        "xsd:language",
        "xsd:string",
        "rdf:langString",
        "rdfs:Literal",
        "schema:Date",
        "schema:Duration",
    }
)

#: Range terms that constrain nothing, because they admit every entity there
#: is. RDF Schema 1.1 section 3.1 defines rdfs:Resource as "the class of
#: everything" and states that "all things described by RDF are called
#: resources, and are instances of the class rdfs:Resource"
#: (https://www.w3.org/TR/rdf11-schema/#ch_resource, retrieved 2026-08-22).
#: CTDL declares it as the whole range of ceterms:hasMember,
#: ceterms:isSimilarTo and owl:sameAs, and no CTDL class reaches it by
#: rdfs:subClassOf, so matching a target's declared classes against it would
#: reject every entity rather than accept every entity.
UNIVERSAL_RANGE_TERMS = frozenset({"rdfs:Resource"})

#: Prefixes whose unknown terms are worth a WARNING. Terms in other namespaces
#: (schema.org, dct, foaf, ...) are not CTDL's to judge and are skipped.
CHECKED_PREFIXES = ("ceterms:", "ceasn:")

#: The two classes CTDL uses, inconsistently, to range a reference to a term
#: from one of its own concept schemes. See rules.CONCEPT_RANGE_CONFLICT.
CONCEPT_RANGE_TERM = "skos:Concept"
ALIGNMENT_RANGE_TERM = "ceterms:CredentialAlignmentObject"


@dataclass(frozen=True)
class ClassDef:
    term: str
    parents: tuple[str, ...]


@dataclass(frozen=True)
class PropertyDef:
    term: str
    domain: frozenset[str]
    range: frozenset[str]
    inverse: str | None
    id_coerced: bool
    language_map: bool
    #: meta:targetScheme declarations: the CTDL concept scheme(s) a value of
    #: this property is drawn from. Present on both families of concept-valued
    #: property, which is what makes it a discriminator for "this is a
    #: controlled-vocabulary term reference" independent of the declared range.
    target_scheme: frozenset[str] = frozenset()

    @property
    def range_has_entities(self) -> bool:
        """True when at least one declared range term is an entity class."""
        return bool(self.range - LITERAL_RANGE_TERMS)

    @property
    def range_is_universal(self) -> bool:
        """True when the declared range admits every entity, so it rules nothing out.

        See ``UNIVERSAL_RANGE_TERMS``. A property declared this way says
        "any resource may go here", and the honest reading of a range that
        excludes nothing is that no reference can fall outside it.
        """
        return bool(self.range & UNIVERSAL_RANGE_TERMS)

    @property
    def is_scheme_bound_concept(self) -> bool:
        """True when this property names a concept scheme and ranges on skos:Concept.

        These are the properties caught by the concept-range inconsistency
        described in ``rules.CONCEPT_RANGE_CONFLICT``: CTDL declares the same
        kind of value — a term drawn from one of its own concept schemes —
        with two incompatible ranges depending on the property.
        """
        return CONCEPT_RANGE_TERM in self.range and bool(self.target_scheme)


@dataclass(frozen=True)
class TermIndex:
    """The encoding's statements about terms, as opposed to about structure.

    Grouped into one value because they are read together and because they
    arrive together: one pass over the same ``@graph`` produces all three.
    """

    #: Concept term -> the concept scheme(s) the encoding declares it in, from
    #: ``skos:inScheme``. Absent for a term the snapshot does not declare,
    #: which is not the same as a term declared in no scheme.
    concepts: dict[str, frozenset[str]] = field(default_factory=dict)
    #: Every ``skos:ConceptScheme`` the encoding declares.
    schemes: frozenset[str] = frozenset()
    #: Every term the encoding declares ``vs:term_status vs:unstable``, of any
    #: kind: class, property, concept or concept scheme. What that status
    #: means is not recorded here, because the encoding does not say it and
    #: this tool does not guess.
    unstable: frozenset[str] = frozenset()


class SchemaIndex:
    def __init__(
        self,
        classes: dict[str, ClassDef],
        properties: dict[str, PropertyDef],
        prefixes: dict[str, str],
        terms: TermIndex | None = None,
    ) -> None:
        self.classes = classes
        self.properties = properties
        self.terms = terms if terms is not None else TermIndex()
        # Longest namespace first so the most specific prefix wins.
        self._namespaces = sorted(
            ((ns, prefix) for prefix, ns in prefixes.items()),
            key=lambda pair: -len(pair[0]),
        )
        self._ancestor_cache: dict[str, frozenset[str]] = {}

    @property
    def concepts(self) -> dict[str, frozenset[str]]:
        return self.terms.concepts

    @property
    def schemes(self) -> frozenset[str]:
        return self.terms.schemes

    @property
    def unstable(self) -> frozenset[str]:
        return self.terms.unstable

    def compact_iri(self, iri: str) -> str:
        """Compact a full IRI to prefix:local using the vendored contexts."""
        if "://" not in iri:
            return iri
        for ns, prefix in self._namespaces:
            if iri.startswith(ns) and len(iri) > len(ns):
                return f"{prefix}:{iri[len(ns) :]}"
        return iri

    def ancestors_of(self, term: str) -> frozenset[str]:
        """The class itself plus its transitive rdfs:subClassOf parents."""
        cached = self._ancestor_cache.get(term)
        if cached is not None:
            return cached
        seen: set[str] = set()
        stack = [term]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            cls = self.classes.get(current)
            if cls is not None:
                stack.extend(cls.parents)
        result = frozenset(seen)
        self._ancestor_cache[term] = result
        return result

    def class_matches(self, node_types: tuple[str, ...], allowed: frozenset[str]) -> bool:
        """True when any node type, or an ancestor of it, is in ``allowed``."""
        return any(bool(self.ancestors_of(t) & allowed) for t in node_types)

    def known_types(self, node_types: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(t for t in node_types if t in self.classes)

    def alignment_ranged_siblings(self, prop: str) -> tuple[str, ...]:
        """Properties naming the same concept scheme but ranged on the other class.

        The demonstration that CTDL's two concept ranges describe one kind of
        value: these properties draw from the *same* ``meta:targetScheme`` as
        ``prop`` and declare ``ceterms:CredentialAlignmentObject`` where
        ``prop`` declares ``skos:Concept``. Derived from the vendored snapshot
        on every call rather than written down, so refreshing the snapshot
        refreshes the evidence.
        """
        prop_def = self.properties.get(prop)
        if prop_def is None or not prop_def.target_scheme:
            return ()
        return tuple(
            sorted(
                other.term
                for other in self.properties.values()
                if other.term != prop
                and ALIGNMENT_RANGE_TERM in other.range
                and other.target_scheme & prop_def.target_scheme
            )
        )

    def domain_only_classes(self, prop: str) -> frozenset[str]:
        """Classes this property's domain admits and its own range excludes.

        Read out of the vendored snapshot on every call rather than written
        down, so refreshing the snapshot refreshes the evidence. For CTDL's
        three version properties this set is the whole of the disagreement
        described in ``rules.version_range_conflict_rule``: the encoding says
        an instance of the class may *have* a version while saying its version
        may not *be* one.
        """
        prop_def = self.properties.get(prop)
        if prop_def is None:
            return frozenset()
        return prop_def.domain - prop_def.range

    def scheme_bound_concept_properties(self) -> tuple[str, ...]:
        """Every property the concept-range conflict disposition can apply to."""
        return tuple(sorted(p.term for p in self.properties.values() if p.is_scheme_bound_concept))


@dataclass
class _Found:
    """Mutable accumulator for one pass over the vendored graphs."""

    concepts: dict[str, set[str]] = field(default_factory=dict)
    schemes: set[str] = field(default_factory=set)
    unstable: set[str] = field(default_factory=set)


def _read_vendor(relpath: str) -> Any:
    path = resources.files("ctdl_validate").joinpath("vendor").joinpath(relpath)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def vendor_graph(relpath: str) -> list[Any]:
    """The ``@graph`` array of a vendored schema encoding, unmodified.

    Exposed so the extraction crosswalk can read the same snapshot the
    validator's rules come from, rather than carrying a hand-written copy of
    Credential Engine's vocabulary alignments.
    """
    graph = _read_vendor(relpath)["@graph"]
    if not isinstance(graph, list):  # pragma: no cover - vendored files are hash-checked
        raise ValueError(f"vendored {relpath} has no @graph array")
    return graph


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _index_schema_entry(
    entry: dict[str, Any],
    classes: dict[str, ClassDef],
    raw_props: dict[str, dict[str, Any]],
    found: _Found,
) -> None:
    """Fold one @graph entry into the class and property indexes."""
    term = entry.get("@id")
    etype = entry.get("@type")
    if not isinstance(term, str):
        return
    if entry.get("vs:term_status") == "vs:unstable":
        found.unstable.add(term)
    if etype == "rdfs:Class":
        parents = tuple(
            sorted(
                set(_as_list(entry.get("rdfs:subClassOf")))
                | set(classes[term].parents if term in classes else ())
            )
        )
        classes[term] = ClassDef(term=term, parents=parents)
    elif etype == "skos:Concept":
        found.concepts.setdefault(term, set()).update(
            entry_id
            for entry_id in (
                value.get("@id") if isinstance(value, dict) else value
                for value in _as_list(entry.get("skos:inScheme"))
            )
            if isinstance(entry_id, str)
        )
    elif etype == "skos:ConceptScheme":
        found.schemes.add(term)
    elif etype == "rdf:Property":
        merged = raw_props.setdefault(term, {"domain": set(), "range": set(), "scheme": set()})
        merged["domain"].update(_as_list(entry.get("schema:domainIncludes")))
        merged["range"].update(_as_list(entry.get("schema:rangeIncludes")))
        merged["scheme"].update(_as_list(entry.get("meta:targetScheme")))
        inverse = _as_list(entry.get("owl:inverseOf"))
        if inverse:
            merged["inverse"] = inverse[0]


@lru_cache(maxsize=1)
def load_schema() -> SchemaIndex:
    classes: dict[str, ClassDef] = {}
    raw_props: dict[str, dict[str, Any]] = {}
    found = _Found()

    for relpath in ("ctdl/schema.json", "ctdlasn/schema.json"):
        for entry in vendor_graph(relpath):
            _index_schema_entry(entry, classes, raw_props, found)

    coercions: dict[str, dict[str, Any]] = {}
    prefixes: dict[str, str] = {}
    for relpath in ("ctdl/context.json", "ctdlasn/context.json"):
        context = _read_vendor(relpath)["@context"]
        for key, value in context.items():
            if isinstance(value, str):
                prefixes.setdefault(key, value)
            elif isinstance(value, dict):
                coercions.setdefault(key, value)

    properties: dict[str, PropertyDef] = {}
    for term, merged in raw_props.items():
        coercion = coercions.get(term, {})
        properties[term] = PropertyDef(
            term=term,
            domain=frozenset(merged["domain"]),
            range=frozenset(merged["range"]),
            inverse=merged.get("inverse"),
            id_coerced=coercion.get("@type") == "@id",
            language_map=coercion.get("@container") == "@language",
            target_scheme=frozenset(merged["scheme"]),
        )

    return SchemaIndex(
        classes=classes,
        properties=properties,
        prefixes=prefixes,
        terms=TermIndex(
            concepts={term: frozenset(scheme) for term, scheme in found.concepts.items()},
            schemes=frozenset(found.schemes),
            unstable=frozenset(found.unstable),
        ),
    )


def is_checked_term(term: str) -> bool:
    return term.startswith(CHECKED_PREFIXES)


def vocab_prefix(term: str) -> str:
    return term.split(":", 1)[0]


__all__ = [
    "ALIGNMENT_RANGE_TERM",
    "CHECKED_PREFIXES",
    "CONCEPT_RANGE_TERM",
    "LITERAL_RANGE_TERMS",
    "UNIVERSAL_RANGE_TERMS",
    "ClassDef",
    "PropertyDef",
    "SchemaIndex",
    "TermIndex",
    "is_checked_term",
    "load_schema",
    "rules",
    "vendor_graph",
    "vocab_prefix",
]
