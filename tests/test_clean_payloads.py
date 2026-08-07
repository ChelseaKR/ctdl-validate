"""Clean payloads pass with zero findings; external references are
UNVERIFIABLE, never a pass or a fail."""

from __future__ import annotations

from ctdl_validate import Severity, validate_document

from .conftest import load_fixture


def test_empty_graph_has_no_findings() -> None:
    assert validate_document(load_fixture("clean_empty_graph.json")) == []


def test_single_self_contained_entity_has_no_findings() -> None:
    assert validate_document(load_fixture("clean_single_entity.json")) == []


def test_entity_with_only_optional_properties_has_no_findings() -> None:
    assert validate_document(load_fixture("clean_optional_only.json")) == []


def test_clean_framework_graph_has_no_findings() -> None:
    assert validate_document(load_fixture("clean_framework.json")) == []


def test_reference_outside_payload_is_unverifiable_only() -> None:
    findings = validate_document(load_fixture("external_reference.json"))
    assert findings, "the external reference must be surfaced"
    assert {f.severity for f in findings} == {Severity.UNVERIFIABLE}
    assert {f.code for f in findings} == {"REF_OUTSIDE_PAYLOAD"}
    assert "cannot be confirmed or denied" in findings[0].message
