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


def test_inverse_written_as_a_nested_object_still_counts_as_pointing_back() -> None:
    # Course A ceterms:hasPart Course B, written as a plain IRI. Course B
    # ceterms:isPartOf Course A, but written as a full nested object (@id plus
    # other properties) rather than a bare {"@id": ...} reference -- a
    # publisher embedding the entity it points at instead of just citing it,
    # which is still the same document asserting both directions and
    # agreeing. This must not be reported as a mismatch (the nested value
    # never equals the plain node_id string it names) or reduced to "one
    # direction alone" (Course A's own hasPart, declared at the top level,
    # must still be visible from the embedded copy's identity).
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:name": {"en-US": "Course A"},
                "ceterms:hasPart": [
                    "https://credentialengineregistry.org/resources/ce-d9a8ddae-ea6e-4f69-9c36-3f51a3104a0e"
                ],
            },
            {
                "@id": "https://credentialengineregistry.org/resources/ce-d9a8ddae-ea6e-4f69-9c36-3f51a3104a0e",
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-d9a8ddae-ea6e-4f69-9c36-3f51a3104a0e",
                "ceterms:name": {"en-US": "Course B"},
                "ceterms:isPartOf": {
                    "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                    "@type": "ceterms:Course",
                    "ceterms:name": {"en-US": "Course A (embedded copy)"},
                },
            },
        ]
    }
    # Asserted against the inverse codes this test was written for, not against
    # every finding. Course A is declared twice -- once at the top level and
    # once as the embedded copy -- which check 6 (ID_DECLARED_MORE_THAN_ONCE,
    # added later, in #37) correctly discloses as a merge. That disclosure is
    # the point of ADR-0005 and must not be suppressed to keep this assertion
    # convenient; what this test is about is that neither inverse code fires.
    findings = validate_document(payload)
    assert [f for f in findings if f.code.startswith("INVERSE_")] == []
