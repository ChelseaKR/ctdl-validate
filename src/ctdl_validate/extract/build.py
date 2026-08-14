"""Turning what a page published into CTDL, and reporting what did not survive.

The rule this module exists to enforce: a foreign term becomes a CTDL term
only where Credential Engine's own schema encoding declares an equivalence for
it, read from the vendored snapshot by :mod:`ctdl_validate.extract.crosswalk`.
Everything else is reported and dropped. In particular:

- A class with no ``owl:equivalentClass`` produces no entity. Emitting its
  properties under a class this tool picked would be an assertion the page
  never made, and the validator downstream would then be checking a claim
  invented here.
- A property with two or more CTDL equivalents is resolved only when exactly
  one of them declares a ``schema:domainIncludes`` the subject's class
  satisfies. Otherwise it is dropped as ambiguous.
- A property whose CTDL definition takes an identifier, given a literal by the
  page, is dropped. Minting an identifier to hold a name is how a credential
  that never existed gets published.
- No ``ceterms:ctid`` is ever generated. An extract is a draft for a human to
  finish, not a Registry payload.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from .. import rules
from ..findings import Severity
from ..schema import CHECKED_PREFIXES, SchemaIndex
from .crosswalk import (
    EQUIVALENT_CLASS,
    EQUIVALENT_PROPERTY,
    SUBCLASS_OF,
    SUBPROPERTY_OF,
    Crosswalk,
)
from .items import RawItem, RawValue, walk_items
from .report import Note
from .terms import is_absolute_iri

#: The context the emitted document declares. Terms are written prefixed, the
#: form the CTDL context and the Registry's own payloads use.
CTDL_CONTEXT = rules.CTDL_CONTEXT_URL


def _is_ctdl(term: str) -> bool:
    return term.startswith(CHECKED_PREFIXES)


class _Builder:
    def __init__(self, source: str, schema: SchemaIndex, crosswalk: Crosswalk) -> None:
        self.source = source
        self.schema = schema
        self.crosswalk = crosswalk
        self.notes: list[Note] = []
        self.labels: dict[str, str] = {}
        self.classes: dict[str, tuple[str, ...]] = {}
        self.nodes: dict[str, dict[str, Any]] = {}

    # -- identifiers ------------------------------------------------------

    def _label(self, item: RawItem, index: int) -> str:
        """The entity's identifier: the one the page published, or a blank node.

        A blank node is the honest fallback. Its scope is the payload that
        declares it, which is exactly what an extract is: a set of assertions
        about entities the page did not give Registry identifiers to.
        """
        published = item.item_id
        if published is None:
            return f"_:n{index}"
        if published.startswith("_:"):
            return published
        resolved = published if is_absolute_iri(published) else urljoin(self.source, published)
        return resolved if is_absolute_iri(resolved) else f"_:n{index}"

    # -- classes ----------------------------------------------------------

    def _class_for(self, term: str, item: RawItem) -> str | None:
        if _is_ctdl(term) and term in self.schema.classes:
            return term
        candidates = self.crosswalk.equivalents(term, is_class=True)
        if len(candidates) == 1:
            return candidates[0]
        if not candidates and term in self.schema.classes:
            # A term from another vocabulary that CTDL's own encoding declares
            # and uses (skos:Concept, asn:ProgressionModel). Kept as published.
            return term
        if len(candidates) > 1:
            self.notes.append(
                Note(
                    code="CLASS_AMBIGUOUS",
                    severity=Severity.WARNING,
                    subject=item.path,
                    term=term,
                    detail=(
                        "More than one CTDL class declares an equivalence to this "
                        "type, so no single class follows from the markup and the "
                        "item was dropped."
                    ),
                    rule=rules.ambiguous_equivalence_rule(term, candidates),
                )
            )
            return None
        self._report_unmapped_class(term, item)
        return None

    def _report_unmapped_class(self, term: str, item: RawItem) -> None:
        self.notes.append(
            Note(
                code="CLASS_NOT_MAPPED",
                severity=Severity.WARNING,
                subject=item.path,
                term=term,
                detail=(
                    f"No CTDL class is declared equivalent to this type, so the item "
                    f"and its {len(item.props)} property value(s) were dropped rather "
                    "than filed under a class this tool chose for it."
                ),
                rule=rules.no_equivalence_rule(term, EQUIVALENT_CLASS),
            )
        )
        for related in self.crosswalk.specializations(term, is_class=True):
            self.notes.append(
                Note(
                    code="CLASS_RELATED_NOT_EQUIVALENT",
                    severity=Severity.INFO,
                    subject=item.path,
                    term=term,
                    detail=(
                        f"{related} is declared a subclass of this type. That relation "
                        "runs from CTDL outward and does not license reading this type "
                        f"as {related}; a human who knows the resource may decide it is."
                    ),
                    rule=rules.subclass_only_rule(related, term, SUBCLASS_OF),
                )
            )

    # -- properties -------------------------------------------------------

    def _property_for(self, term: str, subject_classes: tuple[str, ...], path: str) -> str | None:
        if _is_ctdl(term) and term in self.schema.properties:
            return term
        candidates = self.crosswalk.equivalents(term, is_class=False)
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            if term in self.schema.properties:
                # Declared in CTDL's own encoding under another vocabulary's
                # namespace (skos:prefLabel, qdata:percentage). Kept as published.
                return term
            self._report_unmapped_property(term, path)
            return None
        narrowed = tuple(
            candidate
            for candidate in candidates
            if self.schema.class_matches(subject_classes, self.schema.properties[candidate].domain)
        )
        if len(narrowed) == 1:
            return narrowed[0]
        self.notes.append(
            Note(
                code="PROPERTY_AMBIGUOUS",
                severity=Severity.WARNING,
                subject=path,
                term=term,
                detail=(
                    "Two or more CTDL properties declare an equivalence to this term "
                    "and the subject's class does not single one out by declared "
                    "domain, so the value was dropped."
                ),
                rule=rules.ambiguous_equivalence_rule(term, candidates),
            )
        )
        return None

    def _report_unmapped_property(self, term: str, path: str) -> None:
        self.notes.append(
            Note(
                code="PROPERTY_NOT_MAPPED",
                severity=Severity.WARNING,
                subject=path,
                term=term,
                detail=(
                    "No CTDL property is declared equivalent to this term, so the "
                    "value was dropped. The page published it; this extract does not "
                    "carry it."
                ),
                rule=rules.no_equivalence_rule(term, EQUIVALENT_PROPERTY),
            )
        )
        for related in self.crosswalk.specializations(term, is_class=False):
            self.notes.append(
                Note(
                    code="PROPERTY_RELATED_NOT_EQUIVALENT",
                    severity=Severity.INFO,
                    subject=path,
                    term=term,
                    detail=(
                        f"{related} is declared a subproperty of this term, which does "
                        "not license reading this term as that one."
                    ),
                    rule=rules.subclass_only_rule(related, term, SUBPROPERTY_OF),
                )
            )

    # -- values -----------------------------------------------------------

    def _reference(self, prop: str, target: RawItem, path: str) -> str | None:
        if target.path not in self.nodes:
            self.notes.append(
                Note(
                    code="NESTED_ITEM_DROPPED",
                    severity=Severity.WARNING,
                    subject=path,
                    term=prop,
                    detail=(
                        "The value is a nested item that produced no CTDL entity, so "
                        "the reference would point at nothing and was dropped with it."
                    ),
                    rule=rules.EXTRACTION_POLICY,
                )
            )
            return None
        return self.labels[target.path]

    def _literal(self, prop: str, value: RawValue, path: str) -> Any | None:
        text = value.text
        definition = self.schema.properties.get(prop)
        if text is None or definition is None:
            return text
        if definition.id_coerced and definition.range_has_entities:
            return self._identifier_from_literal(prop, text, path)
        if definition.language_map and value.language is not None:
            return {value.language: text}
        if definition.language_map:
            self.notes.append(
                Note(
                    code="LANGUAGE_UNDECLARED",
                    severity=Severity.INFO,
                    subject=path,
                    term=prop,
                    detail=(
                        "CTDL declares this property as a language map and the page "
                        "declared no language for the value. The literal is emitted "
                        "untagged for a publisher to complete."
                    ),
                    rule=rules.language_map_rule(prop),
                )
            )
        return text

    def _identifier_from_literal(self, prop: str, text: str, path: str) -> str | None:
        if is_absolute_iri(text):
            return text
        self.notes.append(
            Note(
                code="VALUE_NOT_IDENTIFIER",
                severity=Severity.WARNING,
                subject=path,
                term=prop,
                detail=(
                    "This CTDL property takes an identifier and the page published a "
                    "literal here. Minting an identifier to hold it would invent an "
                    "entity, so the value was dropped."
                ),
                rule=rules.id_coercion_rule(prop),
            )
        )
        return None

    def _value(self, prop: str, value: RawValue, path: str) -> Any | None:
        if value.item is None:
            return value.iri if value.iri is not None else self._literal(prop, value, path)
        definition = self.schema.properties.get(prop)
        if definition is not None and not definition.id_coerced:
            self.notes.append(
                Note(
                    code="VALUE_NOT_LITERAL",
                    severity=Severity.WARNING,
                    subject=path,
                    term=prop,
                    detail=(
                        "The page published a nested item where this CTDL property "
                        "takes a literal, so it was dropped rather than flattened "
                        "into text this tool composed."
                    ),
                    rule=rules.id_coercion_rule(prop),
                )
            )
            return None
        return self._reference(prop, value.item, path)

    # -- assembly ---------------------------------------------------------

    def assign(self, items: list[RawItem]) -> None:
        """First pass: identifiers and classes, so references can resolve later."""
        for index, item in enumerate(items):
            self.labels[item.path] = self._label(item, index)
            if not item.types:
                self._report_untyped(item)
                continue
            classes = tuple(
                dict.fromkeys(
                    term for term in (self._class_for(t, item) for t in item.types) if term
                )
            )
            if not classes:
                continue
            self.classes[item.path] = classes
            self.nodes[item.path] = {
                "@id": self.labels[item.path],
                "@type": list(classes) if len(classes) > 1 else classes[0],
            }

    def _report_untyped(self, item: RawItem) -> None:
        self.notes.append(
            Note(
                code="ITEM_UNTYPED",
                severity=Severity.WARNING,
                subject=item.path,
                term="(no type)",
                detail=(
                    "The markup declares no type for this item, so there is no class "
                    "to map and nothing was emitted for it."
                ),
                rule=rules.EXTRACTION_POLICY,
            )
        )

    def fill(self, items: list[RawItem]) -> None:
        """Second pass: property values, now that every entity has a label."""
        for item in items:
            node = self.nodes.get(item.path)
            if node is None:
                continue
            for term, value in item.props:
                prop = self._property_for(term, self.classes[item.path], item.path)
                if prop is None:
                    continue
                rendered = self._value(prop, value, item.path)
                if rendered is not None:
                    _append(node, prop, rendered)

    def report_ctid(self) -> None:
        if not self.nodes or any("ceterms:ctid" in node for node in self.nodes.values()):
            return
        self.notes.append(
            Note(
                code="CTID_ABSENT",
                severity=Severity.INFO,
                subject="$.@graph",
                term="ceterms:ctid",
                detail=(
                    "No entity in this extract carries a CTID, because the page "
                    "published none. Registry publication needs one per resource; "
                    "this tool will not generate it."
                ),
                rule=rules.CTID_NOT_INVENTED,
            )
        )

    def document(self) -> dict[str, Any]:
        return {"@context": CTDL_CONTEXT, "@graph": list(self.nodes.values())}


def _merge_language_maps(existing: dict[str, Any], addition: dict[str, Any]) -> None:
    for language, text in addition.items():
        if language not in existing:
            existing[language] = text
        elif isinstance(existing[language], list):
            existing[language].append(text)
        else:
            existing[language] = [existing[language], text]


def _append(node: dict[str, Any], prop: str, value: Any) -> None:
    """Add a value, keeping single values scalar and repeats in document order."""
    if prop not in node:
        node[prop] = value
        return
    current = node[prop]
    if isinstance(current, dict) and isinstance(value, dict):
        _merge_language_maps(current, value)
    elif isinstance(current, list):
        current.append(value)
    else:
        node[prop] = [current, value]


def build_document(
    items: list[RawItem], source: str, schema: SchemaIndex, crosswalk: Crosswalk
) -> tuple[dict[str, Any], list[Note]]:
    """Map read items onto CTDL, returning the document and every note raised."""
    builder = _Builder(source, schema, crosswalk)
    ordered = list(walk_items(items))
    builder.assign(ordered)
    builder.fill(ordered)
    builder.report_ctid()
    return builder.document(), builder.notes
