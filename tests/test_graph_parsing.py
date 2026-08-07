"""Input shapes: full IRIs, arrays, @id-object references, rejects."""

from __future__ import annotations

import pytest

from ctdl_validate import Severity, validate_document
from ctdl_validate.graph import DocumentError
from ctdl_validate.schema import load_schema


def test_full_iri_keys_and_types_are_compacted_and_checked() -> None:
    # The same bare-UUID bug, written with full IRIs instead of prefixed
    # terms; compaction must not let it slip through.
    payload = {
        "@type": "https://purl.org/ctdl/terms/Certification",
        "https://purl.org/ctdl/terms/ctid": "b55f88e3-dfd4-430b-ab47-3e5f9986e1e4",
    }
    findings = validate_document(payload)
    assert any(f.code == "CTID_BARE_UUID" and f.severity is Severity.ERROR for f in findings)


def test_reference_as_id_object_is_treated_as_a_reference() -> None:
    payload = {
        "@graph": [
            {
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:ownedBy": [{"@id": "_:org1"}],
            },
            {
                "@id": "_:org1",
                "@type": "ceterms:Organization",
                "ceterms:name": {"en-US": "Org referenced via an @id object"},
            },
        ]
    }
    assert validate_document(payload) == []


def test_scalar_document_is_rejected() -> None:
    with pytest.raises(DocumentError):
        validate_document(42)


def test_graph_must_be_an_array() -> None:
    with pytest.raises(DocumentError):
        validate_document({"@graph": {"@type": "ceterms:Certification"}})


def test_schema_index_loads_the_vendored_vocabularies() -> None:
    schema = load_schema()
    # Spot checks against the vendored files, not exhaustive counts.
    assert "ceterms:Certification" in schema.classes
    assert "ceasn:CompetencyFramework" in schema.classes
    assert schema.properties["ceasn:isPartOf"].range == frozenset({"ceasn:CompetencyFramework"})
    assert schema.properties["ceterms:hasPart"].inverse == "ceterms:isPartOf"
    assert schema.properties["ceterms:ctid"].id_coerced is False
    assert schema.properties["ceterms:ownedBy"].id_coerced is True
    assert "ceterms:Organization" in schema.ancestors_of("ceterms:CredentialOrganization")
