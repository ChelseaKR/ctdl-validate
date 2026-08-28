"""Check 7: a value on a scheme-bound property, against the scheme named for it.

The two halves of this check are both in the vendored snapshot: 48 properties
declare ``meta:targetScheme``, and 456 concepts declare ``skos:inScheme``.
Nothing here needs a network call, and nothing is written down by hand -- the
tests read the same index the check does, so refreshing the snapshot refreshes
them.

Every payload is synthetic.
"""

from __future__ import annotations

from typing import Any

import pytest

from ctdl_validate import Severity, validate_document
from ctdl_validate.schema import load_schema

ORG = "https://credentialengineregistry.org/resources/ce-11111111-1111-4111-8111-111111111111"


def _cost_profile(direct_cost_type: Any) -> dict[str, Any]:
    """An entity carrying ceterms:directCostType, which draws on CostType."""
    return {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:CostProfile",
                "ceterms:directCostType": direct_cost_type,
            }
        ]
    }


def _alignment(target_node: str) -> dict[str, Any]:
    return {
        "@type": "ceterms:CredentialAlignmentObject",
        "ceterms:targetNode": target_node,
    }


def _codes(payload: dict[str, Any]) -> list[str]:
    return [f.code for f in validate_document(payload)]


def test_the_snapshot_supplies_both_halves_of_the_check() -> None:
    """Read from the index, not written down, so a re-vendoring updates it."""
    schema = load_schema()
    bound = [p for p in schema.properties.values() if p.target_scheme]
    assert len(bound) == 48
    assert len(schema.concepts) == 456
    assert len(schema.schemes) == 36
    assert schema.concepts["costType:Tuition"] == frozenset({"ceterms:CostType"})
    assert schema.properties["ceterms:directCostType"].target_scheme == frozenset(
        {"ceterms:CostType"}
    )


def test_a_concept_from_the_named_scheme_is_clean() -> None:
    assert "CONCEPT_OUTSIDE_SCHEME" not in _codes(_cost_profile(_alignment("costType:Tuition")))


def test_a_concept_from_another_scheme_is_reported() -> None:
    """credentialStat:Active is a real CTDL concept, in the wrong scheme here."""
    payload = _cost_profile(_alignment("credentialStat:Active"))
    findings = [f for f in validate_document(payload) if f.code == "CONCEPT_OUTSIDE_SCHEME"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert "ceterms:CredentialStatus" in findings[0].message
    assert "ceterms:CostType" in findings[0].message


def test_the_term_may_be_written_directly_rather_than_wrapped() -> None:
    payload = _cost_profile("credentialStat:Active")
    assert "CONCEPT_OUTSIDE_SCHEME" in _codes(payload)


def test_a_term_the_snapshot_does_not_declare_is_unverifiable_not_wrong() -> None:
    payload = _cost_profile(_alignment("costType:NoSuchConceptAnywhere"))
    findings = [f for f in validate_document(payload) if f.code == "CONCEPT_OUTSIDE_SNAPSHOT"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.UNVERIFIABLE


def test_an_external_framework_uri_is_unverifiable() -> None:
    """The common case in published documents. It must never be an error."""
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Occupation",
                "ceterms:occupationType": _alignment(
                    "https://www.onetonline.org/link/summary/15-1244.00"
                ),
            }
        ]
    }
    findings = [f for f in validate_document(payload) if f.code.startswith("CONCEPT_")]
    assert [f.severity for f in findings] == [Severity.UNVERIFIABLE]
    assert "O*NET" in findings[0].message


def test_an_alignment_object_naming_its_term_in_words_is_unverifiable() -> None:
    payload = _cost_profile(
        {
            "@type": "ceterms:CredentialAlignmentObject",
            "ceterms:targetNodeName": {"en-US": "Tuition"},
        }
    )
    findings = [f for f in validate_document(payload) if f.code == "CONCEPT_NOT_IDENTIFIED"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.UNVERIFIABLE


def test_a_property_with_no_target_scheme_is_not_this_checks_business() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Organization",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:keyword": {"en-US": "nursing"},
            }
        ]
    }
    assert not [c for c in _codes(payload) if c.startswith("CONCEPT_")]


def test_no_finding_from_this_check_can_gate_an_exit_code() -> None:
    """ERROR is the only severity that gates. This check must never emit one."""
    payloads = [
        _cost_profile(_alignment("credentialStat:Active")),
        _cost_profile(_alignment("costType:NoSuchConceptAnywhere")),
        _cost_profile({"@type": "ceterms:CredentialAlignmentObject"}),
    ]
    for payload in payloads:
        concept = [f for f in validate_document(payload) if f.code.startswith("CONCEPT_")]
        assert concept, "each payload is meant to exercise the check"
        assert all(f.severity is not Severity.ERROR for f in concept)


@pytest.mark.parametrize(
    "term",
    ["costType:Tuition", "costType:AggregateCost"],
)
def test_every_concept_of_the_named_scheme_passes(term: str) -> None:
    assert "CONCEPT_OUTSIDE_SCHEME" not in _codes(_cost_profile(_alignment(term)))


def test_the_check_covers_every_scheme_bound_property_not_a_written_list() -> None:
    """Derived from the snapshot: each bound property reports a wrong term.

    Written as a sweep rather than a sample so that a property gaining a
    meta:targetScheme in a future snapshot is covered without an edit here.
    """
    schema = load_schema()
    bound = sorted(p.term for p in schema.properties.values() if p.target_scheme)
    unchecked = []
    for prop in bound:
        payload = {"@graph": [{"@id": ORG, prop: _alignment("costType:NoSuchConceptAnywhere")}]}
        if "CONCEPT_OUTSIDE_SNAPSHOT" not in _codes(payload):
            unchecked.append(prop)
    assert not unchecked, f"scheme-bound properties the check never looked at: {unchecked}"
