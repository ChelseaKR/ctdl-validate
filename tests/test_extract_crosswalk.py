"""The crosswalk is Credential Engine's, read out of the vendored snapshot.

These tests exist to prove there is no hand-written mapping table hiding in
this repository: every assertion below is checked against the vendored schema
encodings themselves, so a refreshed snapshot changes the tests' inputs and
their expectations together.
"""

from __future__ import annotations

from typing import Any

from ctdl_validate.extract.crosswalk import (
    EQUIVALENT_CLASS,
    EQUIVALENT_PROPERTY,
    load_crosswalk,
)
from ctdl_validate.schema import CHECKED_PREFIXES, vendor_graph

ENCODINGS = ("ctdl/schema.json", "ctdlasn/schema.json")


def _declared(key: str, entry_type: str) -> set[tuple[str, str]]:
    """(CTDL term, foreign term) pairs the vendored encodings declare for a key.

    Filtered to the entry type the crosswalk indexes: an equivalence declared
    on a ``skos:ConceptScheme`` (``ceasn:PublicationStatus`` declares one) is
    not a class an entity can be typed with, so extraction has no use for it.
    """
    pairs: set[tuple[str, str]] = set()
    for relpath in ENCODINGS:
        for entry in vendor_graph(relpath):
            term = entry.get("@id")
            if not isinstance(term, str) or not term.startswith(CHECKED_PREFIXES):
                continue
            if entry.get("@type") != entry_type:
                continue
            raw: Any = entry.get(key)
            for foreign in raw if isinstance(raw, list) else [raw]:
                if isinstance(foreign, str) and not foreign.startswith(CHECKED_PREFIXES):
                    pairs.add((term, foreign))
    return pairs


def test_every_equivalence_comes_from_the_snapshot_and_none_is_invented() -> None:
    crosswalk = load_crosswalk()
    for key, entry_type, table in (
        (EQUIVALENT_CLASS, "rdfs:Class", crosswalk.equivalent_class),
        (EQUIVALENT_PROPERTY, "rdf:Property", crosswalk.equivalent_property),
    ):
        in_table = {(ctdl, foreign) for foreign, terms in table.items() for ctdl in terms}
        assert in_table == _declared(key, entry_type), key


def test_the_crosswalk_is_keyed_by_foreign_terms_only() -> None:
    crosswalk = load_crosswalk()
    for table in (crosswalk.equivalent_class, crosswalk.equivalent_property):
        assert not [term for term in table if term.startswith(CHECKED_PREFIXES)]


def test_the_schema_org_classes_credential_engine_declares_equivalent() -> None:
    crosswalk = load_crosswalk()
    schema_org = [term for term in crosswalk.covered_classes if term.startswith("schema:")]
    assert schema_org == [
        "schema:ContactPoint",
        "schema:Course",
        "schema:GeoCoordinates",
        "schema:Organization",
        "schema:Place",
        "schema:PostalAddress",
    ]
    assert crosswalk.equivalents("schema:Course", is_class=True) == ("ceterms:Course",)


def test_a_specialization_is_never_offered_as_an_equivalence() -> None:
    # ceterms:LearningProgram rdfs:subClassOf schema:EducationalOccupationalProgram.
    # The relation exists and points the wrong way for extraction; the two
    # tables must not be confused for one another.
    crosswalk = load_crosswalk()
    program = "schema:EducationalOccupationalProgram"
    assert crosswalk.equivalents(program, is_class=True) == ()
    assert crosswalk.specializations(program, is_class=True) == ("ceterms:LearningProgram",)


def test_ambiguous_terms_keep_every_candidate() -> None:
    crosswalk = load_crosswalk()
    assert crosswalk.equivalents("schema:name", is_class=False) == ("ceasn:name", "ceterms:name")
