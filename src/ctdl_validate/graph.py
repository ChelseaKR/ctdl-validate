"""Parse a CTDL JSON-LD document into a flat, indexable node set.

This is deliberately not a general JSON-LD processor. Registry payloads use a
small, regular subset of JSON-LD: a ``@graph`` array (or a single entity, or a
bare array of entities), prefixed term keys, string IRIs as references,
occasional inline nested objects, and language-map literals. Handling that
subset directly keeps the tool dependency-free and its behavior deterministic
and inspectable. Anything outside the subset is left alone rather than
guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import SchemaIndex


class DocumentError(ValueError):
    """The input is not a shape this tool knows how to read."""


@dataclass(frozen=True)
class NestedRef:
    """A property value that was an inline (nested) object in the document.

    The nested object is registered as a node in its own right; containment
    means the reference trivially resolves inside the payload.
    """

    target_path: str
    target_id: str | None


@dataclass
class Node:
    path: str
    node_id: str | None
    types: tuple[str, ...]
    props: dict[str, tuple[Any, ...]]

    @property
    def label(self) -> str:
        return self.node_id if self.node_id is not None else self.path


@dataclass
class Graph:
    nodes: list[Node]
    by_id: dict[str, Node]
    by_path: dict[str, Node]
    #: Identifier -> every path in the document that declared it, in walk
    #: order. An entry with more than one path is a node object written more
    #: than once; the builder merges those into a single node, and
    #: ``checks.identity`` reports that it did.
    declarations: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def repeated_ids(self) -> dict[str, tuple[str, ...]]:
        """Identifiers declared by more than one node object, with their paths."""
        return {node_id: paths for node_id, paths in self.declarations.items() if len(paths) > 1}

    def resolve(self, value: Any) -> Node | None:
        """Resolve a reference value to an in-payload node, if present.

        A nested object that carries its own ``@id`` is, by JSON-LD's own
        identity rule, the same node as anything else in the payload with that
        ``@id`` -- not a second, unrelated entity that happens to render at a
        different path. When that identifier is already registered (the usual
        case: the entity is declared once at the top level and embedded again,
        inline, wherever something points at it), resolving by identity finds
        the fully-declared node instead of the thinner duplicate ``_Builder``
        created for the nested occurrence, so every property asserted about
        the entity anywhere in the document is visible from here. Falling back
        to the path only covers a nested object with no ``@id`` at all (a
        genuinely anonymous/blank node), or one whose ``@id`` this payload
        never declares elsewhere.

        Since ADR-0005 the identity preference is belt and braces rather than
        the thing that makes this work: ``_node_for`` merges a repeated
        identifier into the node that already holds it and registers the new
        path against that merged node, so the path fallback now reaches the
        same object in every case. Kept because it is the direct statement of
        the rule, and pinned by
        ``test_an_embedded_copy_and_its_top_level_declaration_are_one_node``,
        which fails if the two ever stop agreeing.
        """
        if isinstance(value, NestedRef):
            if value.target_id is not None and value.target_id in self.by_id:
                return self.by_id[value.target_id]
            return self.by_path.get(value.target_path)
        if isinstance(value, str):
            return self.by_id.get(value)
        return None


def _is_reference_only(obj: dict[str, Any]) -> bool:
    return set(obj.keys()) == {"@id"} and isinstance(obj["@id"], str)


def _merged_types(first: tuple[str, ...], second: tuple[str, ...]) -> tuple[str, ...]:
    """Union two declarations' @type tuples, sorted.

    Sorted, where a single declaration's types keep the order the document
    wrote them in, because between two declarations there is no document
    order: which one the walk reached first is a function of ``@graph`` array
    position and JSON key order. Type names reach the reader inside messages
    (``domain_range`` renders ``[{', '.join(types)}]``), so leaving the union
    in encounter order would make the same document produce different bytes
    when its entities were rearranged.
    """
    if not second or set(second) <= set(first):
        return first
    return tuple(sorted(set(first) | set(second)))


class _Builder:
    def __init__(self, schema: SchemaIndex) -> None:
        self.schema = schema
        self.nodes: list[Node] = []
        self.by_id: dict[str, Node] = {}
        self.by_path: dict[str, Node] = {}
        self.declarations: dict[str, list[str]] = {}

    def _node_for(self, path: str, node_id: str | None, types: tuple[str, ...]) -> Node:
        """The node this declaration belongs to: a new one, or one it joins.

        A second node object claiming an identity the document already gave to
        another one is merged into it. JSON-LD reads those as one node, so
        this unions them rather than keeping whichever was walked first and
        dropping the rest, which made a verdict a function of ``@graph`` array
        order (issue #33, ADR-0005).
        """
        if node_id is not None:
            self.declarations.setdefault(node_id, []).append(path)

        existing = self.by_id.get(node_id) if node_id is not None else None
        if existing is not None:
            existing.types = _merged_types(existing.types, types)
            self.by_path[path] = existing
            return existing

        node = Node(path=path, node_id=node_id, types=types, props={})
        self.nodes.append(node)
        if node_id is not None:
            self.by_id[node_id] = node
        self.by_path[path] = node
        return node

    def walk(self, obj: dict[str, Any], path: str) -> Node:
        node_id = obj.get("@id") if isinstance(obj.get("@id"), str) else None
        raw_types = obj.get("@type")
        type_list = raw_types if isinstance(raw_types, list) else [raw_types] if raw_types else []
        types = tuple(self.schema.compact_iri(t) for t in type_list if isinstance(t, str))

        node = self._node_for(path, node_id, types)

        for key, raw in obj.items():
            if key.startswith("@"):
                continue
            prop = self.schema.compact_iri(key)
            prop_def = self.schema.properties.get(prop)
            raw_values = raw if isinstance(raw, list) else [raw]
            values: list[Any] = []
            for index, item in enumerate(raw_values):
                if isinstance(item, dict):
                    if _is_reference_only(item):
                        values.append(item["@id"])
                    elif "@value" in item:
                        values.append(item["@value"])
                    elif prop_def is not None and prop_def.language_map:
                        values.append(item)
                    else:
                        child = self.walk(item, f"{path}.{prop}[{index}]")
                        values.append(NestedRef(target_path=child.path, target_id=child.node_id))
                else:
                    values.append(item)
            if prop in node.props:
                # Only reachable on a merge: a decoded JSON object cannot
                # carry the same key twice. Within one declaration the values
                # are kept exactly as written, repeats included.
                already = node.props[prop]
                node.props[prop] = already + tuple(v for v in values if v not in already)
            else:
                node.props[prop] = tuple(values)
        return node


def parse_document(data: Any, schema: SchemaIndex) -> Graph:
    """Parse a decoded JSON document into a Graph.

    Accepted shapes: an object with ``@graph``, a single entity object, or an
    array of entity objects.
    """
    if isinstance(data, dict) and "@graph" in data:
        top = data["@graph"]
        if not isinstance(top, list):
            raise DocumentError("@graph must be an array of entities")
        entities = top
        prefix = "$.@graph"
    elif isinstance(data, dict):
        entities = [data]
        prefix = "$"
    elif isinstance(data, list):
        entities = data
        prefix = "$"
    else:
        raise DocumentError(
            "expected a JSON-LD object with @graph, a single entity object, or an array of entities"
        )

    builder = _Builder(schema)
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            raise DocumentError(f"entity at index {index} is not a JSON object")
        path = f"{prefix}[{index}]" if (len(entities) > 1 or prefix.endswith("@graph")) else prefix
        builder.walk(entity, path)

    return Graph(
        nodes=builder.nodes,
        by_id=builder.by_id,
        by_path=builder.by_path,
        declarations={k: tuple(v) for k, v in builder.declarations.items()},
    )
