"""Break the extractor on purpose, the way the validator's gate is broken.

The validator's discipline is: corrupt a clean payload and prove the check
catches it. The extractor's equivalent question is the opposite one, because
its failure mode is not missing a defect but inventing a fact. So each test
here takes a page that would tempt a tool into a guess, and proves no guess
was made.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from ctdl_validate.extract.crosswalk import load_crosswalk
from ctdl_validate.extract.markup import extract_from_html
from ctdl_validate.extract.report import Extraction

SOURCE = "https://example.edu/programs/welding"

PAGE = """<!doctype html>
<html lang="en"><body>
<script type="application/ld+json">
{{"@context": "https://schema.org", "@type": "{type_}", "name": "Welding Technology",
  "{property_}": "{value}"}}
</script>
</body></html>
"""


def extract(**parts: str) -> Extraction:
    defaults = {"type_": "Course", "property_": "description", "value": "Six months."}
    return extract_from_html(PAGE.format(**{**defaults, **parts}), SOURCE)


def graph(extraction: Extraction) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = extraction.document["@graph"]
    return nodes


def codes(extraction: Extraction) -> set[str]:
    return {note.code for note in extraction.notes}


def test_the_baseline_page_really_does_extract() -> None:
    # Every test below is only meaningful against a page that otherwise works.
    assert graph(extract())[0]["@type"] == "ceterms:Course"


def test_a_type_with_no_declared_equivalence_is_never_given_a_ctdl_class() -> None:
    # schema:EducationalOccupationalProgram is the type a credential provider
    # is most likely to publish, and CTDL declares only a subclass relation
    # pointing the other way. Guessing ceterms:LearningProgram here would be
    # the whole bug class this tool exists to prevent.
    extraction = extract(type_="EducationalOccupationalProgram")
    assert graph(extraction) == []
    assert {"CLASS_NOT_MAPPED", "CLASS_RELATED_NOT_EQUIVALENT"} <= codes(extraction)


def test_a_property_with_no_declared_equivalence_is_never_renamed_into_ctdl() -> None:
    extraction = extract(property_="courseCode", value="WELD-101")
    assert "WELD-101" not in str(graph(extraction))
    assert "PROPERTY_NOT_MAPPED" in codes(extraction)


def test_an_identifier_is_never_minted_to_hold_a_name() -> None:
    extraction = extract(property_="provider", value="Example Community College")
    assert "ceterms:offeredBy" not in graph(extraction)[0]
    assert "VALUE_NOT_IDENTIFIER" in codes(extraction)


def test_a_language_tag_is_never_inferred_from_the_text() -> None:
    extraction = extract(value="Seis meses.")
    assert graph(extraction)[0]["ceterms:description"] == "Seis meses."
    assert "LANGUAGE_UNDECLARED" in codes(extraction)


def test_prose_alone_extracts_nothing() -> None:
    page = "<html lang='en'><body><h1>Welding Certificate</h1><p>Six months.</p></body></html>"
    extraction = extract_from_html(page, SOURCE)
    assert graph(extraction) == []
    assert codes(extraction) == {"NO_STRUCTURED_DATA"}


def test_the_source_page_is_never_asserted_as_a_property_of_the_entity() -> None:
    # ceterms:subjectWebpage would be a defensible inference and is still an
    # inference: the page did not say it.
    assert "ceterms:subjectWebpage" not in graph(extract())[0]


def test_removing_an_equivalence_from_the_crosswalk_removes_the_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The crosswalk is the only thing licensing a mapping. Take the licence
    # away and the mapping must disappear, not fall back to a guess.
    crosswalk = load_crosswalk()
    without_course = replace(
        crosswalk,
        equivalent_class={
            term: candidates
            for term, candidates in crosswalk.equivalent_class.items()
            if term != "schema:Course"
        },
    )
    monkeypatch.setattr("ctdl_validate.extract.markup.load_crosswalk", lambda: without_course)
    extraction = extract()
    assert graph(extraction) == []
    assert "CLASS_NOT_MAPPED" in codes(extraction)
