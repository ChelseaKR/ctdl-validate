"""Reference resolution: in-payload, blank node, and external cases."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


def test_undefined_blank_node_reference_is_an_error() -> None:
    findings = validate_document(load_fixture("unresolved_bnode.json"))
    (finding,) = [f for f in findings if f.code == "REF_UNRESOLVED_BNODE"]
    assert finding.severity is Severity.ERROR
    assert finding.value == "_:org-that-is-never-defined"
    assert "Blank Node Identifier" in finding.rule.citation


def test_defined_blank_node_reference_is_fine() -> None:
    payload = {
        "@graph": [
            {
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-82566cee-17f3-4a6e-8f59-b45273aac457",
                "ceterms:ownedBy": ["_:org1"],
            },
            {
                "@id": "_:org1",
                "@type": "ceterms:Organization",
                "ceterms:name": {"en-US": "Blank Node Organization"},
            },
        ]
    }
    assert validate_document(payload) == []


def test_inline_nested_entity_resolves_by_containment() -> None:
    payload = {
        "@type": "ceterms:Certification",
        "ceterms:ctid": "ce-82566cee-17f3-4a6e-8f59-b45273aac457",
        "ceterms:ownedBy": [
            {
                "@type": "ceterms:Organization",
                "ceterms:name": {"en-US": "Inline Organization"},
            }
        ],
    }
    assert validate_document(payload) == []


def test_literal_valued_id_coerced_properties_are_not_reference_checked() -> None:
    # ceterms:subjectWebpage is {"@type": "@id"} in the context but its range
    # is xsd:anyURI: an ordinary web page, not a graph entity to resolve.
    payload = {
        "@type": "ceterms:Certification",
        "ceterms:subjectWebpage": "https://example.org/some-page",
    }
    assert validate_document(payload) == []
