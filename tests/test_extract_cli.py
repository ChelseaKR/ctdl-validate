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


# --- saved pages are decoded the way fetched pages are (#59) ---------------
#
# --from-file existed to make a run reproducible offline: "same page bytes,
# same output, byte for byte" (README). It hard-coded UTF-8 while the fetch
# path honoured the markup's declared charset, so the two paths disagreed on
# the same bytes, and a non-UTF-8 saved page raised UnicodeDecodeError -- a
# ValueError, caught by neither handler -- and exited 1, the code reserved for
# "read fine, publishes no CTDL".


def _page_bytes(name: str, charset: str, encoding: str) -> bytes:
    """A minimal JSON-LD course page declaring ``charset``, stored as ``encoding``."""
    return (
        '<!doctype html>\n<html lang="fr">\n<head>\n'
        f'<meta charset="{charset}">\n'
        "<title>Soudage</title>\n"
        '<script type="application/ld+json">\n'
        '{"@context": "https://schema.org", "@type": "Course",'
        ' "@id": "https://example.edu/courses/weld-101",'
        f' "name": "{name}", "courseCode": "WELD-101"}}\n'
        "</script>\n</head>\n<body></body>\n</html>\n"
    ).encode(encoding)


def _run_json(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, Any]:
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_a_non_utf8_saved_page_is_read_rather_than_crashing(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "page_cp1252.html"
    saved.write_bytes(_page_bytes("Collège Example Welding", "windows-1252", "windows-1252"))

    code, payload = _run_json(
        ["extract", SOURCE, "--from-file", str(saved), "--format", "json"], capsys
    )

    assert code == 0, "the page is readable and carries a course; it is not a failed read"
    assert payload["fetch"]["encoding"] == "windows-1252"
    assert payload["fetch"]["bytes"] == len(saved.read_bytes()), "bytes read, not bytes re-encoded"
    names = json.dumps(payload["document"], ensure_ascii=False)
    assert "Collège" in names, "the accented byte survived the round trip"


def test_a_saved_page_whose_bytes_defy_its_declared_charset_is_labelled_not_lost(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    # Bytes are windows-1252 but the page claims UTF-8, so the declared codec
    # cannot decode them. The fetch path replaces and says so; so must this one.
    saved = tmp_path / "page_mislabelled.html"
    saved.write_bytes(_page_bytes("Collège Example Welding", "utf-8", "windows-1252"))

    code, payload = _run_json(
        ["extract", SOURCE, "--from-file", str(saved), "--format", "json"], capsys
    )

    assert code != 2, "the page was read; only some bytes were unrepresentable"
    assert payload["fetch"]["encoding"] == "utf-8 (undecodable, replaced)"


def test_an_unreadable_saved_page_exits_two_and_never_traces_back(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    # A directory is the readable stand-in for every OSError: exit 2 ("nothing
    # could be read"), never exit 1 ("read fine, no CTDL"), never a traceback.
    unreadable = tmp_path / "a_directory.html"
    unreadable.mkdir()
    assert main(["extract", SOURCE, "--from-file", str(unreadable)]) == 2
    assert "cannot read" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("charset", "encoding"),
    [
        ("windows-1252", "windows-1252"),  # declared charset matches the bytes
        ("utf-8", "utf-8"),  # the ordinary case
        ("windows-1252", "utf-8"),  # declared charset disagrees with the bytes
        ("utf-8", "windows-1252"),  # ... and the other way, so decoding fails
    ],
)
def test_from_file_and_fetch_produce_the_same_document_for_the_same_bytes(
    charset: str, encoding: str, tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """README's "same page bytes, same output, byte for byte" guarantee, pinned.

    Whether the declared charset is right, wrong, or unusable, the two paths
    must agree -- the point is parity, not that either answer is correct.
    """
    body = _page_bytes("Collège Example Welding", charset, encoding)
    saved = tmp_path / "saved.html"
    saved.write_bytes(body)

    # No charset on the response, so the markup's own declaration decides on
    # both paths; that is the only condition under which they can agree.
    routes = {"/robots.txt": ALLOW_ALL, "/course": Route(body=body, content_type="text/html")}
    with serve(routes) as site:
        url = f"{site.base}/course"
        fetched_code, fetched = _run_json(
            ["extract", url, "--format", "json", "--min-interval", "0"], capsys
        )
        saved_code, from_file = _run_json(
            ["extract", url, "--from-file", str(saved), "--format", "json"], capsys
        )

    assert fetched_code == saved_code
    assert from_file["document"] == fetched["document"]
    assert from_file["blocks"] == fetched["blocks"]
    assert from_file["notes"] == fetched["notes"]
    assert from_file["fetch"]["encoding"] == fetched["fetch"]["encoding"]
    assert from_file["fetch"]["bytes"] == fetched["fetch"]["bytes"] == len(body)
