"""``--format sarif``: the same findings, in SARIF 2.1.0, with no pass invented.

Four things are pinned here. The output validates against the vendored OASIS
schema, offline. It carries exactly the findings the canonical JSON report
carries, in the same order, with the same citation on each. The severity
mapping never produces ``kind: pass``, and an UNVERIFIABLE finding is
``open``. And every log says which vendored snapshot decided it, computed from
the bytes the run read.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft4Validator

from ctdl_validate import __version__, snapshot, validate_document
from ctdl_validate.cli import main
from ctdl_validate.findings import Finding, Rule, Severity, render_findings_json
from ctdl_validate.rules import RETRIEVED
from ctdl_validate.sarif import (
    DESCRIPTIONS,
    FINGERPRINT,
    KINDS,
    merge_logs,
    render_findings_sarif,
)
from ctdl_validate.snapshot import VENDORED_FILES, digests

from . import test_vendor_integrity
from .conftest import fixture_path, load_fixture
from .sarif.capture import CASES, HERE, ROOT, run

EXPECTED_VENDOR_HASHES = test_vendor_integrity.EXPECTED

SCHEMA = json.loads((HERE / "sarif-schema-2.1.0.json").read_text(encoding="utf-8"))
CHECKS = ROOT / "src" / "ctdl_validate" / "checks"


def _findings(name: str, resolve: list[Path] | None = None) -> list[Finding]:
    return validate_document(load_fixture(name), resolve)


def _sarif(name: str, resolve: list[Path] | None = None) -> dict[str, Any]:
    log: dict[str, Any] = json.loads(
        render_findings_sarif(_findings(name, resolve), __version__, fixture_path(name))
    )
    return log


def _report(name: str, resolve: list[Path] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = json.loads(render_findings_json(_findings(name, resolve), __version__))
    return report


# -- the schema, offline -------------------------------------------------------


def test_the_vendored_schema_is_the_sarif_2_1_0_schema() -> None:
    assert SCHEMA["id"].endswith("/sarif-schema-2.1.0.json")
    assert SCHEMA["properties"]["version"]["enum"] == ["2.1.0"]
    Draft4Validator.check_schema(SCHEMA)


def test_the_vendored_schema_is_the_bytes_its_provenance_records() -> None:
    """The provenance row in tests/sarif/README.md is the only statement of
    where this file came from, and a hash nobody checks is a hash nobody can
    rely on."""
    raw = (HERE / "sarif-schema-2.1.0.json").read_bytes()
    recorded = re.search(
        r"`sarif-schema-2\.1\.0\.json`.*?SHA-256 `([0-9a-f]{64})`",
        (HERE / "README.md").read_text(encoding="utf-8"),
        re.S,
    )
    assert recorded is not None, "README.md records no hash for the vendored SARIF schema"
    assert hashlib.sha256(raw).hexdigest() == recorded.group(1)


@pytest.mark.parametrize(
    "document",
    [
        "clean_framework.json",
        "bug_class_250_bare_uuid_for_ctid.json",
        "bug_class_252_wrong_framework_identifier.json",
        "ctid_warnings.json",
        "external_reference.json",
        "inverse_mismatch.json",
    ],
)
def test_every_report_validates_against_the_sarif_schema(document: str) -> None:
    log = _sarif(document)
    errors = sorted(Draft4Validator(SCHEMA).iter_errors(log), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


# -- the goldens ---------------------------------------------------------------


@pytest.mark.parametrize(("name", "document"), CASES)
def test_the_cli_reproduces_the_golden_sarif_bytes(name: str, document: str) -> None:
    expected = (HERE / f"{name}.sarif.out").read_bytes()
    assert run(document) == expected, f"{name} drifted from the golden"


def test_sarif_output_is_byte_identical_across_processes() -> None:
    command = [
        sys.executable,
        "-m",
        "ctdl_validate",
        str(Path("tests") / "fixtures" / "bug_class_252_wrong_framework_identifier.json"),
        "--format",
        "sarif",
    ]
    runs = [subprocess.run(command, capture_output=True, check=False, cwd=ROOT) for _ in range(2)]
    assert runs[0].stdout == runs[1].stdout
    assert runs[0].stdout
    json.loads(runs[0].stdout)


def test_the_report_carries_no_timestamp() -> None:
    rendered = json.dumps(_sarif("bug_class_252_wrong_framework_identifier.json"))
    for word in ("timestamp", "startTimeUtc", "endTimeUtc", "generated_at", "duration"):
        assert word not in rendered


# -- the same findings as the canonical report ---------------------------------


def test_sarif_carries_every_finding_of_the_json_report_in_the_same_order() -> None:
    name = "bug_class_252_wrong_framework_identifier.json"
    report = _report(name)
    results = _sarif(name)["runs"][0]["results"]
    assert len(results) == len(report["findings"]) > 0
    for finding, result in zip(report["findings"], results, strict=True):
        assert result["ruleId"] == finding["code"]
        assert result["properties"]["severity"] == finding["severity"]
        assert result["properties"]["entity"] == finding["entity"]
        assert result["properties"]["property"] == finding["property"]
        assert result["properties"]["value"] == finding["value"]
        assert result["properties"]["rule"] == finding["rule"]
        assert finding["message"] in result["message"]["text"]
        assert finding["rule"]["citation"] in result["message"]["text"]
        assert f"retrieved {finding['rule']['retrieved']}" in result["message"]["text"]


def test_the_run_summary_is_the_json_reports_summary() -> None:
    name = "bug_class_252_wrong_framework_identifier.json"
    run_properties = _sarif(name)["runs"][0]["properties"]
    assert run_properties["summary"] == _report(name)["summary"]
    assert run_properties["summary"] == {"ERROR": 1, "WARNING": 1, "INFO": 0, "UNVERIFIABLE": 1}


def test_the_tool_names_itself_and_its_version_and_its_document() -> None:
    name = "clean_framework.json"
    log = _sarif(name)
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ctdl-validate"
    assert driver["version"] == __version__
    assert driver["informationUri"].startswith("https://")
    assert log["runs"][0]["properties"]["document"] == {"path": fixture_path(name).as_uri()}


# -- severities: never a pass ---------------------------------------------------


def test_error_is_a_fail_and_unverifiable_is_open() -> None:
    results = _sarif("bug_class_252_wrong_framework_identifier.json")["runs"][0]["results"]
    by_severity = {r["properties"]["severity"]: r for r in results}
    assert by_severity["ERROR"]["kind"] == "fail"
    assert by_severity["ERROR"]["level"] == "error"
    assert by_severity["WARNING"]["kind"] == "fail"
    assert by_severity["WARNING"]["level"] == "warning"
    unverifiable = by_severity["UNVERIFIABLE"]
    assert unverifiable["kind"] == "open", "UNVERIFIABLE is evaluated and unsettled, not a pass"
    assert unverifiable["level"] == "note", "level none would hide it from code scanning"
    assert unverifiable["properties"]["severity"] == "UNVERIFIABLE"


def test_no_result_is_ever_a_pass() -> None:
    for name in ("bug_class_250_bare_uuid_for_ctid.json", "ctid_warnings.json"):
        for result in _sarif(name)["runs"][0]["results"]:
            assert result["kind"] != "pass"
    assert all(kind != "pass" for kind, _ in KINDS.values())


def test_a_clean_payload_reports_nothing_rather_than_reporting_a_pass() -> None:
    """The one place an empty results array is correct: nothing was found. It
    must not be dressed up as a passing check."""
    log = _sarif("clean_framework.json")
    assert log["runs"][0]["results"] == []
    assert log["runs"][0]["properties"]["summary"] == {
        "ERROR": 0,
        "WARNING": 0,
        "INFO": 0,
        "UNVERIFIABLE": 0,
    }


def test_an_info_finding_is_informational_and_still_shown() -> None:
    results = _sarif("inverse_mismatch.json")["runs"][0]["results"]
    info = [r for r in results if r["properties"]["severity"] == "INFO"]
    assert info, "the fixture must produce an INFO finding for this to test anything"
    for result in info:
        assert result["kind"] == "informational"
        assert result["level"] == "note"


# -- rules and citations --------------------------------------------------------


def test_every_result_points_at_a_rule_that_names_its_sources() -> None:
    log = _sarif("bug_class_252_wrong_framework_identifier.json")
    rules = log["runs"][0]["tool"]["driver"]["rules"]
    for result in log["runs"][0]["results"]:
        rule = rules[result["ruleIndex"]]
        assert rule["id"] == result["ruleId"]
        cited = {(s["url"], s["retrieved"]) for s in rule["properties"]["sources"]}
        carried = result["properties"]["rule"]
        assert (carried["url"], carried["retrieved"]) in cited


def test_the_ctid_rule_carries_the_published_ctid_citation() -> None:
    log = _sarif("bug_class_250_bare_uuid_for_ctid.json")
    rules = {rule["id"]: rule for rule in log["runs"][0]["tool"]["driver"]["rules"]}
    assert rules["CTID_BARE_UUID"]["helpUri"] == "https://credreg.net/ctdl/ctid"
    for result in log["runs"][0]["results"]:
        assert "CTID" in result["message"]["text"]
        assert result["properties"]["rule"]["url"] == "https://credreg.net/ctdl/ctid"


def test_help_uri_is_the_citation_url_and_only_when_it_is_a_url() -> None:
    tool_policy = Rule(citation="tool policy", url="tool policy (README)", retrieved="-")
    published = Rule(citation="published", url="https://credreg.net/ctdl/ctid", retrieved="x")
    findings = [
        Finding("A", Severity.ERROR, "e", "p", "v", "m", tool_policy),
        Finding("B", Severity.ERROR, "e", "p", "v", "m", published),
    ]
    rules = json.loads(render_findings_sarif(findings, "0", Path("x.json")))["runs"][0]["tool"][
        "driver"
    ]["rules"]
    by_id = {rule["id"]: rule for rule in rules}
    assert "helpUri" not in by_id["A"], "a non-URL citation must not become a helpUri"
    assert by_id["B"]["helpUri"] == "https://credreg.net/ctdl/ctid"


def test_a_code_cited_from_two_sources_keeps_both_and_no_single_help_uri() -> None:
    ctdl = Rule(citation="c", url="https://credreg.net/ctdl/schema/encoding/json", retrieved="x")
    ctdlasn = Rule(
        citation="c", url="https://credreg.net/ctdlasn/schema/encoding/json", retrieved="x"
    )
    findings = [
        Finding("RANGE_VIOLATION", Severity.ERROR, "e1", "p", "v", "m", ctdl),
        Finding("RANGE_VIOLATION", Severity.ERROR, "e2", "p", "v", "m", ctdlasn),
    ]
    rule = json.loads(render_findings_sarif(findings, "0", Path("x.json")))["runs"][0]["tool"][
        "driver"
    ]["rules"][0]
    assert "helpUri" not in rule
    assert [s["url"] for s in rule["properties"]["sources"]] == [
        "https://credreg.net/ctdl/schema/encoding/json",
        "https://credreg.net/ctdlasn/schema/encoding/json",
    ]


def test_every_code_the_checks_can_emit_has_a_description() -> None:
    """A rule with no shortDescription shows in a code-scanning list as its
    bare code. Reading the codes by AST, not by regex, because a ``[A-Z_]+``
    scan silently omits ``CTID_NOT_UUIDV4``."""
    emitted: set[str] = set()
    for path in sorted(CHECKS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if (
                    value.isupper()
                    and len(value) > 3
                    and re.fullmatch(r"[A-Z][A-Z0-9_]+", value)
                    and value not in {s.value for s in Severity}
                    and value != "ALL_CHECKS"
                ):
                    emitted.add(value)
    assert emitted, "no finding codes were found; the AST scan is broken, not the descriptions"
    assert emitted <= set(DESCRIPTIONS), f"no description for {sorted(emitted - set(DESCRIPTIONS))}"
    assert set(DESCRIPTIONS) <= emitted, (
        f"stale description for {sorted(set(DESCRIPTIONS) - emitted)}"
    )


# -- locations ------------------------------------------------------------------


def test_locations_carry_the_document_and_the_entity_and_no_line() -> None:
    name = "bug_class_250_bare_uuid_for_ctid.json"
    for result in _sarif(name)["runs"][0]["results"]:
        location = result["locations"][0]
        assert (
            location["physicalLocation"]["artifactLocation"]["uri"] == fixture_path(name).as_uri()
        )
        assert "region" not in location["physicalLocation"]
        logical = location["logicalLocations"][0]
        assert logical["fullyQualifiedName"] == result["properties"]["entity"]


def test_a_relative_document_path_is_kept_relative() -> None:
    findings = _findings("clean_framework.json")
    log = json.loads(render_findings_sarif(findings, "0", Path("payloads/a.json")))
    assert log["runs"][0]["properties"]["document"]["path"] == "payloads/a.json"


def test_fingerprints_are_stable_and_distinct() -> None:
    name = "bug_class_252_wrong_framework_identifier.json"
    first = _sarif(name)["runs"][0]["results"]
    second = _sarif(name)["runs"][0]["results"]
    prints = [r["partialFingerprints"][FINGERPRINT] for r in first]
    assert prints == [r["partialFingerprints"][FINGERPRINT] for r in second]
    assert len(set(prints)) == len(prints)


# -- which bytes decided it -----------------------------------------------------


def test_the_driver_records_the_snapshot_date_and_a_digest_of_every_vendored_file() -> None:
    driver = _sarif("clean_framework.json")["runs"][0]["tool"]["driver"]
    recorded = driver["properties"]["vendoredSnapshot"]
    assert recorded["retrieved"] == RETRIEVED
    assert recorded["algorithm"] == "sha256"
    assert set(recorded["files"]) == set(VENDORED_FILES)
    for digest in recorded["files"].values():
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_the_driver_digests_are_the_hashes_the_integrity_gate_records() -> None:
    """The digests are computed from the files; these are transcribed from
    SOURCES.md. They are two independent answers to "which snapshot is this",
    and the whole value of shipping the first one is that it can disagree with
    the second."""
    recorded = _sarif("clean_framework.json")["runs"][0]["tool"]["driver"]["properties"][
        "vendoredSnapshot"
    ]["files"]
    assert recorded == EXPECTED_VENDOR_HASHES


def test_the_snapshot_identity_covers_every_vendored_file() -> None:
    """A partial fingerprint is the worse failure: it looks complete while a
    changed encoding passes under it."""
    vendored = ROOT / "src" / "ctdl_validate" / "vendor"
    on_disk = {
        str(path.relative_to(vendored).as_posix())
        for path in vendored.rglob("*")
        if path.is_file() and path.name != "SOURCES.md"
    }
    assert on_disk == set(VENDORED_FILES)


def test_the_digests_are_taken_from_the_bytes_and_not_from_a_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alter one vendored file's bytes and the digest must move with them. A
    digest transcribed from SOURCES.md would sit still and keep vouching for a
    snapshot the tool is no longer reading."""
    encoding = VENDORED_FILES[0]
    vendor = ROOT / "src" / "ctdl_validate" / "vendor"
    real = (vendor / encoding).read_bytes()

    def altered(relpath: str) -> bytes:
        data = (vendor / relpath).read_bytes()
        return data + b"\n" if relpath == encoding else data

    digests.cache_clear()
    try:
        monkeypatch.setattr(snapshot, "_read", altered)
        moved = digests()[encoding]
    finally:
        digests.cache_clear()
        monkeypatch.undo()
    assert moved == hashlib.sha256(real + b"\n").hexdigest()
    assert moved != EXPECTED_VENDOR_HASHES[encoding]
    assert digests()[encoding] == EXPECTED_VENDOR_HASHES[encoding]


