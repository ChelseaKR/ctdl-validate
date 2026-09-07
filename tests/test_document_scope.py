"""A document this tool has nothing to say about is not a clean payload.

``ctdl-validate`` checks terms in the ``ceterms:`` and ``ceasn:`` namespaces. A
document declaring none of them trips no rule -- correctly. What was wrong is
that the *report* of such a run was indistinguishable from the report of a
clean CTDL payload: both read ``0 finding(s): 0 ERROR, 0 WARNING, 0 INFO, 0
UNVERIFIABLE`` and both exited 0.

Measured on 2026-09-07 against this repository's own files: ``package.json``,
``tsconfig.json``, ``{}``, ``[]``, ``src/ctdl_validate/report.schema.json``
and the vendored ``vendor/ctdl/context.json`` each produced exactly that
report. The sibling tool refuses the same input -- ``oscal-validate`` exits 2
with "no OSCAL model root found" -- so the two validators disagreed about what
to do with a file that is not theirs.

That matters most where #63 wants to put this tool: a ``pre-commit`` hook with
``types: [json]`` hands the validator every JSON file in a repository, and a
wall of clean reports over files that are not CTDL reads as a passing gate.
The exit contract is unchanged on purpose -- a document that parses is not a
document that could not be read -- so the report has to carry the fact instead.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import __version__
from ctdl_validate.findings import render_findings_json, render_findings_text
from ctdl_validate.graph import parse_document, scope_of
from ctdl_validate.report import REPORT_SCHEMA_PATH, DocumentScope
from ctdl_validate.schema import load_schema
from ctdl_validate.validator import build_session, validate

from .conftest import fixture_path, load_fixture
from .schema_check import UnsupportedKeyword, check

SCHEMA: dict[str, Any] = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

#: Shapes that are valid JSON, that this tool reads without complaint, and that
#: contain nothing it checks. The first two are the files a `types: [json]`
#: pre-commit hook would hand it in almost any repository.
NOT_CTDL: list[tuple[str, Any]] = [
    ("package.json", {"name": "my-app", "version": "1.0.0", "scripts": {"test": "jest"}}),
    ("tsconfig.json", {"compilerOptions": {"strict": True}, "include": ["src"]}),
    ("empty object", {}),
    ("empty array", []),
]


def _scope(data: Any) -> DocumentScope:
    return scope_of(parse_document(data, load_schema()))


def _report(data: Any) -> dict[str, Any]:
    session = build_session(data)
    findings = validate(session)
    rendered: dict[str, Any] = json.loads(
        render_findings_json(findings, __version__, scope=scope_of(session.graph))
    )
    return rendered


# -- the condition this exists for --------------------------------------------


@pytest.mark.parametrize(("label", "data"), NOT_CTDL, ids=[n for n, _ in NOT_CTDL])
def test_a_document_with_nothing_to_check_says_so_rather_than_reporting_it_clean(
    label: str, data: Any
) -> None:
    report = _report(data)
    assert report["findings"] == [], f"{label} should trip no rule"
    assert report["summary"] == {"ERROR": 0, "WARNING": 0, "INFO": 0, "UNVERIFIABLE": 0}
    # The one thing that now tells this apart from a clean CTDL payload.
    assert report["document"]["checked_entities"] == 0


def test_a_clean_ctdl_payload_reports_entities_it_actually_checked() -> None:
    report = _report(load_fixture("clean_framework.json"))
    assert report["findings"] == []
    assert report["summary"]["ERROR"] == 0
    assert report["document"]["checked_entities"] > 0
    assert report["document"]["entities"] >= report["document"]["checked_entities"]


def test_the_two_reports_differ_in_exactly_the_field_that_was_added() -> None:
    """Without ``document`` the two runs are the same bytes. That was the defect."""
    nothing = _report({"name": "my-app", "version": "1.0.0"})
    clean = _report(load_fixture("clean_framework.json"))
    del nothing["document"], clean["document"]
    assert nothing == clean, (
        "if these ever differ for another reason, this test is no longer measuring the "
        "thing it was written to measure"
    )


def test_the_text_report_says_it_in_words() -> None:
    session = build_session({"name": "my-app"})
    text = render_findings_text(validate(session), scope=scope_of(session.graph))
    assert "Nothing here was checked" in text
    assert "1 entity read" in text


def test_a_clean_payload_gets_no_such_line() -> None:
    session = build_session(load_fixture("clean_framework.json"))
    text = render_findings_text(validate(session), scope=scope_of(session.graph))
    assert "Nothing here was checked" not in text


# -- what counts as checked ---------------------------------------------------


def test_a_ceterms_type_puts_an_entity_in_scope() -> None:
    assert _scope({"@type": "ceterms:Credential"}).checked_entities == 1


def test_a_ceasn_property_puts_an_entity_in_scope_even_with_no_type() -> None:
    """A node can carry checked properties under a class the snapshot does not name.

    Counting only ``@type`` would have called such an entity out of scope while
    ``domain_range`` was busy emitting findings about it.
    """
    assert (
        _scope({"@id": "https://example.org/x", "ceasn:competencyText": "x"}).checked_entities == 1
    )


def test_a_type_outside_the_checked_namespaces_is_not_in_scope() -> None:
    assert _scope({"@type": "schema:Organization", "name": "x"}).checked_entities == 0


def test_nested_entities_are_counted() -> None:
    scope = _scope(
        {
            "@type": "ceterms:Credential",
            "ceterms:owns": {"@type": "ceterms:CredentialOrganization"},
        }
    )
    assert scope.entities == 2
    assert scope.checked_entities == 2


# -- three states, not two ----------------------------------------------------


def test_a_producer_that_did_not_measure_the_scope_publishes_null_not_zero() -> None:
    """``null`` and ``0`` are different facts and the report keeps them apart.

    A caller rendering findings it assembled by hand has no document to measure.
    Writing ``0`` there would be the same defect this field removes, pointing
    the other way: an unmeasured scope reading as "nothing was checked".
    """
    report = json.loads(render_findings_json([], __version__))
    assert report["document"] == {"entities": None, "checked_entities": None}
    assert check(report, SCHEMA) == []


def test_the_text_report_stays_silent_when_the_scope_was_not_measured() -> None:
    assert "Nothing here was checked" not in render_findings_text([])


# -- the published schema moved with the report -------------------------------


def test_the_schema_declares_the_new_field_and_the_version_moved() -> None:
    assert SCHEMA["properties"]["report_schema_version"]["const"] == "1.1.0"
    assert "document" in SCHEMA["required"]
    assert set(SCHEMA["$defs"]["measured_count"]["type"]) == {"integer", "null"}


@pytest.mark.parametrize(("label", "data"), NOT_CTDL, ids=[n for n, _ in NOT_CTDL])
def test_every_such_report_still_conforms_to_the_shipped_schema(label: str, data: Any) -> None:
    assert check(_report(data), SCHEMA) == []


def test_a_report_that_lost_the_document_block_is_caught() -> None:
    report = _report({})
    del report["document"]
    assert check(report, SCHEMA) != []


def test_a_scope_count_that_is_a_string_is_caught() -> None:
    report = _report({})
    report["document"]["checked_entities"] = "0"
    assert check(report, SCHEMA) != []


def test_the_checker_accepts_a_type_union_and_still_refuses_a_name_it_lacks() -> None:
    """The union was added for ``measured_count``; it is not an escape hatch."""
    union = {"type": ["integer", "null"], "minimum": 0}
    assert check(1, union) == []
    assert check(None, union) == []
    assert check("1", union) != []
    with pytest.raises(UnsupportedKeyword):
        check(1, {"type": ["integer", "decimal"]})
    with pytest.raises(UnsupportedKeyword):
        check(1, {"type": []})


# -- the contracts that must not have moved -----------------------------------


def test_the_exit_code_for_a_document_with_nothing_to_check_is_still_zero(
    tmp_path: Path,
) -> None:
    """``docs/API.md`` pins exit 2 for input that could not be read. This parses.

    Read from a real process rather than through a pipe, so the number tested is
    the one a hook would see.
    """
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"name": "my-app", "version": "1.0.0"}), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "ctdl_validate", str(path)],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert b"Nothing here was checked" in completed.stdout


def test_a_broken_payload_still_exits_one_and_is_not_called_unchecked() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ctdl_validate", str(fixture_path("domain_violation.json"))],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert b"Nothing here was checked" not in completed.stdout


def test_two_runs_over_the_same_document_render_the_same_bytes() -> None:
    first = render_findings_json([], __version__, scope=_scope({"@type": "ceterms:Credential"}))
    second = render_findings_json([], __version__, scope=_scope({"@type": "ceterms:Credential"}))
    assert first == second
