"""CTID grammar unit tests against the published definition."""

from __future__ import annotations

from typing import Any

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


# --- the @graph envelope's own @id (#58) -----------------------------------
#
# parse_document took data["@graph"] and discarded every other top-level key,
# so the envelope's @id never became visible to any check. That is the one
# position in which a Registry *graph* URI appears in a published Registry
# document -- in all five Registry-shaped fixtures here, "/graph/" occurs
# exactly once each, always as this key -- so REGISTRY_URI_MALFORMED could not
# fire on a real Registry payload, and the 1,200-document survey checked none
# of its 1,200 graph URIs.


def _registry_envelope(graph_id: str | None = None) -> Any:
    """The repo's own Registry-shaped fixture, optionally with a different @id."""
    payload = load_fixture("resolve/variants/owner_is_not_an_organization.json")
    if graph_id is not None:
        payload["@id"] = graph_id
    return payload


def test_the_registry_envelope_fixture_is_the_shape_this_check_is_about() -> None:
    """If the fixture stops being a Registry envelope the tests below prove nothing."""
    payload = _registry_envelope()
    assert payload["@id"].startswith("https://credentialengineregistry.org/graph/")
    assert isinstance(payload["@graph"], list) and payload["@graph"]
    assert validate_document(payload) == [], "the unmodified fixture must be clean"


def test_a_malformed_graph_uri_on_the_envelope_is_an_error() -> None:
    payload = _registry_envelope("https://credentialengineregistry.org/graph/not-a-ctid-at-all")
    findings = [f for f in validate_document(payload) if f.code == "REGISTRY_URI_MALFORMED"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    # The report says which position the URI sits in, not just that it is bad.
    assert "@graph envelope's own @id" in findings[0].message


def test_a_graph_uri_whose_ctid_no_entity_declares_is_an_error() -> None:
    payload = _registry_envelope(
        "https://credentialengineregistry.org/graph/ce-00000000-0000-4000-8000-000000000000"
    )
    findings = [f for f in validate_document(payload) if f.code == "CTID_URI_MISMATCH"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    # The finding names what the payload does declare, so it is actionable.
    assert "ce-79298677-d0e4-4799-853a-a633d9071826" in findings[0].message


def test_a_graph_uri_matching_the_resource_uri_tail_alone_is_accepted() -> None:
    """The resource need not repeat ceterms:ctid for the graph URI to check out.

    The CTID is declared in two positions and either satisfies the envelope;
    requiring ceterms:ctid specifically would report documents that are correct.
    """
    payload = _registry_envelope()
    for entity in payload["@graph"]:
        entity.pop("ceterms:ctid", None)
    assert [f for f in validate_document(payload) if f.code == "CTID_URI_MISMATCH"] == []


def test_an_envelope_id_that_is_not_a_registry_uri_is_not_judged() -> None:
    """Only Registry URIs carry the CTID-tail contract; nothing else is invented."""
    payload = _registry_envelope("https://example.org/some/other/graph")
    assert validate_document(payload) == []


def test_a_document_with_no_envelope_is_unaffected() -> None:
    """The single-entity and bare-array shapes have no envelope to read."""
    entity = {
        "@id": "https://credentialengineregistry.org/resources/ce-e8a41a52-6ff6-48f0-9872-889c87b093b7",
        "@type": "ceterms:Certification",
        "ceterms:ctid": "ce-e8a41a52-6ff6-48f0-9872-889c87b093b7",
    }
    assert validate_document(entity) == []
    assert validate_document([entity]) == []