# -- merging: one file for a publication set of many payloads -------------------


def _log(name: str) -> dict[str, Any]:
    return _sarif(name)


def test_a_merged_log_validates_against_the_sarif_schema() -> None:
    merged = json.loads(
        merge_logs(
            [
                _log("bug_class_250_bare_uuid_for_ctid.json"),
                _log("bug_class_252_wrong_framework_identifier.json"),
            ]
        )
    )
    Draft4Validator(SCHEMA).validate(merged)
    assert len(merged["runs"]) == 1


def test_merging_keeps_every_result_and_sums_every_summary() -> None:
    first = _log("bug_class_250_bare_uuid_for_ctid.json")
    second = _log("bug_class_252_wrong_framework_identifier.json")
    merged = json.loads(merge_logs([first, second]))
    run = merged["runs"][0]
    assert len(run["results"]) == len(first["runs"][0]["results"]) + len(
        second["runs"][0]["results"]
    )
    for severity, total in run["properties"]["summary"].items():
        assert total == (
            first["runs"][0]["properties"]["summary"][severity]
            + second["runs"][0]["properties"]["summary"][severity]
        )
    assert run["properties"]["documents"] == [
        first["runs"][0]["properties"]["document"],
        second["runs"][0]["properties"]["document"],
    ]


def test_every_merged_result_still_points_at_its_own_rule() -> None:
    """Re-indexing is the one thing a merge can get quietly wrong: a ruleIndex
    off by one attributes a finding to another rule's citation."""
    merged = json.loads(
        merge_logs(
            [
                _log("bug_class_250_bare_uuid_for_ctid.json"),
                _log("bug_class_252_wrong_framework_identifier.json"),
            ]
        )
    )
    run = merged["runs"][0]
    rules = run["tool"]["driver"]["rules"]
    assert rules
    for result in run["results"]:
        assert rules[result["ruleIndex"]]["id"] == result["ruleId"]


