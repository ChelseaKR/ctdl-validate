"""What one validation run has in front of it.

A CTDL payload is not the whole story about itself. Registry documents
reference other Registry documents by URI as a matter of course: a credential
names the organization that owns it, a competency names its framework, a
condition profile names the learning opportunity it requires. Check 3 reports
every one of those as ``REF_OUTSIDE_PAYLOAD`` / UNVERIFIABLE, which is the
honest answer when the referenced document is not in hand, and a permanent
non-answer when there is no way to put it there.

``--resolve`` is that way. It takes documents the operator already has and
indexes the entities they declare, so a reference into one of them stops being
unknowable and starts being checkable: check 4 can ask whether the referenced
entity is of the class the property's declared range requires.

Three properties of this design are load-bearing and are enforced by tests:

- **Nothing is fetched.** ``--resolve`` reads local files. The validator opens
  no socket in any code path, with or without it, and
  ``tests/test_offline_guarantee.py`` runs the whole thing with ``socket``
  removed from ``sys.modules``.
- **Supplied documents are never validated.** They go into a side index of
  ``@id`` to class, not into the graph being checked. Findings are reported
  against the primary payload only, so adding a neighbour can never change how
  many entities the report is about, nor put someone else's document's defects
  in your report.
- **An unresolved reference stays UNVERIFIABLE.** Supplying documents can turn
  a non-answer into an answer; it can never turn a non-answer into a failure.
  See ``docs/adr/0004-resolution-is-additive.md`` for why this tool stops
  short of the ERROR that ``oscal-validate`` raises in the same situation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .graph import DocumentError, Graph, parse_document
from .schema import SchemaIndex


@dataclass(frozen=True)
class SuppliedEntity:
    """One ``@id`` declared by a document passed with ``--resolve``."""

    node_id: str
    types: tuple[str, ...]
    #: The path the entity was read from, as given on the command line.
    source: str


@dataclass(frozen=True)
class Supplied:
    """The side index built from ``--resolve`` documents.

    ``documents`` records what was supplied even when none of it resolved
    anything, because an UNVERIFIABLE finding has to be able to say whether it
    is unverifiable for want of a document or in spite of the documents given.
    """

    documents: tuple[str, ...] = ()
    entities: dict[str, SuppliedEntity] = field(default_factory=dict)

    @property
    def any_documents(self) -> bool:
        return bool(self.documents)

    def get(self, value: Any) -> SuppliedEntity | None:
        return self.entities.get(value) if isinstance(value, str) else None

    def shortfall(self) -> str:
        """A phrase for a finding message naming what was in hand and missed."""
        count = len(self.documents)
        noun = "document" if count == 1 else "documents"
        return (
            f"None of the {count} {noun} supplied with --resolve "
            f"({', '.join(self.documents)}) declares it."
        )


@dataclass(frozen=True)
class Session:
    """The primary payload, the schema, and whatever was supplied with it.

    Every check takes one of these rather than reaching for a global, so the
    single thing that can change a finding's severity -- whether the referenced
    document was in hand -- is explicit at every use.
    """

    graph: Graph
    schema: SchemaIndex
    supplied: Supplied = field(default_factory=Supplied)


def collect_paths(paths: list[Path]) -> list[Path]:
    """Expand directories into the ``.json`` files directly inside them.

    Sorted, and one level deep only: a run must not depend on filesystem
    ordering, and walking a tree the operator did not point at is a surprise.
    """
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(p for p in path.iterdir() if p.suffix == ".json"))
        else:
            found.append(path)
    return found


def _load(path: Path, schema: SchemaIndex) -> Graph:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentError(f"cannot read {path}: {exc}") from exc
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DocumentError(f"{path} is not valid JSON: {exc}") from exc
    return parse_document(data, schema)


def build_supplied(paths: list[Path], schema: SchemaIndex) -> Supplied:
    """Index every identified entity in the supplied documents.

    Where two supplied documents declare the same ``@id``, the first in sorted
    path order wins and the second is ignored. That is a deterministic rule
    rather than a considered one: two documents disagreeing about what an
    ``@id`` is are a problem this tool does not try to adjudicate, and the
    report names the file every resolution came from so the disagreement is
    visible rather than silent.
    """
    documents: list[str] = []
    entities: dict[str, SuppliedEntity] = {}
    for path in collect_paths(paths):
        graph = _load(path, schema)
        source = str(path)
        documents.append(source)
        for node in graph.nodes:
            if node.node_id is None or node.node_id.startswith("_:"):
                continue  # blank nodes mean nothing outside the graph declaring them
            entities.setdefault(
                node.node_id,
                SuppliedEntity(node_id=node.node_id, types=node.types, source=source),
            )
    return Supplied(documents=tuple(documents), entities=entities)
