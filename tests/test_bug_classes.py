"""The two motivating bug classes, reproduced generically.

These fixtures are original test data (UUIDs generated for this repo); they
copy nothing from any upstream repository or issue tracker. Each test name
states the bug class it encodes.
"""

from __future__ import annotations

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


def _codes(findings: list) -> set[str]:  # type: ignore[type-arg]
    return {f.code for f in findings}


class TestBugClass250BareUuidWhereCtidBelongs:
    """Bug class: an extract writes a generated UUID where a CTID belongs
    (the ce- prefix and CTID semantics are lost)."""

    def test_bare_uuid_in_ctid_property_is_caught(self) -> None:
        findings = validate_document(load_fixture("bug_class_250_bare_uuid_for_ctid.json"))
        bare = [f for f in findings if f.code == "CTID_BARE_UUID"]
        assert len(bare) == 1
        assert bare[0].severity is Severity.ERROR
        assert "ce-" in bare[0].message
        assert bare[0].rule.url == "https://credreg.net/ctdl/ctid"

    def test_registry_uri_with_bare_uuid_tail_is_caught(self) -> None:
        findings = validate_document(load_fixture("bug_class_250_bare_uuid_for_ctid.json"))
        uri = [f for f in findings if f.code == "REGISTRY_URI_MALFORMED"]
        assert len(uri) == 1
        assert uri[0].severity is Severity.ERROR
        assert uri[0].prop == "@id"

    def test_bare_uuid_as_reference_value_is_caught(self) -> None:
        payload = {
            "@type": "ceterms:Certification",
            "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
            "ceterms:ownedBy": ["b55f88e3-dfd4-430b-ab47-3e5f9986e1e4"],
        }
        findings = validate_document(payload)
        assert "REF_BARE_UUID" in _codes(findings)
        (finding,) = [f for f in findings if f.code == "REF_BARE_UUID"]
        assert finding.severity is Severity.ERROR


class TestBugClass252IsPartOfCarriesWrongFrameworkIdentifier:
    """Bug class: a competency extract's isPartOf carries an identifier that
    is not the framework's."""

    def test_ispartof_identifier_matching_no_framework_in_payload_is_caught(self) -> None:
        findings = validate_document(
            load_fixture("bug_class_252_wrong_framework_identifier.json")
        )
        mismatches = [f for f in findings if f.code == "ISPARTOF_FRAMEWORK_MISMATCH"]
        assert len(mismatches) == 1
        assert mismatches[0].severity is Severity.WARNING
        assert mismatches[0].entity.endswith("ce-9e492574-07fc-4154-b7f2-898425f4f3a3")
        # The unresolved identifier itself is UNVERIFIABLE, never a pass or fail.
        assert "REF_OUTSIDE_PAYLOAD" in _codes(findings)

    def test_ispartof_resolving_to_a_non_framework_is_caught_as_range_violation(self) -> None:
        findings = validate_document(
            load_fixture("bug_class_252_wrong_framework_identifier.json")
        )
        violations = [f for f in findings if f.code == "RANGE_VIOLATION"]
        assert len(violations) == 1
        assert violations[0].severity is Severity.ERROR
        assert violations[0].prop == "ceasn:isPartOf"
        assert violations[0].entity.endswith("ce-b4da9602-bb7a-4ddc-9426-f119482e32a9")
        assert "rangeIncludes" in violations[0].rule.citation

    def test_correct_member_competency_is_not_flagged(self) -> None:
        findings = validate_document(
            load_fixture("bug_class_252_wrong_framework_identifier.json")
        )
        good_entity = "https://credentialengineregistry.org/resources/ce-5e3de882-3b49-421b-b623-695c63587f4f"
        assert not [f for f in findings if f.entity == good_entity]
