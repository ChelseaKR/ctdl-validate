"""The JSON report has a published shape, and the suite holds it to it.

Until this file existed, the shape of ``--format json`` was whatever
``render_findings_json`` happened to write. Three consumers parse it -- the
GitHub Action, the playground (which renders the same report through Pyodide
and offers it as a download), and the Registry survey harness -- and one of
them, the Action, read its counts with ``summary.get(severity, 0)``: a key
that went missing counted as zero findings and the gate passed. An absence
published as a measurement, in the tool whose purpose is to refuse exactly
that.

So: ``report.schema.json`` is shipped as package data, ``--report-schema``
prints it, every report carries ``report_schema_version``, and everything
below either validates a real report against that schema or breaks the
contract on purpose and checks that something notices.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import (
    REPORT_SCHEMA_VERSION,
    Finding,
    Rule,
    Severity,
    read_report_schema,
    validate_document,
)
from ctdl_validate import __version__ as tool_version
from ctdl_validate.findings import render_findings_json
from ctdl_validate.report import REPORT_SCHEMA_PATH

from .conftest import fixture_path, load_fixture
from .schema_check import UnsupportedKeyword, check

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "index.html"
SCHEMA: dict[str, Any] = json.loads(read_report_schema())

#: Fixtures whose live reports are validated. Between them they carry every
#: severity the tool emits, and both a clean and a failing payload.
DOCUMENTS = [
    "clean_framework.json",
    "clean_single_entity.json",
    "clean_empty_graph.json",
    "domain_violation.json",
    "ctid_warnings.json",
    "inverse_mismatch.json",
    "unresolved_bnode.json",
    "external_reference.json",
]


def _report(document: str) -> dict[str, Any]:
    findings = validate_document(load_fixture(document))
    report: dict[str, Any] = json.loads(render_findings_json(findings, tool_version))
    return report


# -- the schema is published, and it is what the report says it is -------------


def test_the_schema_ships_as_package_data() -> None:
    listed = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"report.schema.json"' in listed, "package-data no longer ships the schema"
    assert REPORT_SCHEMA_PATH.is_file()


def test_the_report_schema_flag_prints_the_shipped_schema_and_exits_clean() -> None:
    command = [sys.executable, "-m", "ctdl_validate", "--report-schema"]
    runs = [subprocess.run(command, capture_output=True, check=False) for _ in range(2)]
    assert runs[0].returncode == 0
    assert runs[0].stdout == runs[1].stdout
    assert runs[0].stdout.decode("utf-8") == REPORT_SCHEMA_PATH.read_text(encoding="utf-8")
    assert json.loads(runs[0].stdout)["$schema"].endswith("/2020-12/schema")


def test_the_schemas_declared_version_is_the_one_reports_carry() -> None:
    assert SCHEMA["properties"]["report_schema_version"]["const"] == REPORT_SCHEMA_VERSION
    assert REPORT_SCHEMA_VERSION.count(".") == 2


def test_every_report_declares_the_schema_version_and_the_tool_version() -> None:
    report = _report("domain_violation.json")
    assert report["report_schema_version"] == REPORT_SCHEMA_VERSION
    assert report["tool"] == {"name": "ctdl-validate", "version": tool_version}


def test_the_schema_version_is_not_the_tool_version() -> None:
    """They are allowed to coincide by accident, but nothing may derive one
    from the other: a release that bumps the tool must not silently claim a
    new report shape."""
    source = (ROOT / "src" / "ctdl_validate" / "report.py").read_text(encoding="utf-8")
    assert "__version__" not in source
    assert re.search(r'REPORT_SCHEMA_VERSION = "\d+\.\d+\.\d+"', source)


# -- every report the suite can produce conforms -------------------------------


@pytest.mark.parametrize("document", DOCUMENTS)
def test_a_live_report_validates_against_the_shipped_schema(document: str) -> None:
    assert check(_report(document), SCHEMA) == []


def test_the_cli_output_validates_against_the_shipped_schema() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ctdl_validate",
            str(fixture_path("domain_violation.json")),
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert check(json.loads(completed.stdout), SCHEMA) == []


def test_a_report_with_no_findings_at_all_still_conforms() -> None:
    empty = json.loads(render_findings_json([], tool_version))
    assert check(empty, SCHEMA) == []
    assert empty["summary"] == {"ERROR": 0, "WARNING": 0, "INFO": 0, "UNVERIFIABLE": 0}


# -- the playground reads the same shape ---------------------------------------


def _bootstrap_source() -> str:
    page = PAGE.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="text/plain" id="py-bootstrap">(.*?)</script>', page, re.DOTALL
    )
    assert match, "the page no longer carries a py-bootstrap block"
    return match.group(1)


def test_the_playground_download_is_the_cli_renderer_and_not_a_second_one() -> None:
    """The page's Download button hands over whatever its ``json`` key holds.

    Rather than assert the page's bytes -- which needs a browser and a 5.6 MB
    runtime -- this pins the one property that makes them conform: the page
    does not build a report, it calls the same renderer, so it carries
    ``report_schema_version`` for the same reason the CLI does. A second
    formatter written on the page would fail here.
    """
    source = _bootstrap_source()
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_findings_json"
    ]
    assert len(calls) == 1, "the page should render the JSON report exactly once"
    assert re.findall(r'"json":\s*([a-z_]+)\(', source) == ["render_findings_json"]


def test_the_playground_result_is_assembled_from_the_renderers_and_nothing_else() -> None:
    """The dict the page hands to JavaScript. ``json`` and ``text`` are the
    CLI's own renderers; ``findings`` is ``Finding.to_dict``, the same method
    the report is built from. Anything else appearing here would be a second
    description of a finding, which is the thing that goes stale."""
    source = _bootstrap_source()
    body = source[source.index("def run(") :]
    body = body[: body.index("\ndef ")]
    keys = re.findall(r'^\s+"([a-z_]+)":', body, re.MULTILINE)
    assert sorted(keys) == ["findings", "json", "text", "version"], keys


# -- break the contract on purpose ---------------------------------------------


def _valid() -> dict[str, Any]:
    return _report("domain_violation.json")


def test_renaming_summary_is_caught_before_it_reaches_a_consumer() -> None:
    report = _valid()
    report["totals"] = report.pop("summary")
    errors = check(report, SCHEMA)
    assert any("summary" in e for e in errors), errors
    assert any("totals" in e for e in errors), errors


def test_a_summary_missing_one_severity_is_caught() -> None:
    report = _valid()
    del report["summary"]["UNVERIFIABLE"]
    assert check(report, SCHEMA) != []


def test_a_count_that_is_not_a_number_is_caught() -> None:
    report = _valid()
    report["summary"]["ERROR"] = "1"
    assert check(report, SCHEMA) != []


def test_a_negative_count_is_caught() -> None:
    report = _valid()
    report["summary"]["ERROR"] = -1
    assert check(report, SCHEMA) != []


def test_an_unknown_severity_is_caught() -> None:
    report = _valid()
    report["findings"][0]["severity"] = "CRITICAL"
    assert check(report, SCHEMA) != []


def test_a_finding_that_lost_its_rule_is_caught() -> None:
    report = _valid()
    del report["findings"][0]["rule"]
    assert check(report, SCHEMA) != []


def test_a_finding_that_lost_its_retrieval_date_is_caught() -> None:
    report = _valid()
    del report["findings"][0]["rule"]["retrieved"]
    assert check(report, SCHEMA) != []


def test_a_finding_that_lost_its_entity_is_caught() -> None:
    report = _valid()
    del report["findings"][0]["entity"]
    assert check(report, SCHEMA) != []


def test_a_new_undeclared_key_is_caught_rather_than_ignored() -> None:
    report = _valid()
    report["findings"][0]["confidence"] = 0.9
    assert check(report, SCHEMA) != []


def test_a_report_declaring_the_wrong_schema_version_is_caught() -> None:
    report = _valid()
    report["report_schema_version"] = "2.0.0"
    assert check(report, SCHEMA) != []


def test_a_report_with_no_schema_version_at_all_is_caught() -> None:
    report = _valid()
    del report["report_schema_version"]
    assert check(report, SCHEMA) != []


# -- the checker itself cannot pass by ignoring --------------------------------


def test_the_checker_refuses_a_keyword_it_does_not_enforce() -> None:
    """A subset checker that skipped unknown keywords would be a gate that
    cannot fail on the half of the contract it does not implement."""
    with pytest.raises(UnsupportedKeyword):
        check({"a": 1}, {"type": "object", "patternProperties": {"^a$": {"type": "string"}}})


def test_the_checker_enforces_every_keyword_the_shipped_schema_uses() -> None:
    assert check(_valid(), SCHEMA) == []
    assert check({}, SCHEMA) != []


def test_the_checker_does_not_confuse_a_boolean_with_an_integer() -> None:
    assert check(True, {"type": "integer"}) != []
    assert check(1, {"type": "integer"}) == []


def test_the_checker_reads_local_references() -> None:
    schema = {
        "type": "object",
        "properties": {"n": {"$ref": "#/$defs/count"}},
        "$defs": {"count": {"type": "integer", "minimum": 0}},
    }
    assert check({"n": 1}, schema) == []
    assert check({"n": -1}, schema) != []


# -- the schema and the renderer cannot drift apart ----------------------------


def test_every_key_the_renderer_writes_is_declared_by_the_schema() -> None:
    report = _valid()
    assert set(report) == set(SCHEMA["properties"])
    declared = set(SCHEMA["$defs"]["finding"]["properties"])
    for finding in report["findings"]:
        assert set(finding) == declared, set(finding) ^ declared


def test_the_schema_declares_the_severities_the_tool_actually_has() -> None:
    assert SCHEMA["$defs"]["severity"]["enum"] == [s.value for s in Severity]
    assert set(SCHEMA["properties"]["summary"]["required"]) == {s.value for s in Severity}


def test_a_hand_built_finding_of_every_severity_conforms() -> None:
    rule = Rule(citation="c", url="https://example.invalid/", retrieved="2026-01-01")
    findings = [
        Finding("CODE", severity, "urn:ctid:x", "ceterms:name", "v", "m", rule)
        for severity in Severity
    ]
    report = json.loads(render_findings_json(findings, tool_version))
    assert check(report, SCHEMA) == []
    assert report["summary"] == dict.fromkeys((s.value for s in Severity), 1)


def test_the_shipped_schema_is_byte_stable() -> None:
    raw = REPORT_SCHEMA_PATH.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + "\n" == raw
