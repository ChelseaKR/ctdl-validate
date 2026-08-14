"""The extract subcommand: dispatch, formats, exit codes, and the pipeline."""

from __future__ import annotations

import json
from typing import Any

import pytest

from ctdl_validate.cli import main

from .conftest import ALLOW_ALL, Route, fixture_path, load_page, page_path, robots, serve

SOURCE = "https://example.edu/courses/weld-101"


def extract_args(page: str, *extra: str) -> list[str]:
    return ["extract", SOURCE, "--from-file", str(page_path(page)), *extra]


def test_validation_still_runs_when_the_first_argument_is_a_file() -> None:
    assert main([str(fixture_path("clean_framework.json"))]) == 0


def test_a_page_with_entities_exits_zero_and_reports() -> None:
    assert main(extract_args("course_jsonld.html")) == 0


def test_a_page_with_no_extractable_entities_exits_one() -> None:
    # Not an error: the page is fine, it simply publishes no structured data.
    assert main(extract_args("no_markup.html")) == 1


def test_the_text_report_names_the_source_and_every_note(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(extract_args("course_jsonld.html"))
    out = capsys.readouterr().out
    assert SOURCE in out
    assert "CLASS_NOT_MAPPED" in out
    assert "rule:" in out and "source:" in out
    assert "2 CTDL entity(ies) extracted" in out


def test_jsonld_format_puts_the_document_on_stdout_and_the_report_on_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(extract_args("course_jsonld.html", "--format", "jsonld"))
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["@context"] == "https://credreg.net/ctdl/schema/context/json"
    assert "CLASS_NOT_MAPPED" in captured.err, "notes are never dropped, only moved"


def test_json_format_is_one_machine_readable_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(extract_args("course_jsonld.html", "--format", "json"))
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == {
        "name": "ctdl-validate",
        "version": payload["tool"]["version"],
        "command": "extract",
    }
    assert payload["fetch"]["source"] == "file"
    assert payload["summary"]["entities"] == 2
    assert [block["format"] for block in payload["blocks"]] == ["json-ld"]
    for note in payload["notes"]:
        assert note["rule"]["citation"] and note["rule"]["url"]


def test_the_pipeline_runs_extraction_and_validation_in_one_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Every term here mapped through a declared equivalence, and the result
    # still violates CTDL: schema.org's address points at a PostalAddress,
    # while ceterms:address declares its range as ceterms:Place. A faithful
    # extract can be an invalid payload, which is the whole argument for
    # validating one before publishing it.
    code = main(extract_args("organization_microdata.html", "--validate"))
    out = capsys.readouterr().out
    assert "validation of the extracted document:" in out
    assert "RANGE_VIOLATION" in out
    assert code == 1


def test_a_clean_extract_passes_validation() -> None:
    assert main(extract_args("ctdl_jsonld.html", "--validate")) == 0


def test_a_pathologically_nested_page_is_refused_not_absorbed(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    page = tmp_path / "deep.html"
    page.write_text("<div>" * 5000 + "x" + "</div>" * 5000, encoding="utf-8")
    assert main(["extract", SOURCE, "--from-file", str(page)]) == 2
    assert "nesting deeper than" in capsys.readouterr().err


def test_a_missing_saved_page_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extract", SOURCE, "--from-file", "/nonexistent/page.html"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_a_disallowed_page_exits_two_and_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    rules = "User-agent: *\nDisallow: /\n"
    with serve({"/robots.txt": robots(rules)}) as site:
        code = main(["extract", f"{site.base}/programs/x", "--min-interval", "0"])
    assert code == 2
    assert "disallowed by" in capsys.readouterr().err


def test_a_real_fetch_reports_the_transport_it_used(capsys: pytest.CaptureFixture[str]) -> None:
    page = load_page("course_jsonld.html").encode("utf-8")
    routes = {"/robots.txt": ALLOW_ALL, "/course": Route(body=page)}
    with serve(routes) as site:
        code = main(["extract", f"{site.base}/course", "--format", "json", "--min-interval", "0"])
        payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["fetch"]["status"] == 200
    assert payload["fetch"]["robots"].startswith("read from")
    assert payload["fetch"]["bytes"] == len(page)


def test_help_for_the_subcommand_is_its_own(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["extract", "--help"])
    assert exit_info.value.code == 0
    assert "robots.txt" in capsys.readouterr().out
