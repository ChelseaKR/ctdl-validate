"""Reader 1: ``<script type="application/ld+json">`` blocks.

Like :mod:`ctdl_validate.graph`, this is deliberately not a general JSON-LD
processor. It reads the subset that appears in published pages: a top-level
object, an array, or an object with ``@graph``; ``@type``/``@id`` keys;
prefixed or bare term keys; nested objects; ``@value``/``@language`` objects.

The one judgment call is what a bare key such as ``"name"`` means, and it is
answered from the block's own ``@context`` rather than by assumption. A
context this tool recognizes (schema.org, CTDL, CTDL-ASN, or an inline
``@vocab``/prefix map) resolves bare keys; anything else leaves them unread
and says so. Guessing the vocabulary would invent the meaning of the data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .. import rules
from ..findings import Severity
from ..schema import SchemaIndex
from .items import JSON_LD, RawItem, RawValue
from .report import Note
from .terms import SCHEMA_ORG_HTTPS, normalize_term

#: ``@context`` values that identify schema.org. schema.org publishes its
#: context at these IRIs and pages use all of these spellings.
SCHEMA_ORG_CONTEXTS = frozenset(
    {
        "http://schema.org",
        "https://schema.org",
        "http://schema.org/",
        "https://schema.org/",
        "http://schema.org/docs/jsonldcontext.json",
        "https://schema.org/docs/jsonldcontext.json",
    }
)

#: ``@context`` values that identify the CTDL vocabularies. Their terms are
#: written prefixed (``ceterms:name``), so they need no default vocabulary.
CTDL_CONTEXTS = frozenset({rules.CTDL_CONTEXT_URL, rules.CTDLASN_CONTEXT_URL})

_CONTEXT_EXCERPT = 80


@dataclass
class ActiveContext:
    """What the block's ``@context`` established, and nothing more."""

    vocab: str | None = None
    language: str | None = None
    prefixes: dict[str, str] = field(default_factory=dict)
    terms: dict[str, str] = field(default_factory=dict)
    resolved: bool = False

    def expand(self, key: str) -> str | None:
        """The IRI or CURIE a key denotes, or None when the context is silent."""
        defined = self.terms.get(key)
        if defined is not None:
            return defined
        prefix, separator, local = key.partition(":")
        if separator:
            namespace = self.prefixes.get(prefix)
            return namespace + local if namespace else key
        if self.vocab is not None:
            return self.vocab + key
        return None


def _merge_named_context(active: ActiveContext, name: str) -> None:
    """A ``@context`` that is a URL: recognized by identity, never fetched."""
    if name in SCHEMA_ORG_CONTEXTS:
        active.vocab = SCHEMA_ORG_HTTPS
        active.resolved = True
    elif name in CTDL_CONTEXTS:
        # CTDL documents write their terms prefixed, so no default vocabulary
        # is needed and none is assumed.
        active.resolved = True


def _merge_inline_context(active: ActiveContext, raw: dict[str, Any]) -> None:
    for key, value in raw.items():
        if key == "@vocab" and isinstance(value, str):
            active.vocab = value
        elif key == "@language" and isinstance(value, str):
            active.language = value
        elif key.startswith("@"):
            continue
        elif isinstance(value, str):
            active.prefixes[key] = value
        elif isinstance(value, dict) and isinstance(value.get("@id"), str):
            active.terms[key] = value["@id"]
    active.resolved = active.resolved or bool(
        active.vocab or active.prefixes or active.terms or active.language
    )


def _merge_context(active: ActiveContext, raw: Any) -> None:
    if isinstance(raw, str):
        _merge_named_context(active, raw)
    elif isinstance(raw, dict):
        _merge_inline_context(active, raw)


