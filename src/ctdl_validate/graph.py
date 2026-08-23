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

from dataclasses import dataclass
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


class _Builder:
    def __init__(self, schema: SchemaIndex) -> None:
        self.schema = schema
        self.nodes: list[Node] = []
        self.by_id: dict[str, Node] = {}
        self.by_path: dict[str, Node] = {}

    def walk(self, obj: dict[str, Any], path: str) -> Node:
        node_id = obj.get("@id") if isinstance(obj.get("@id"), str) else None
        raw_types = obj.get("@type")
        type_list = raw_types if isinstance(raw_types, list) else [raw_types] if raw_types else []
        types = tuple(self.schema.compact_iri(t) for t in type_list if isinstance(t, str))

        node = Node(path=path, node_id=node_id, types=types, props={})
        self.nodes.append(node)
        self.by_path[path] = node
        if node_id is not None and node_id not in self.by_id:
            self.by_id[node_id] = node

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

    return Graph(nodes=builder.nodes, by_id=builder.by_id, by_path=builder.by_path)
