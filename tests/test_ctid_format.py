"""CTID grammar unit tests against the published definition."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document
from ctdl_validate.ctid import classify_ctid

from .conftest import load_fixture

PUBLISHED_EXAMPLE = "ce-e8a41a52-6ff6-48f0-9872-889c87b093b7"


def test_published_example_is_valid() -> None:
    shape = classify_ctid(PUBLISHED_EXAMPLE)
    assert shape.matches_shape and shape.lowercase and shape.uuid_v4


def test_bare_uuid_is_recognized_as_the_missing_prefix_case() -> None:
    shape = classify_ctid("e8a41a52-6ff6-48f0-9872-889c87b093b7")
    assert not shape.matches_shape
    assert shape.bare_uuid


def test_arbitrary_string_is_neither() -> None:
    shape = classify_ctid("certification-123")
    assert not shape.matches_shape
    assert not shape.bare_uuid


def test_wrong_group_lengths_do_not_match() -> None:
    assert not classify_ctid("ce-e8a41a52-6ff6-48f0-9872-889c87b093b").matches_shape
    assert not classify_ctid("ce-e8a41a526ff6-48f0-9872-889c87b093b7").matches_shape


def test_uppercase_and_non_v4_are_warnings_not_errors() -> None:
    findings = validate_document(load_fixture("ctid_warnings.json"))
    by_code = {f.code: f for f in findings}
    assert set(by_code) == {"CTID_UPPERCASE", "CTID_NOT_UUIDV4"}
    assert all(f.severity is Severity.WARNING for f in findings)
    # Honesty requirement: the WARNING explains why it is not an ERROR.
    assert "not documented" in by_code["CTID_UPPERCASE"].message
    assert "not documented" in by_code["CTID_NOT_UUIDV4"].message


def test_ctid_must_match_the_uri_tail() -> None:
    payload = {
        "@id": "https://credentialengineregistry.org/resources/ce-e8a41a52-6ff6-48f0-9872-889c87b093b7",
        "@type": "ceterms:Certification",
        "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
    }
    findings = validate_document(payload)
    assert any(f.code == "CTID_URI_MISMATCH" and f.severity is Severity.ERROR for f in findings)


def test_every_finding_cites_a_rule_with_a_source() -> None:
    findings = validate_document(load_fixture("bug_class_250_bare_uuid_for_ctid.json"))
    assert findings
    for finding in findings:
        assert finding.rule.citation
        assert finding.rule.url
        assert finding.rule.retrieved