def read_context(raw: Any) -> ActiveContext:
    active = ActiveContext()
    for entry in raw if isinstance(raw, list) else [raw]:
        _merge_context(active, entry)
    return active


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _literal(value: Any) -> str | None:
    """A scalar rendered exactly as JSON writes it; anything else is not a literal."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return json.dumps(value)
    return None


class _BlockReader:
    """Reads one JSON-LD block into items, collecting notes as it goes."""

    def __init__(self, schema: SchemaIndex, context: ActiveContext, block_path: str) -> None:
        self.schema = schema
        self.context = context
        self.block_path = block_path

    def _term(self, key: str) -> str | None:
        expanded = self.context.expand(key)
        return None if expanded is None else normalize_term(expanded, self.schema)

    def _value(self, raw: Any, path: str) -> RawValue | None:
        if isinstance(raw, dict):
            if "@value" in raw:
                text = _literal(raw["@value"])
                language = raw.get("@language")
                return (
                    None
                    if text is None
                    else RawValue(
                        text=text,
                        language=language if isinstance(language, str) else self.context.language,
                    )
                )
            if set(raw) == {"@id"} and isinstance(raw["@id"], str):
                return RawValue(iri=raw["@id"])
            return RawValue(item=self.read_item(raw, path))
        text = _literal(raw)
        return None if text is None else RawValue(text=text, language=self.context.language)

    def _language_map(self, term: str, raw: Any) -> bool:
        """True for ``{"en": "..."}`` under a property CTDL declares as a map.

        The CTDL context declares 80 properties with ``{"@container":
        "@language"}``, and a page publishing CTDL directly writes them as
        language maps. Without this the map would be read as a nested item.
        """
        definition = self.schema.properties.get(term)
        return (
            definition is not None
            and definition.language_map
            and isinstance(raw, dict)
            and all(not key.startswith("@") for key in raw)
        )

    def _entry_values(self, term: str, raw: Any, path: str) -> list[RawValue]:
        if self._language_map(term, raw):
            return [
                RawValue(text=text, language=language)
                for language, entry in raw.items()
                for text in [_literal(item) for item in _as_list(entry)]
                if text is not None
            ]
        value = self._value(raw, path)
        return [] if value is None else [value]

    def _values(self, term: str, raw: Any, path: str) -> list[tuple[str, RawValue]]:
        pairs: list[tuple[str, RawValue]] = []
        for index, entry in enumerate(_as_list(raw)):
            for value in self._entry_values(term, entry, f"{path}.{term}[{index}]"):
                pairs.append((term, value))
        return pairs

    def read_item(self, obj: dict[str, Any], path: str) -> RawItem:
        raw_types = obj.get("@type")
        type_list = raw_types if isinstance(raw_types, list) else [raw_types]
        types = tuple(
            term
            for term in (self._term(t) for t in type_list if isinstance(t, str))
            if term is not None
        )
        props: list[tuple[str, RawValue]] = []
        for key, raw in obj.items():
            if key.startswith("@"):
                continue
            term = self._term(key)
            if term is None:
                continue
            props.extend(self._values(term, raw, path))

        item_id = obj.get("@id")
        return RawItem(
            fmt=JSON_LD,
            path=path,
            types=types,
            item_id=item_id if isinstance(item_id, str) else None,
            props=tuple(props),
        )


def _top_level(data: Any, block_path: str) -> list[tuple[dict[str, Any], str]]:
    if isinstance(data, dict) and isinstance(data.get("@graph"), list):
        graph: list[Any] = data["@graph"]
        return [
            (entry, f"{block_path}.@graph[{index}]")
            for index, entry in enumerate(graph)
            if isinstance(entry, dict)
        ]
    if isinstance(data, list):
        return [
            (entry, f"{block_path}[{index}]")
            for index, entry in enumerate(data)
            if isinstance(entry, dict)
        ]
    if isinstance(data, dict):
        return [(data, block_path)]
    return []


def _context_note(raw_context: Any, block_path: str) -> Note:
    rendered = json.dumps(raw_context, sort_keys=True) if raw_context is not None else "(absent)"
    if len(rendered) > _CONTEXT_EXCERPT:
        rendered = rendered[:_CONTEXT_EXCERPT] + "..."
    return Note(
        code="JSONLD_CONTEXT_UNRESOLVED",
        severity=Severity.WARNING,
        subject=block_path,
        term=rendered,
        detail=(
            "This block's @context is not one this tool resolves, so its unprefixed "
            "keys were left unread. Prefixed keys in the block were still read. "
            "Recognized contexts: schema.org, the CTDL and CTDL-ASN contexts, or an "
            "inline @vocab or prefix map."
        ),
        rule=rules.JSONLD_UNRESOLVED_CONTEXT,
    )


def read_block(
    source: str, block_path: str, schema: SchemaIndex
) -> tuple[list[RawItem], list[Note]]:
    """Read one JSON-LD block into its top-level items, plus any notes."""
    try:
        data = json.loads(source)
    except (json.JSONDecodeError, RecursionError) as exc:
        # RecursionError is json's answer to a block nested past the
        # interpreter's limit. Both are the same finding: unreadable, reported.
        where = (
            f" at line {exc.lineno} column {exc.colno}"
            if isinstance(exc, json.JSONDecodeError)
            else ""
        )
        note = Note(
            code="JSONLD_PARSE_ERROR",
            severity=Severity.WARNING,
            subject=block_path,
            term="application/ld+json",
            detail=(
                f"Block declares itself as application/ld+json but is not readable "
                f"JSON ({type(exc).__name__}{where}). Reported, not repaired: a block "
                "this tool guessed at would not be the block the page publishes."
            ),
            rule=rules.EXTRACTION_POLICY,
        )
        return [], [note]

    raw_context = data.get("@context") if isinstance(data, dict) else None
    context = read_context(raw_context)
    notes = [] if context.resolved else [_context_note(raw_context, block_path)]

    reader = _BlockReader(schema, context, block_path)
    top_level = [reader.read_item(obj, path) for obj, path in _top_level(data, block_path)]
    return top_level, notes
