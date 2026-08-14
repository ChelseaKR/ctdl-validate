"""The vocabulary-neutral item model the three markup readers share.

A ``RawItem`` is what a page literally published: a set of type IRIs, an
optional identifier, and an ordered list of property/value pairs, in whatever
vocabulary the author used. Nothing here is CTDL yet, and nothing here is
inferred: a reader that cannot determine a term's IRI records no term rather
than guessing one. The crosswalk in :mod:`ctdl_validate.extract.build` is the
only place a foreign term becomes a CTDL term, and it does so only where
Credential Engine's own schema encoding declares an equivalence.

``path`` is a deterministic locator for the item inside the page (for example
``json-ld[0].@graph[1]`` or ``microdata[0].schema:provider[0]``) so that every
note can say exactly which item it is about, with no reference to wall-clock
time, iteration order, or object identity.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

#: Reader identifiers, used in ``RawItem.fmt`` and in the block inventory.
JSON_LD = "json-ld"
MICRODATA = "microdata"
RDFA = "rdfa"


@dataclass(frozen=True)
class RawValue:
    """One property value exactly as published.

    Exactly one of ``text``, ``iri``, and ``item`` is set:

    - ``text``: a literal. ``language`` carries the language tag the markup
      declared for it (a JSON-LD ``@language``, or the nearest HTML ``lang``
      attribute), or ``None`` when the markup declared none.
    - ``iri``: the markup structurally said this value is an identifier (a
      JSON-LD ``@id``, a microdata URL property element's ``href``/``src``, an
      RDFa ``resource``). A literal that merely looks like a URL is ``text``.
    - ``item``: a nested item.
    """

    text: str | None = None
    iri: str | None = None
    item: RawItem | None = None
    language: str | None = None


@dataclass(frozen=True)
class RawItem:
    fmt: str
    path: str
    types: tuple[str, ...] = ()
    item_id: str | None = None
    props: tuple[tuple[str, RawValue], ...] = ()


def walk_items(items: Iterable[RawItem]) -> Iterator[RawItem]:
    """Every item and nested item, in document order."""
    for item in items:
        yield item
        for _, value in item.props:
            if value.item is not None:
                yield from walk_items([value.item])


def declared_types(items: Iterable[RawItem]) -> tuple[str, ...]:
    """Every type any item declared, in document order, without repeats."""
    return tuple(dict.fromkeys(term for item in walk_items(items) for term in item.types))
