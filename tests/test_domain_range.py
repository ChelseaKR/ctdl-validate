"""Domain/range checks from the schema's own declarations."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


def test_property_on_class_outside_declared_domain_is_an_error() -> None:
    findings = validate_document(load_fixture("domain_violation.json"))
    (finding,) = [f for f in findings if f.code == "DOMAIN_VIOLATION"]
    assert finding.severity is Severity.ERROR
    assert finding.prop == "ceterms:isPartOf"
    assert "domainIncludes" in finding.rule.citation
    assert finding.rule.url == "https://credreg.net/ctdl/schema/encoding/json"


def test_reference_to_wrong_class_is_a_range_error_with_declaration_cited() -> None:
    findings = validate_document(load_fixture("bug_class_252_wrong_framework_identifier.json"))
    (finding,) = [f for f in findings if f.code == "RANGE_VIOLATION"]
    assert "rangeIncludes" in finding.rule.citation
    assert "ceasn:CompetencyFramework" in finding.rule.citation
    assert finding.rule.url == "https://credreg.net/ctdlasn/schema/encoding/json"


def test_subclasses_satisfy_domain_and_range() -> None:
    # ceterms:ownedBy range includes ceterms:Organization;
    # ceterms:CredentialOrganization is its subclass and must satisfy it.
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:ownedBy": [
                    "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826"
                ],
            },
            {
                "@id": "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826",
                "@type": "ceterms:CredentialOrganization",
                "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
                "ceterms:name": {"en-US": "A Credential Organization"},
            },
        ]
    }
    assert validate_document(payload) == []


def test_unknown_ctdl_property_is_a_warning_not_an_error() -> None:
    payload = {
        "@type": "ceterms:Certification",
        "ceterms:notARealProperty": "x",
    }
    findings = validate_document(payload)
    (finding,) = findings
    assert finding.code == "UNKNOWN_PROPERTY"
    assert finding.severity is Severity.WARNING
    assert "snapshot" in finding.rule.citation


def test_unknown_ctdl_class_is_a_warning_not_an_error() -> None:
    payload = {"@type": "ceterms:NotARealClass"}
    findings = validate_document(payload)
    (finding,) = findings
    assert finding.code == "UNKNOWN_CLASS"
    assert finding.severity is Severity.WARNING


def test_foreign_namespace_terms_are_not_judged() -> None:
    payload = {
        "@type": "ceterms:Certification",
        "schema:thisIsNotOurs": "x",
        "dct:alsoNotOurs": "y",
    }
    assert validate_document(payload) == []


def test_ischildof_pointing_at_framework_is_info_due_to_documented_conflict() -> None:
    # The CTDL-ASN schema does not include CompetencyFramework in
    # ceasn:isChildOf's range, but Credential Engine's own handbook examples
    # and the isPartOf usage note use exactly that pattern for top-level
    # competencies. Conflicting sources: INFO, not ERROR.
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
                "@type": "ceasn:CompetencyFramework",
                "ceterms:ctid": "ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
                "ceasn:name": {"en-US": "Framework"},
            },
            {
                "@id": "https://credentialengineregistry.org/resources/ce-5e3de882-3b49-421b-b623-695c63587f4f",
                "@type": "ceasn:Competency",
                "ceterms:ctid": "ce-5e3de882-3b49-421b-b623-695c63587f4f",
                "ceasn:competencyText": {"en-US": "Top-level competency"},
                "ceasn:isPartOf": "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
                "ceasn:isChildOf": "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
            },
        ]
    }
    findings = validate_document(payload)
    conflict = [f for f in findings if f.code == "RANGE_DOCS_CONFLICT"]
    assert len(conflict) == 1
    assert conflict[0].severity is Severity.INFO
    assert not [f for f in findings if f.severity is Severity.ERROR]
