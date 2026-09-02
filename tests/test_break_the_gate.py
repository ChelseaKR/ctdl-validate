"""Break the gate on purpose before trusting it.

Discipline these tests encode: a gate is only trusted after deliberately
corrupting a known-good payload and confirming the gate catches the
corruption. Each test starts from the clean framework fixture (proven clean
first), breaks exactly one thing, and asserts the specific catch.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


@pytest.fixture()
def clean_payload() -> Any:
    payload = load_fixture("clean_framework.json")
    assert validate_document(payload) == [], "gate test requires a proven-clean baseline"
    return copy.deepcopy(payload)


def test_stripping_ce_prefix_from_a_ctid_is_caught(clean_payload: Any) -> None:
    node = clean_payload["@graph"][1]
    node["ceterms:ctid"] = node["ceterms:ctid"].removeprefix("ce-")
    findings = validate_document(clean_payload)
    assert any(f.code == "CTID_BARE_UUID" and f.severity is Severity.ERROR for f in findings)


def test_pointing_ispartof_at_a_wrong_identifier_is_caught(clean_payload: Any) -> None:
    node = clean_payload["@graph"][2]
    node["ceasn:isPartOf"] = (
        "https://credentialengineregistry.org/resources/ce-82566cee-17f3-4a6e-8f59-b45273aac457"
    )
    findings = validate_document(clean_payload)
    assert any(f.code == "ISPARTOF_FRAMEWORK_MISMATCH" for f in findings)


def test_breaking_an_inverse_pair_is_caught(clean_payload: Any) -> None:
    # Competency 2 stops pointing back at its parent; hasChild still points at it.
    node = clean_payload["@graph"][2]
    node["ceasn:isChildOf"] = (
        "https://credentialengineregistry.org/resources/ce-9e492574-07fc-4154-b7f2-898425f4f3a3"
    )
    findings = validate_document(clean_payload)
    assert any(f.code == "INVERSE_MISMATCH" and f.severity is Severity.ERROR for f in findings)


def test_retyping_the_framework_is_caught(clean_payload: Any) -> None:
    # The framework becomes an Organization: isPartOf/isTopChildOf ranges break.
    clean_payload["@graph"][0]["@type"] = "ceterms:Organization"
    findings = validate_document(clean_payload)
    assert any(f.code == "RANGE_VIOLATION" and f.severity is Severity.ERROR for f in findings)


def test_corrupting_a_registry_uri_is_caught(clean_payload: Any) -> None:
    node = clean_payload["@graph"][0]
    node["@id"] = "https://credentialengineregistry.org/resources/not-a-ctid-at-all"
    findings = validate_document(clean_payload)
    assert any(
        f.code == "REGISTRY_URI_MALFORMED" and f.severity is Severity.ERROR for f in findings
    )


def test_giving_two_entities_one_identifier_is_caught(clean_payload: Any) -> None:
    # Competency 2 is re-declared as an embedded stub under competency 1, so
    # one identifier is now claimed by two node objects. The parser reads them
    # as one entity (ADR-0005) and check 6 says so; nothing about the clean
    # payload is otherwise wrong, so this must be the only new finding.
    duplicated = clean_payload["@graph"][2]["@id"]
    clean_payload["@graph"][1]["ceasn:isRelatedTo"] = {
        "@id": duplicated,
        "@type": "ceasn:Competency",
    }
    findings = validate_document(clean_payload)
    merged = [f for f in findings if f.code == "ID_DECLARED_MORE_THAN_ONCE"]
    assert len(merged) == 1
    assert merged[0].entity == duplicated
    assert merged[0].severity is Severity.INFO


# -- three rules that fired against nothing until 2026-08-28 --------------------
#
# CTID_MALFORMED, REF_BARE_CTID and REF_NOT_IRI were emitted by the source,
# named in the README's rule table, and asserted by no test in this suite.
# Each of them could have been deleted without turning a single gate red.
# tests/test_every_rule_fires.py is the structural guard against that
# recurring; these are the corruptions in this file's own idiom.


def test_a_ctid_that_is_not_a_uuid_at_all_is_caught(clean_payload: Any) -> None:
    # Not a bare UUID either: nothing about this value is UUID-shaped, so it
    # takes the malformed branch rather than the missing-prefix one.
    clean_payload["@graph"][1]["ceterms:ctid"] = "ce-not-a-uuid"
    findings = validate_document(clean_payload)
    assert any(f.code == "CTID_MALFORMED" and f.severity is Severity.ERROR for f in findings)


def test_a_non_string_ctid_is_caught(clean_payload: Any) -> None:
    # A JSON number where the published grammar describes a 39-character
    # string. Reported rather than skipped for not being a string.
    clean_payload["@graph"][1]["ceterms:ctid"] = 177
    findings = validate_document(clean_payload)
    assert any(f.code == "CTID_MALFORMED" and f.severity is Severity.ERROR for f in findings)


def test_a_bare_ctid_where_an_iri_belongs_is_caught(clean_payload: Any) -> None:
    # Right identifier kind, wrong form: the competency names its framework by
    # CTID instead of by the CTID-based URI.
    clean_payload["@graph"][2]["ceasn:isPartOf"] = "ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37"
    findings = validate_document(clean_payload)
    assert any(f.code == "REF_BARE_CTID" and f.severity is Severity.WARNING for f in findings)


def test_a_name_where_an_identifier_belongs_is_caught(clean_payload: Any) -> None:
    # The shape an extractor produces when it maps a label to a property that
    # takes an IRI: neither an IRI nor a blank node identifier.
    clean_payload["@graph"][2]["ceasn:isPartOf"] = "Example Widgetry Competency Framework"
    findings = validate_document(clean_payload)
    assert any(f.code == "REF_NOT_IRI" and f.severity is Severity.WARNING for f in findings)


def test_a_concept_from_the_wrong_scheme_is_caught(clean_payload: Any) -> None:
    # The framework gains a cost profile whose directCostType names a real
    # CTDL concept from ceterms:CredentialStatus instead of ceterms:CostType.
    clean_payload["@graph"].append(
        {
            "@id": "_:cost",
            "@type": "ceterms:CostProfile",
            "ceterms:directCostType": {
                "@type": "ceterms:CredentialAlignmentObject",
                "ceterms:targetNode": "credentialStat:Active",
            },
        }
    )
    findings = validate_document(clean_payload)
    assert any(
        f.code == "CONCEPT_OUTSIDE_SCHEME" and f.severity is Severity.WARNING for f in findings
    )