def test_a_merged_rule_keeps_every_source_both_documents_cited() -> None:
    first = _log("bug_class_250_bare_uuid_for_ctid.json")
    second = _log("bug_class_252_wrong_framework_identifier.json")
    merged = json.loads(merge_logs([first, second]))
    sources: dict[str, set[tuple[str, str]]] = {}
    for log in (first, second):
        for rule in log["runs"][0]["tool"]["driver"]["rules"]:
            cited = sources.setdefault(rule["id"], set())
            for source in rule["properties"]["sources"]:
                cited.add((source["url"], source["retrieved"]))
    for rule in merged["runs"][0]["tool"]["driver"]["rules"]:
        got = {(s["url"], s["retrieved"]) for s in rule["properties"]["sources"]}
        assert got == sources[rule["id"]]
        urls = {url for url, _ in got}
        expected = len(urls) == 1 and next(iter(urls)).startswith("https://")
        assert ("helpUri" in rule) == expected


def test_merging_one_log_is_that_log_with_its_document_listed() -> None:
    only = _log("bug_class_250_bare_uuid_for_ctid.json")
    merged = json.loads(merge_logs([only]))
    assert merged["runs"][0]["results"] == only["runs"][0]["results"]
    assert merged["runs"][0]["tool"]["driver"] == only["runs"][0]["tool"]["driver"]


