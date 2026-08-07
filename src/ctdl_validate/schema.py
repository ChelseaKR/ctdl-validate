"""Load and index the vendored CTDL and CTDL-ASN schema and context files.

The schema encodings supply class declarations (with rdfs:subClassOf),
property declarations (schema:domainIncludes, schema:rangeIncludes,
owl:inverseOf), and the JSON-LD contexts supply per-property value coercions
({"@type": "@id"} marks identifier-valued properties; {"@container":
"@language"} marks language maps). See vendor/SOURCES.md for provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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

#: Prefixes whose unknown terms are worth a WARNING. Terms in other namespaces
#: (schema.org, dct, foaf, ...) are not CTDL's to judge and are skipped.
CHECKED_PREFIXES = ("ceterms:", "ceasn:")


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

    @property
    def range_has_entities(self) -> bool:
        """True when at least one declared range term is an entity class."""
        return bool(self.range - LITERAL_RANGE_TERMS)


class SchemaIndex:
    def __init__(
        self,
        classes: dict[str, ClassDef],
        properties: dict[str, PropertyDef],
        prefixes: dict[str, str],
    ) -> None:
        self.classes = classes
        self.properties = properties
        # Longest namespace first so the most specific prefix wins.
        self._namespaces = sorted(
            ((ns, prefix) for prefix, ns in prefixes.items()),
            key=lambda pair: -len(pair[0]),
        )
        self._ancestor_cache: dict[str, frozenset[str]] = {}

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


def _read_vendor(relpath: str) -> Any:
    path = resources.files("ctdl_validate").joinpath("vendor").joinpath(relpath)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
) -> None:
    """Fold one @graph entry into the class and property indexes."""
    term = entry.get("@id")
    etype = entry.get("@type")
    if not isinstance(term, str):
        return
    if etype == "rdfs:Class":
        parents = tuple(
            sorted(
                set(_as_list(entry.get("rdfs:subClassOf")))
                | set(classes[term].parents if term in classes else ())
            )
        )
        classes[term] = ClassDef(term=term, parents=parents)
    elif etype == "rdf:Property":
        merged = raw_props.setdefault(term, {"domain": set(), "range": set()})
        merged["domain"].update(_as_list(entry.get("schema:domainIncludes")))
        merged["range"].update(_as_list(entry.get("schema:rangeIncludes")))
        inverse = _as_list(entry.get("owl:inverseOf"))
        if inverse:
            merged["inverse"] = inverse[0]


@lru_cache(maxsize=1)
def load_schema() -> SchemaIndex:
    classes: dict[str, ClassDef] = {}
    raw_props: dict[str, dict[str, Any]] = {}

    for relpath in ("ctdl/schema.json", "ctdlasn/schema.json"):
        graph = _read_vendor(relpath)["@graph"]
        for entry in graph:
            _index_schema_entry(entry, classes, raw_props)

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
        )

    return SchemaIndex(classes=classes, properties=properties, prefixes=prefixes)


def is_checked_term(term: str) -> bool:
    return term.startswith(CHECKED_PREFIXES)


def vocab_prefix(term: str) -> str:
    return term.split(":", 1)[0]


__all__ = [
    "CHECKED_PREFIXES",
    "LITERAL_RANGE_TERMS",
    "ClassDef",
    "PropertyDef",
    "SchemaIndex",
    "is_checked_term",
    "load_schema",
    "rules",
    "vocab_prefix",
]
