"""Domain/range checks from the schema's own declarations."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document
from ctdl_validate.rules import concept_range_conflict_rule
from ctdl_validate.schema import ALIGNMENT_RANGE_TERM, CONCEPT_RANGE_TERM, load_schema

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


# -- the concept-range conflict --------------------------------------------
#
# CTDL declares a reference to a term from one of its own concept schemes two
# incompatible ways: across the vendored snapshot 46 properties range on
# ceterms:CredentialAlignmentObject and 45 range on skos:Concept, with nothing
# about the value distinguishing the families. Three concept schemes are named
# by different properties in each family, and a fourth is named by a single
# property declaring both ranges at once. The published Registry corpus encodes
# both families as CredentialAlignmentObject. Erroring on that reports
# Credential Engine's own dominant encoding as a defect, so it is an INFO
# disposition. These tests pin it to exactly the properties the evidence
# covers, in both directions.


def _credit_unit_payload(unit_type: object) -> dict[str, object]:
    """A course whose credit value names a term from the CreditUnit scheme."""
    return {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:creditValue": [
                    {
                        "@type": "ceterms:ValueProfile",
                        "ceterms:creditUnitType": [unit_type],
                        "schema:value": 3.0,
                    }
                ],
            }
        ]
    }


ALIGNMENT_VALUE = {
    "@type": "ceterms:CredentialAlignmentObject",
    "ceterms:framework": "https://credreg.net/ctdl/terms/CreditUnit",
    "ceterms:targetNode": "creditUnit:SemesterHour",
}


def test_alignment_object_on_a_scheme_bound_concept_property_is_info_not_error() -> None:
    findings = validate_document(_credit_unit_payload(ALIGNMENT_VALUE))
    (finding,) = [f for f in findings if f.code == "CONCEPT_RANGE_CONFLICT"]
    assert finding.severity is Severity.INFO
    assert finding.prop == "ceterms:creditUnitType"
    assert not [f for f in findings if f.severity is Severity.ERROR]


def test_the_conflict_message_names_the_property_the_scheme_and_the_declarations() -> None:
    (finding,) = [
        f
        for f in validate_document(_credit_unit_payload(ALIGNMENT_VALUE))
        if f.code == "CONCEPT_RANGE_CONFLICT"
    ]
    assert "ceterms:creditUnitType" in finding.message
    assert "ceterms:CreditUnit" in finding.message  # the meta:targetScheme
    assert "ceterms:CredentialAlignmentObject" in finding.message
    assert "skos:Concept" in finding.rule.citation
    assert "meta:targetScheme" in finding.rule.citation
    assert finding.rule.url == "https://credreg.net/ctdl/schema/encoding/json"


def test_a_sibling_property_over_the_same_scheme_is_cited_where_one_exists() -> None:
    # ceterms:creditLevelType (skos:Concept) and ceterms:audienceLevelType
    # (CredentialAlignmentObject) both declare meta:targetScheme
    # ceterms:AudienceLevel. That pair is the sharpest evidence in the
    # snapshot, so the citation names it rather than arguing in the abstract.
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:creditValue": [
                    {
                        "@type": "ceterms:ValueProfile",
                        "ceterms:creditLevelType": [
                            {
                                "@type": "ceterms:CredentialAlignmentObject",
                                "ceterms:framework": "https://credreg.net/ctdl/terms/AudienceLevel",
                                "ceterms:targetNode": "audLevel:BeginnerLevel",
                            }
                        ],
                        "schema:value": 3.0,
                    }
                ],
            }
        ]
    }
    (finding,) = [f for f in validate_document(payload) if f.code == "CONCEPT_RANGE_CONFLICT"]
    assert "ceterms:audienceLevelType" in finding.rule.citation


def test_an_actual_skos_concept_satisfies_the_declared_range_with_no_finding() -> None:
    payload = _credit_unit_payload(
        "https://credentialengineregistry.org/resources/ce-1f0b7ff2-9e4c-4a19-9d02-6c1b0b3f3a11"
    )
    payload["@graph"].append(  # type: ignore[attr-defined]
        {
            "@id": "https://credentialengineregistry.org/resources/ce-1f0b7ff2-9e4c-4a19-9d02-6c1b0b3f3a11",
            "@type": "skos:Concept",
            "ceterms:ctid": "ce-1f0b7ff2-9e4c-4a19-9d02-6c1b0b3f3a11",
        }
    )
    findings = validate_document(payload)
    assert not [f for f in findings if f.code in {"CONCEPT_RANGE_CONFLICT", "RANGE_VIOLATION"}]


def test_a_wrong_class_on_a_scheme_bound_property_is_still_an_error() -> None:
    # The disposition covers CredentialAlignmentObject and nothing else. An
    # Organization standing where a concept belongs is still a range error.
    payload = _credit_unit_payload(
        "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826"
    )
    payload["@graph"].append(  # type: ignore[attr-defined]
        {
            "@id": "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826",
            "@type": "ceterms:CredentialOrganization",
            "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
        }
    )
    findings = validate_document(payload)
    (finding,) = [f for f in findings if f.code == "RANGE_VIOLATION"]
    assert finding.severity is Severity.ERROR
    assert finding.prop == "ceterms:creditUnitType"
    assert not [f for f in findings if f.code == "CONCEPT_RANGE_CONFLICT"]


def test_a_skos_ranged_property_with_no_target_scheme_is_still_an_error() -> None:
    # ceterms:classification ranges on skos:Concept but declares no
    # meta:targetScheme, so it is not one of the properties the evidence
    # covers and an alignment object there stays an ERROR. This is the guard
    # against the disposition quietly widening to every skos:Concept range.
    payload = {
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:classification": [ALIGNMENT_VALUE],
            }
        ]
    }
    findings = validate_document(payload)
    (finding,) = [f for f in findings if f.code == "RANGE_VIOLATION"]
    assert finding.severity is Severity.ERROR
    assert finding.prop == "ceterms:classification"


def test_the_conflict_the_disposition_rests_on_is_still_in_the_snapshot() -> None:
    """If Credential Engine fixes the encoding, this test says so.

    The INFO disposition above is only defensible while CTDL really does
    declare one kind of value two incompatible ways. Refreshing the vendored
    snapshot could settle that, at which point a `CONCEPT_RANGE_CONFLICT` would
    be hiding a real error and this disposition should be removed rather than
    left running on a premise that has expired.
    """
    schema = load_schema()
    skos_only: dict[str, set[str]] = {}
    alignment_only: dict[str, set[str]] = {}
    both_at_once: dict[str, set[str]] = {}
    for prop in schema.properties.values():
        ranges_concept = CONCEPT_RANGE_TERM in prop.range
        ranges_alignment = ALIGNMENT_RANGE_TERM in prop.range
        for scheme in prop.target_scheme:
            if ranges_concept and ranges_alignment:
                both_at_once.setdefault(scheme, set()).add(prop.term)
            elif ranges_concept:
                skos_only.setdefault(scheme, set()).add(prop.term)
            elif ranges_alignment:
                alignment_only.setdefault(scheme, set()).add(prop.term)

    # Evidence 1: schemes where two *different* properties disagree on range.
    contested = sorted(set(skos_only) & set(alignment_only))
    assert contested == [
        "ceterms:AudienceLevel",
        "ceterms:CostType",
        "ceterms:ScheduleFrequency",
    ], "the two concept ranges no longer disagree: revisit CONCEPT_RANGE_CONFLICT"
    assert skos_only["ceterms:AudienceLevel"] == {
        "ceasn:educationLevelType",
        "ceterms:creditLevelType",
    }
    assert alignment_only["ceterms:AudienceLevel"] == {"ceterms:audienceLevelType"}

    # Evidence 2: CTDL declares one property both ways at once, which is the
    # encoding itself saying the two ranges describe one kind of value.
    assert both_at_once == {
        "ceterms:InstructionalProgramClassification": {"ceterms:instructionalProgramType"}
    }

    # And the disposition stays narrow: it reaches scheme-bound properties only.
    covered = schema.scheme_bound_concept_properties()
    assert len(covered) == 20
    assert "ceterms:creditUnitType" in covered
    assert "ceterms:classification" not in covered  # no meta:targetScheme
    assert "skos:broader" not in covered


def test_the_sibling_citation_truncates_and_says_how_many_it_left_out() -> None:
    # No property in the current snapshot has more than two siblings, so the
    # truncation is exercised directly rather than left as an untested branch
    # waiting on a schema release to reach it.
    rule = concept_range_conflict_rule(
        "ceterms:creditUnitType",
        frozenset({"ceterms:CreditUnit"}),
        ("ceterms:a", "ceterms:b", "ceterms:c", "ceterms:d"),
    )
    assert "ceterms:a, ceterms:b, ceterms:c, ... (4 properties total)" in rule.citation
    assert "ceterms:d" not in rule.citation


def test_siblings_of_a_property_with_no_target_scheme_is_empty() -> None:
    schema = load_schema()
    assert schema.alignment_ranged_siblings("ceterms:classification") == ()
    assert schema.alignment_ranged_siblings("ceterms:notARealProperty") == ()
    assert schema.alignment_ranged_siblings("ceterms:creditLevelType") == (
        "ceterms:audienceLevelType",
    )


# -- a range of rdfs:Resource constrains nothing --------------------------------

COLLECTION_IRI = (
    "https://credentialengineregistry.org/resources/ce-1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
)
MEMBER_IRI = (
    "https://credentialengineregistry.org/resources/ce-2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
)


def _collection_with_member() -> dict[str, object]:
    return {
        "@graph": [
            {
                "@id": COLLECTION_IRI,
                "@type": "ceterms:Collection",
                "ceterms:ctid": "ce-1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
                "ceterms:hasMember": [MEMBER_IRI],
            },
            {
                "@id": MEMBER_IRI,
                "@type": "ceterms:License",
                "ceterms:ctid": "ce-2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
            },
        ]
    }


def test_a_range_of_rdfs_resource_admits_every_entity() -> None:
    """The 2026-08-21 survey raised 47 range errors on one Collection over this."""
    findings = validate_document(_collection_with_member())
    assert [f for f in findings if f.code == "RANGE_VIOLATION"] == []
    # Kept exhaustive rather than loosened. ceterms:Collection and
    # ceterms:hasMember are both declared vs:unstable in the published
    # encoding, so check 9 discloses them; nothing else fires on this payload.
    assert {(f.code, f.value) for f in findings} == {
        ("TERM_UNSTABLE", "ceterms:Collection"),
        ("TERM_UNSTABLE", "ceterms:hasMember"),
    }


def test_the_universal_range_the_fix_rests_on_is_still_in_the_snapshot() -> None:
    """If CTDL ever ranges hasMember on something real, judge it again.

    The fix is not "hasMember is exempt"; it is that a range naming only
    rdfs:Resource excludes nothing, so matching against it would reject every
    entity rather than accept every entity. Both halves are asserted here.
    """
    schema = load_schema()
    assert schema.properties["ceterms:hasMember"].range == frozenset({"rdfs:Resource"})
    assert schema.properties["ceterms:hasMember"].range_is_universal
    assert "rdfs:Resource" not in schema.classes
    assert not [c for c in schema.classes if "rdfs:Resource" in schema.ancestors_of(c)]


# -- a version property whose range drops a class its own domain admits ---------

TVP_IRI = "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344"
OLDER_TVP_IRI = (
    "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826"
)


def _versioned_transfer_value_profile(target_type: str) -> dict[str, object]:
    return {
        "@graph": [
            {
                "@id": TVP_IRI,
                "@type": "ceterms:TransferValueProfile",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:previousVersion": [OLDER_TVP_IRI],
            },
            {
                "@id": OLDER_TVP_IRI,
                "@type": target_type,
                "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
            },
        ]
    }


def test_versioning_a_class_the_range_drops_is_info_not_an_error() -> None:
    """61 of the survey's 267 errors were this, against 32 published documents."""
    findings = validate_document(_versioned_transfer_value_profile("ceterms:TransferValueProfile"))
    (finding,) = findings
    assert finding.code == "VERSION_RANGE_CONFLICT"
    assert finding.severity is Severity.INFO
    assert finding.prop == "ceterms:previousVersion"


