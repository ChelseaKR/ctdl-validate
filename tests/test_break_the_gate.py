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
