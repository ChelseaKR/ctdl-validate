"""CLI behavior: exit codes, formats, bad input."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctdl_validate.cli import main

from .conftest import fixture_path


def test_clean_payload_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(fixture_path("clean_framework.json"))]) == 0
    out = capsys.readouterr().out
    assert "0 finding(s)" in out


def test_error_findings_exit_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(fixture_path("bug_class_250_bare_uuid_for_ctid.json"))]) == 1
    out = capsys.readouterr().out
    assert "CTID_BARE_UUID" in out
    assert "rule:" in out and "source:" in out


def test_unverifiable_only_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    # UNVERIFIABLE is never rendered as a pass or a fail; it does not gate.
    assert main([str(fixture_path("external_reference.json"))]) == 0
    out = capsys.readouterr().out
    assert "UNVERIFIABLE" in out


def test_warnings_do_not_gate(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(fixture_path("ctid_warnings.json"))]) == 0
    out = capsys.readouterr().out
    assert "CTID_UPPERCASE" in out


def test_json_format_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    fixture = str(fixture_path("bug_class_252_wrong_framework_identifier.json"))
    code = main([fixture, "--format", "json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"]["name"] == "ctdl-validate"
    assert payload["summary"]["ERROR"] == 1
    codes = {f["code"] for f in payload["findings"]}
    assert {"RANGE_VIOLATION", "ISPARTOF_FRAMEWORK_MISMATCH", "REF_OUTSIDE_PAYLOAD"} <= codes
    for finding in payload["findings"]:
        assert finding["rule"]["citation"]
        assert finding["rule"]["url"]


def test_missing_file_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["/nonexistent/nope.json"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_invalid_json_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([str(bad)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_non_entity_json_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scalar = tmp_path / "scalar.json"
    scalar.write_text('"just a string"', encoding="utf-8")
    assert main([str(scalar)]) == 2
    assert "expected" in capsys.readouterr().err
