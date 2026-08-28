"""Check 9: terms the encoding marks unstable, disclosed and not interpreted.

The declaration is in the vendored files; what it means is not. These tests
hold both halves: that the disclosure happens, and that it does not grow into
a claim the snapshot does not support.

Every payload is synthetic.
"""

from __future__ import annotations

from typing import Any

from ctdl_validate import Severity, validate_document
from ctdl_validate.schema import load_schema

ORG = "https://credentialengineregistry.org/resources/ce-11111111-1111-4111-8111-111111111111"


def _unstable_findings(payload: dict[str, Any]) -> list[Any]:
    return [f for f in validate_document(payload) if f.code == "TERM_UNSTABLE"]


def test_the_status_comes_from_the_snapshot_not_a_written_list() -> None:
    schema = load_schema()
    assert len(schema.unstable) == 478
    assert "ceterms:Collection" in schema.unstable
    assert "ceterms:hasMember" in schema.unstable
    assert "ceterms:ctid" not in schema.unstable
    assert "ceterms:License" not in schema.unstable


def test_an_unstable_class_is_disclosed() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Collection",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    findings = _unstable_findings(payload)
    assert [f.value for f in findings] == ["ceterms:Collection"]
    assert findings[0].severity is Severity.INFO
    assert findings[0].prop == "@type"


def test_an_unstable_property_is_disclosed() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:License",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:lifeCycleStatusType": {
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:targetNode": "lifeCycle:Active",
                },
            }
        ]
    }
    assert "ceterms:lifeCycleStatusType" in [f.value for f in _unstable_findings(payload)]


def test_a_stable_only_payload_is_silent() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:License",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    assert _unstable_findings(payload) == []


def test_the_finding_does_not_say_what_unstable_means() -> None:
    """The declaration is vendored; its meaning is not. Hold the claim size.

    Nothing in the four vendored files defines vs:unstable, so a finding that
    predicted withdrawal, rejection, or a required edit would be asserting
    something no source in this repository says.
    """
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Collection",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    finding = _unstable_findings(payload)[0]
    text = (finding.message + " " + finding.rule.citation).lower()
    for overclaim in ("deprecat", "will be removed", "will be withdrawn", "rejected", "must "):
        assert overclaim not in text, f"the finding claims more than the snapshot says: {overclaim}"


def test_this_check_never_gates_an_exit_code() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Collection",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    findings = _unstable_findings(payload)
    assert findings and all(f.severity is not Severity.ERROR for f in findings)


def test_an_unstable_concept_value_is_disclosed() -> None:
    """Terms are covered wherever they appear, not only as types and keys."""
    schema = load_schema()
    concept = next(
        term
        for term, schemes in sorted(schema.concepts.items())
        if term in schema.unstable and "ceterms:CostType" in schemes
    )
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:CostProfile",
                "ceterms:directCostType": {
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:targetNode": concept,
                },
            }
        ]
    }
    assert concept in [f.value for f in _unstable_findings(payload)]


def test_every_unstable_class_the_snapshot_declares_is_covered() -> None:
    """A sweep over the index, so a re-vendoring widens the check with no edit."""
    schema = load_schema()
    classes = sorted(term for term in schema.unstable if term in schema.classes)
    assert classes, "the snapshot is meant to declare unstable classes"
    missed = [
        term
        for term in classes
        if not _unstable_findings({"@graph": [{"@id": ORG, "@type": term}]})
    ]
    assert not missed, f"unstable classes the check never disclosed: {missed}"
