"""--resolve: what a reference means once the document it names is in hand.

Three properties are the contract, and each has a test here that fails if it
stops holding: supplying a document can settle a reference, supplying a
document can never make the report about that document, and supplying nothing
relevant leaves the finding exactly where it was.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document
from ctdl_validate.cli import main
from ctdl_validate.graph import DocumentError
from ctdl_validate.schema import load_schema
from ctdl_validate.session import build_supplied

from .conftest import FIXTURES, fixture_path, load_fixture

RESOLVE = FIXTURES / "resolve"
VARIANTS = RESOLVE / "variants"
OWNER_IRI = "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826"
FRAMEWORK_IRI = (
    "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37"
)


def codes(findings: list[Any]) -> set[str]:
    return {f.code for f in findings}


def test_without_resolve_the_reference_is_unverifiable() -> None:
    findings = validate_document(load_fixture("external_reference.json"))
    assert codes(findings) == {"REF_OUTSIDE_PAYLOAD"}
    assert all(f.severity is Severity.UNVERIFIABLE for f in findings)


def test_a_supplied_document_settles_the_reference() -> None:
    findings = validate_document(
        load_fixture("external_reference.json"), [RESOLVE / "owner_organization.json"]
    )
    assert codes(findings) == {"REF_RESOLVED_SUPPLIED"}
    resolved = findings[0]
    assert resolved.severity is Severity.INFO
    assert "owner_organization.json" in resolved.message
    assert "ceterms:CredentialOrganization" in resolved.message


def test_the_same_reference_is_an_error_once_its_target_is_the_wrong_class() -> None:
    """The paired case: unverifiable without the neighbour, caught with it."""
    payload = load_fixture("external_reference.json")
    without = validate_document(payload)
    assert codes(without) == {"REF_OUTSIDE_PAYLOAD"}
    assert not any(f.severity is Severity.ERROR for f in without)

    with_neighbour = validate_document(payload, [VARIANTS / "owner_is_not_an_organization.json"])
    violation = [f for f in with_neighbour if f.code == "RANGE_VIOLATION"]
    assert len(violation) == 1
    assert violation[0].severity is Severity.ERROR
    assert "ceterms:Certification" in violation[0].message
    assert "owner_is_not_an_organization.json" in violation[0].message


def test_an_unsettled_reference_names_what_was_supplied() -> None:
    findings = validate_document(
        load_fixture("external_reference.json"), [RESOLVE / "framework_only.json"]
    )
    assert codes(findings) == {"REF_OUTSIDE_PAYLOAD"}
    assert findings[0].severity is Severity.UNVERIFIABLE
    assert "framework_only.json" in findings[0].message
    assert "None of the 1 document" in findings[0].message


def test_the_prompt_to_resolve_appears_when_nothing_was_supplied() -> None:
    findings = validate_document(load_fixture("external_reference.json"))
    assert "--resolve" in findings[0].message


def test_supplied_documents_are_never_themselves_validated() -> None:
    """A defect in a neighbour is that neighbour's problem, not this report's."""
    alone = validate_document(load_fixture("resolve/variants/owner_with_a_bare_uuid_ctid.json"))
    assert "CTID_BARE_UUID" in codes(alone), "fixture must actually be defective"

    findings = validate_document(
        load_fixture("external_reference.json"), [VARIANTS / "owner_with_a_bare_uuid_ctid.json"]
    )
    assert "CTID_BARE_UUID" not in codes(findings)
    assert codes(findings) == {"REF_RESOLVED_SUPPLIED"}


def test_a_directory_supplies_the_json_files_inside_it() -> None:
    findings = validate_document(load_fixture("external_reference.json"), [RESOLVE])
    assert codes(findings) == {"REF_RESOLVED_SUPPLIED"}


def test_a_directory_is_read_one_level_deep_in_sorted_order(tmp_path: Path) -> None:
    """Two documents claiming one @id: the first in sorted path order wins."""
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text((RESOLVE / "owner_organization.json").read_text(), encoding="utf-8")
    second.write_text(
        (VARIANTS / "owner_is_not_an_organization.json").read_text(), encoding="utf-8"
    )
    supplied = build_supplied([tmp_path], load_schema())
    assert supplied.entities[OWNER_IRI].source.endswith("a.json")
    assert supplied.documents == (str(first), str(second))


def test_blank_nodes_in_a_supplied_document_are_not_indexed(tmp_path: Path) -> None:
    """A blank node identifier means nothing outside the graph declaring it."""
    document = tmp_path / "bnodes.json"
    document.write_text(
        json.dumps(
            {
                "@context": "https://credreg.net/ctdl/schema/context/json",
                "@graph": [{"@id": "_:org1", "@type": "ceterms:CredentialOrganization"}],
            }
        ),
        encoding="utf-8",
    )
    supplied = build_supplied([document], load_schema())
    assert supplied.entities == {}
    assert supplied.documents == (str(document),)


def test_a_framework_supplied_alongside_puts_its_competency_back_in_reach() -> None:
    payload = load_fixture("resolve/competency_only.json")
    assert codes(validate_document(payload)) == {"REF_OUTSIDE_PAYLOAD"}
    assert codes(validate_document(payload, [RESOLVE / "framework_only.json"])) == {
        "REF_RESOLVED_SUPPLIED"
    }


def test_the_wrong_framework_identifier_is_caught_across_documents() -> None:
    """The bug class the tool exists for, with the framework in a second file."""
    payload = copy.deepcopy(load_fixture("resolve/competency_only.json"))
    payload["@graph"][0]["ceasn:isPartOf"] = (
        "https://credentialengineregistry.org/resources/ce-82566cee-17f3-4a6e-8f59-b45273aac457"
    )
    # Alone, the payload has no framework to compare against, so the tool says
    # only that it cannot see the target.
    assert "ISPARTOF_FRAMEWORK_MISMATCH" not in codes(validate_document(payload))

    findings = validate_document(payload, [RESOLVE / "framework_only.json"])
    mismatch = [f for f in findings if f.code == "ISPARTOF_FRAMEWORK_MISMATCH"]
    assert len(mismatch) == 1
    assert mismatch[0].severity is Severity.WARNING
    assert FRAMEWORK_IRI in mismatch[0].message


def test_an_unreadable_supplied_document_is_a_hard_stop(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(DocumentError):
        validate_document(load_fixture("external_reference.json"), [broken])


def test_a_missing_supplied_document_is_a_hard_stop(tmp_path: Path) -> None:
    with pytest.raises(DocumentError):
        validate_document(load_fixture("external_reference.json"), [tmp_path / "absent.json"])


def test_resolution_is_deterministic() -> None:
    args = (load_fixture("external_reference.json"), [RESOLVE])
    assert validate_document(*args) == validate_document(*args)


def test_the_cli_accepts_repeated_resolve_flags(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            str(fixture_path("external_reference.json")),
            "--resolve",
            str(RESOLVE / "framework_only.json"),
            "--resolve",
            str(RESOLVE / "owner_organization.json"),
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "REF_RESOLVED_SUPPLIED" in out
    assert "0 ERROR, 0 WARNING, 1 INFO, 0 UNVERIFIABLE" in out


def test_the_cli_exits_nonzero_when_a_supplied_document_proves_a_violation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code_alone = main([str(fixture_path("external_reference.json"))])
    assert exit_code_alone == 0
    capsys.readouterr()

    exit_code = main(
        [
            str(fixture_path("external_reference.json")),
            "--resolve",
            str(VARIANTS / "owner_is_not_an_organization.json"),
        ]
    )
    assert exit_code == 1
    assert "RANGE_VIOLATION" in capsys.readouterr().out


def test_an_unreadable_supplied_document_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [str(fixture_path("external_reference.json")), "--resolve", str(RESOLVE / "absent.json")]
    )
    assert exit_code == 2
    assert "cannot read" in capsys.readouterr().err