def test_the_version_conflict_message_names_the_class_and_both_declarations() -> None:
    findings = validate_document(_versioned_transfer_value_profile("ceterms:TransferValueProfile"))
    (finding,) = findings
    assert "ceterms:TransferValueProfile" in finding.message
    assert "domain" in finding.rule.citation and "range" in finding.rule.citation
    assert "schema:domainIncludes" in finding.rule.citation
    assert "schema:rangeIncludes" in finding.rule.citation
    assert finding.rule.url == "https://credreg.net/ctdl/schema/encoding/json"


def test_a_version_link_to_a_different_class_is_still_an_error() -> None:
    """The disposition is about versioning a thing with a thing of its own kind."""
    findings = validate_document(
        _versioned_transfer_value_profile("ceterms:CredentialOrganization")
    )
    (finding,) = [f for f in findings if f.code == "RANGE_VIOLATION"]
    assert finding.severity is Severity.ERROR


def test_the_version_asymmetry_the_disposition_rests_on_is_still_in_the_snapshot() -> None:
    """If CTDL ever ranges these three on what it already domains them on, judge again."""
    schema = load_schema()
    dropped = None
    for prop in ("ceterms:latestVersion", "ceterms:nextVersion", "ceterms:previousVersion"):
        declared = schema.properties[prop]
        assert declared.range < declared.domain, prop
        assert "ceterms:TransferValueProfile" in schema.domain_only_classes(prop), prop
        if dropped is None:
            dropped = schema.domain_only_classes(prop)
        assert schema.domain_only_classes(prop) == dropped, prop
