"""The mapping paths where a tool is most tempted to improvise.

Each case here is a shape a real provider page can publish, and each has one
correct answer: report it and drop it. The synthetic-crosswalk case at the end
covers a shape the current vendored snapshot does not contain, so that the
behavior is pinned before a future snapshot introduces it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from ctdl_validate.extract.crosswalk import load_crosswalk
from ctdl_validate.extract.markup import extract_from_html
from ctdl_validate.extract.report import Extraction

SOURCE = "https://example.edu/p"


def extract(body: str) -> Extraction:
    return extract_from_html(f"<!doctype html><html lang='en'><body>{body}</body></html>", SOURCE)


def block(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


def graph(extraction: Extraction) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = extraction.document["@graph"]
    return nodes


def codes(extraction: Extraction) -> set[str]:
    return {note.code for note in extraction.notes}


def test_two_equivalents_and_no_domain_to_choose_between_them() -> None:
    # schema:startDate is declared equivalent to both ceterms:startDate and
    # ceasn:dateValidFrom, and neither declares ceterms:Course in its domain,
    # so a course's start date has no CTDL home the snapshot can justify.
    extraction = extract(
        block('{"@context":"https://schema.org","@type":"Course","startDate":"2026-09-01"}')
    )
    assert graph(extraction)[0] == {"@id": "_:n0", "@type": "ceterms:Course"}
    assert "PROPERTY_AMBIGUOUS" in codes(extraction)


def test_a_subproperty_relation_is_reported_and_never_used_as_a_mapping() -> None:
    # ceterms:keyword and ceterms:subject are both declared rdfs:subPropertyOf
    # schema:about. Two candidates by specialization is not one by equivalence.
    extraction = extract(
        block('{"@context":"https://schema.org","@type":"Course","about":"welding"}')
    )
    assert graph(extraction)[0] == {"@id": "_:n0", "@type": "ceterms:Course"}
    assert {"PROPERTY_NOT_MAPPED", "PROPERTY_RELATED_NOT_EQUIVALENT"} <= codes(extraction)


def test_a_reference_to_an_unmappable_item_is_dropped_with_the_item() -> None:
    payload = (
        '{"@context":"https://schema.org","@type":"Course",'
        '"hasPart":{"@type":"CourseInstance","name":"Fall term"}}'
    )
    extraction = extract(block(payload))
    assert "ceterms:hasPart" not in graph(extraction)[0]
    assert {"CLASS_NOT_MAPPED", "NESTED_ITEM_DROPPED"} <= codes(extraction)


def test_an_item_where_ctdl_wants_a_literal_is_not_flattened_into_text() -> None:
    payload = (
        '{"@context":"https://schema.org","@type":"Course",'
        '"name":{"@type":"Thing","name":"an object where a name belongs"}}'
    )
    extraction = extract(block(payload))
    assert "ceterms:name" not in graph(extraction)[0]
    assert "VALUE_NOT_LITERAL" in codes(extraction)


def test_a_term_ctdl_declares_under_another_namespace_is_kept_as_published() -> None:
    # CTDL's own encoding declares skos:prefLabel; a page using it is using a
    # term Credential Engine publishes, so it survives unchanged.
    payload = (
        '{"@context":{"skos":"http://www.w3.org/2004/02/skos/core#",'
        '"schema":"https://schema.org/"},"@id":"_:b7","@type":"schema:Course",'
        '"skos:prefLabel":"Welding"}'
    )
    extraction = extract(block(payload))
    assert graph(extraction)[0]["skos:prefLabel"] == "Welding"
    assert graph(extraction)[0]["@id"] == "_:b7", "a published blank node id is kept"


def test_repeated_values_become_a_list_in_document_order() -> None:
    payload = '{"@context":"https://schema.org","@type":"Course","inLanguage":["en","es"]}'
    assert graph(extract(block(payload)))[0]["ceterms:inLanguage"] == ["en", "es"]


def test_repeated_language_tagged_values_merge_into_one_language_map() -> None:
    body = (
        '<div itemscope itemtype="https://schema.org/Organization">'
        '<span itemprop="name">First</span><span itemprop="name">Second</span></div>'
    )
    assert graph(extract(body))[0]["ceterms:name"] == {"en": ["First", "Second"]}


def test_two_ctdl_classes_claiming_one_foreign_type_map_to_neither(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The vendored snapshot has no ambiguous class today. Pin the behavior now,
    # so a future snapshot that introduces one cannot quietly pick a winner.
    crosswalk = load_crosswalk()
    ambiguous = replace(
        crosswalk,
        equivalent_class={
            **crosswalk.equivalent_class,
            "schema:Course": ("ceterms:Course", "ceterms:LearningProgram"),
        },
    )
    monkeypatch.setattr("ctdl_validate.extract.markup.load_crosswalk", lambda: ambiguous)
    extraction = extract(block('{"@context":"https://schema.org","@type":"Course","name":"X"}'))
    assert graph(extraction) == []
    assert "CLASS_AMBIGUOUS" in codes(extraction)
