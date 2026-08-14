"""The CTDL-to-other-vocabulary crosswalk, read out of the vendored schemas.

This module contains no mapping table. Credential Engine's schema encodings
already declare, in machine-readable form, which CTDL terms are equivalent to
terms in other vocabularies (``owl:equivalentClass``,
``owl:equivalentProperty``) and which CTDL terms are specializations of them
(``rdfs:subClassOf``, ``rdfs:subPropertyOf``). Extraction reads those
declarations out of the same vendored, hash-checked snapshot the validator's
rules come from, so the crosswalk is Credential Engine's, with a citation, and
refreshing the snapshot refreshes the crosswalk.

The direction matters and is kept separate on purpose:

- An **equivalence** is symmetric. ``ceterms:Course owl:equivalentClass
  schema:Course`` licenses reading a ``schema:Course`` as a ``ceterms:Course``.
- A **specialization** is not. ``ceterms:LearningProgram rdfs:subClassOf
  schema:EducationalOccupationalProgram`` says every LearningProgram is an
  EducationalOccupationalProgram, not the reverse. It is recorded here so the
  reader can be told the relation exists, and it never produces an assertion.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..schema import CHECKED_PREFIXES, vendor_graph

EQUIVALENT_CLASS = "owl:equivalentClass"
EQUIVALENT_PROPERTY = "owl:equivalentProperty"
SUBCLASS_OF = "rdfs:subClassOf"
SUBPROPERTY_OF = "rdfs:subPropertyOf"

_ENCODINGS = ("ctdl/schema.json", "ctdlasn/schema.json")


@dataclass(frozen=True)
class Crosswalk:
    """Foreign term -> the CTDL terms that declare a relation to it.

    Every mapping is keyed by the foreign term because that is the direction
    extraction reads in: a page publishes ``schema:Course`` and the question
    is what, if anything, CTDL says about it. Values are sorted so the same
    snapshot always yields the same candidate order.
    """

    equivalent_class: dict[str, tuple[str, ...]]
    equivalent_property: dict[str, tuple[str, ...]]
    specialized_class: dict[str, tuple[str, ...]]
    specialized_property: dict[str, tuple[str, ...]]

    def equivalents(self, foreign_term: str, *, is_class: bool) -> tuple[str, ...]:
        table = self.equivalent_class if is_class else self.equivalent_property
        return table.get(foreign_term, ())

    def specializations(self, foreign_term: str, *, is_class: bool) -> tuple[str, ...]:
        table = self.specialized_class if is_class else self.specialized_property
        return table.get(foreign_term, ())

    @property
    def covered_classes(self) -> tuple[str, ...]:
        return tuple(sorted(self.equivalent_class))

    @property
    def covered_properties(self) -> tuple[str, ...]:
        return tuple(sorted(self.equivalent_property))


def _values(entry: dict[str, Any], key: str) -> list[str]:
    raw = entry.get(key)
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    return [item for item in items if isinstance(item, str)]


def _is_foreign(term: str) -> bool:
    """True for a term outside the two CTDL namespaces."""
    return not term.startswith(CHECKED_PREFIXES)


def _collect(entries: Iterable[dict[str, Any]], key: str, entry_type: str) -> dict[str, list[str]]:
    collected: dict[str, list[str]] = {}
    for entry in entries:
        term = entry.get("@id")
        if not isinstance(term, str) or entry.get("@type") != entry_type:
            continue
        if _is_foreign(term):
            continue
        for foreign in _values(entry, key):
            if _is_foreign(foreign):
                collected.setdefault(foreign, []).append(term)
    return collected


def _freeze(collected: dict[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {foreign: tuple(sorted(set(terms))) for foreign, terms in sorted(collected.items())}


@lru_cache(maxsize=1)
def load_crosswalk() -> Crosswalk:
    entries: list[dict[str, Any]] = []
    for relpath in _ENCODINGS:
        entries.extend(entry for entry in vendor_graph(relpath) if isinstance(entry, dict))

    return Crosswalk(
        equivalent_class=_freeze(_collect(entries, EQUIVALENT_CLASS, "rdfs:Class")),
        equivalent_property=_freeze(_collect(entries, EQUIVALENT_PROPERTY, "rdf:Property")),
        specialized_class=_freeze(_collect(entries, SUBCLASS_OF, "rdfs:Class")),
        specialized_property=_freeze(_collect(entries, SUBPROPERTY_OF, "rdf:Property")),
    )