def test_merging_across_two_snapshots_is_refused_rather_than_attributed() -> None:
    """Two logs from different vendored snapshots describe two different
    states of a vocabulary that moves. Merging them silently would file one
    snapshot's verdicts under the other's digests."""
    first = _log("bug_class_250_bare_uuid_for_ctid.json")
    second = copy.deepcopy(first)
    files = second["runs"][0]["tool"]["driver"]["properties"]["vendoredSnapshot"]["files"]
    files[VENDORED_FILES[0]] = "0" * 64
    with pytest.raises(ValueError, match="one vendored snapshot"):
        merge_logs([first, second])


def test_merging_refuses_a_log_that_is_not_a_single_sarif_2_1_0_run() -> None:
    good = _log("bug_class_250_bare_uuid_for_ctid.json")
    with pytest.raises(ValueError, match="no logs to merge"):
        merge_logs([])
    with pytest.raises(ValueError, match="SARIF 2.1.0"):
        merge_logs([{**good, "version": "2.0.0"}])
    with pytest.raises(ValueError, match="exactly one run"):
        merge_logs([{**good, "runs": good["runs"] + good["runs"]}])
    with pytest.raises(ValueError, match="SARIF 2.1.0"):
        merge_logs(["not a log"])


# -- the CLI --------------------------------------------------------------------


def test_the_cli_exit_code_is_the_same_as_for_json(capsys: pytest.CaptureFixture[str]) -> None:
    broken = str(fixture_path("bug_class_250_bare_uuid_for_ctid.json"))
    assert main([broken, "--format", "sarif"]) == 1
    log = json.loads(capsys.readouterr().out)
    assert log["version"] == "2.1.0"
    clean = str(fixture_path("clean_framework.json"))
    assert main([clean, "--format", "sarif"]) == 0
    assert json.loads(capsys.readouterr().out)["runs"][0]["properties"]["summary"]["ERROR"] == 0
