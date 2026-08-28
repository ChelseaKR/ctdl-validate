"""Check 8: a property the context declares a language map carries one.

The declaration under test is in the vendored context, which is why this
check exists and why its sibling -- validating that a value coerced to
``xsd:date`` is a date -- does not. See the module docstring of
``checks/language_map.py``.

Every payload is synthetic.
"""

from __future__ import annotations

from typing import Any

from ctdl_validate import Severity, validate_document
from ctdl_validate.schema import load_schema

ORG = "https://credentialengineregistry.org/resources/ce-11111111-1111-4111-8111-111111111111"


def _credential(name: Any) -> dict[str, Any]:
    return {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Credential",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:name": name,
            }
        ]
    }


def _language_findings(payload: dict[str, Any]) -> list[Any]:
    return [f for f in validate_document(payload) if f.code == "LANGUAGE_MAP_EXPECTED"]


def test_the_context_is_where_the_declaration_comes_from() -> None:
    schema = load_schema()
    assert schema.properties["ceterms:name"].language_map is True
    assert schema.properties["ceterms:ctid"].language_map is False


def test_a_language_map_is_clean() -> None:
    assert _language_findings(_credential({"en-US": "Nursing Assistant Certificate"})) == []


def test_a_bare_literal_where_a_language_map_is_declared_is_reported() -> None:
    findings = _language_findings(_credential("Nursing Assistant Certificate"))
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert findings[0].prop == "ceterms:name"
    assert "@container" in findings[0].rule.citation


def test_one_bare_literal_among_several_values_is_still_reported() -> None:
    findings = _language_findings(_credential([{"en-US": "tagged"}, "untagged"]))
    assert [f.value for f in findings] == ["untagged"]


def test_a_value_object_is_a_bare_literal_once_parsed() -> None:
    """``{"@value": "x"}`` carries no language either, and the parser unwraps it."""
    assert len(_language_findings(_credential({"@value": "untagged"}))) == 1


def test_a_property_that_is_not_a_language_map_is_left_alone() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Credential",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    assert _language_findings(payload) == []


def test_this_check_never_gates_an_exit_code() -> None:
    findings = _language_findings(_credential("untagged"))
    assert findings and all(f.severity is not Severity.ERROR for f in findings)


def test_every_language_map_property_is_covered_not_a_written_list() -> None:
    """Derived from the index, so a re-vendoring widens the check with no edit."""
    schema = load_schema()
    declared = sorted(term for term, p in schema.properties.items() if p.language_map)
    assert len(declared) == 67
    missed = []
    for prop in declared:
        payload = {"@graph": [{"@id": ORG, prop: "untagged"}]}
        if not [f for f in validate_document(payload) if f.code == "LANGUAGE_MAP_EXPECTED"]:
            missed.append(prop)
    assert not missed, f"language-map properties the check never looked at: {missed}"
