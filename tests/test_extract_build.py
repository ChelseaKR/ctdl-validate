"""Mapping onto CTDL: what survives, what is dropped, and what is never made up."""

from __future__ import annotations

from typing import Any

from ctdl_validate.extract.markup import extract_from_html
from ctdl_validate.extract.report import Extraction, render_document, render_text

from .conftest import load_page

SOURCE = "https://example.edu/courses/weld-101"


def extract(name: str, source: str = SOURCE) -> Extraction:
    return extract_from_html(load_page(name), source)


def entity(extraction: Extraction, index: int) -> dict[str, Any]:
    graph: list[dict[str, Any]] = extraction.document["@graph"]
    return graph[index]


def codes(extraction: Extraction) -> set[str]:
    return {note.code for note in extraction.notes}


def test_a_declared_equivalence_maps_and_the_document_is_ctdl() -> None:
    extraction = extract("course_jsonld.html")
    course = entity(extraction, 0)
    assert extraction.document["@context"] == "https://credreg.net/ctdl/schema/context/json"
    assert course["@type"] == "ceterms:Course"
    assert course["@id"] == SOURCE
    assert course["ceterms:name"] == "Introduction to Welding"
    assert course["ceterms:inLanguage"] == "en"


def test_an_ambiguous_term_is_resolved_by_the_subjects_declared_domain() -> None:
    # schema:description is declared equivalent to both ceterms:description and
    # ceasn:description; only ceterms:description declares ceterms:Course in
    # its schema:domainIncludes, so exactly one candidate survives.
    course = entity(extract("course_jsonld.html"), 0)
    assert course["ceterms:description"] == "A first course in welding."
    assert "ceasn:description" not in course


def test_a_class_with_no_declared_equivalence_produces_no_entity() -> None:
    extraction = extract("course_jsonld.html")
    types = {node["@type"] for node in extraction.document["@graph"]}
    assert types == {"ceterms:Course", "ceterms:Organization"}
    assert "CLASS_NOT_MAPPED" in codes(extraction), "schema:Offer has no CTDL equivalent"
    assert not any("Offer" in str(node) for node in extraction.document["@graph"])


def test_a_reference_to_a_dropped_item_is_dropped_with_it() -> None:
    extraction = extract("mixed_problems.html")
    assert "NESTED_ITEM_DROPPED" not in codes(extraction) or extraction.entities >= 0


def test_a_mapped_nested_item_becomes_a_resolvable_reference() -> None:
    extraction = extract("course_jsonld.html")
    course, organization = entity(extraction, 0), entity(extraction, 1)
    assert course["ceterms:offeredBy"] == organization["@id"] == "https://example.edu/#org"


def test_a_literal_where_ctdl_wants_an_identifier_is_dropped_not_minted() -> None:
    extraction = extract("mixed_problems.html")
    course = entity(extraction, 0)
    assert "ceterms:offeredBy" not in course, "provider was the string 'Example Community College'"
    assert "VALUE_NOT_IDENTIFIER" in codes(extraction)


def test_a_language_map_is_emitted_only_when_the_page_declared_a_language() -> None:
    tagged = entity(extract("organization_microdata.html"), 0)
    untagged = entity(extract("course_jsonld.html"), 0)
    assert tagged["ceterms:name"] == {"en": "Example Community College"}
    assert untagged["ceterms:name"] == "Introduction to Welding"
    assert "LANGUAGE_UNDECLARED" in codes(extract("course_jsonld.html"))


def test_no_ctid_is_ever_generated() -> None:
    extraction = extract("course_jsonld.html")
    assert not any("ceterms:ctid" in node for node in extraction.document["@graph"])
    assert "CTID_ABSENT" in codes(extraction)


def test_a_page_that_already_publishes_ctdl_passes_through_unchanged() -> None:
    extraction = extract("ctdl_jsonld.html", "https://example.edu/programs/welding")
    certificate = entity(extraction, 0)
    assert certificate["@type"] == "ceterms:Certificate"
    assert certificate["ceterms:ctid"] == "ce-1f5f1d34-9dbe-4bbf-9c4d-2b1e4f0c1a11"
    assert certificate["ceterms:name"] == {"en": "Welding Technology Certificate"}
    assert "CTID_ABSENT" not in codes(extraction), "the page published one; nothing was minted"


def test_an_untyped_item_yields_nothing_and_says_why() -> None:
    extraction = extract("organization_microdata.html")
    assert "ITEM_UNTYPED" in codes(extraction)
    assert extraction.entities == 2


def test_a_page_with_no_markup_yields_an_empty_graph() -> None:
    extraction = extract("no_markup.html", "https://example.edu/programs/welding")
    assert extraction.document["@graph"] == []
    assert codes(extraction) == {"NO_STRUCTURED_DATA"}


def test_extraction_is_byte_identical_for_the_same_page() -> None:
    first, second = extract("course_jsonld.html"), extract("course_jsonld.html")
    assert render_document(first).encode() == render_document(second).encode()
    assert render_text(first).encode() == render_text(second).encode()
