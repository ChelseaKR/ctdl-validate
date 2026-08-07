"""Inverse consistency for pairs the schema declares with owl:inverseOf."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


def test_disagreeing_inverse_pair_is_an_error() -> None:
    findings = validate_document(load_fixture("inverse_mismatch.json"))
    mismatches = [f for f in findings if f.code == "INVERSE_MISMATCH"]
    assert len(mismatches) == 1
    assert mismatches[0].severity is Severity.ERROR
    assert mismatches[0].prop == "ceterms:hasPart"
    assert "owl:inverseOf" in mismatches[0].rule.citation


def test_single_direction_is_info_not_error() -> None:
    findings = validate_document(load_fixture("inverse_mismatch.json"))
    infos = [f for f in findings if f.code == "INVERSE_ONE_DIRECTION"]
    assert infos, "Course B asserts isPartOf Course C; C does not assert hasPart"
    assert all(f.severity is Severity.INFO for f in infos)
    assert all("not an error" in f.message for f in infos)


def test_agreeing_inverse_pair_produces_no_findings() -> None:
    assert validate_document(load_fixture("clean_framework.json")) == []


def test_undeclared_pairs_are_not_invented() -> None:
    # ceasn:hasTopChild and ceasn:isTopChildOf read like a pair but the schema
    # declares no owl:inverseOf between them, so one-directional use must not
    # produce INFO findings. The tool checks only declared inverses.
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
                "@type": "ceasn:CompetencyFramework",
                "ceterms:ctid": "ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
                "ceasn:hasTopChild": [
                    "https://credentialengineregistry.org/resources/ce-5e3de882-3b49-421b-b623-695c63587f4f"
                ],
            },
            {
                "@id": "https://credentialengineregistry.org/resources/ce-5e3de882-3b49-421b-b623-695c63587f4f",
                "@type": "ceasn:Competency",
                "ceterms:ctid": "ce-5e3de882-3b49-421b-b623-695c63587f4f",
                "ceasn:isPartOf": "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
            },
        ]
    }
    assert validate_document(payload) == []
