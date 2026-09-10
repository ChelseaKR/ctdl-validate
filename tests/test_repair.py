"""``repair --draft``: what it writes, what it refuses, and what it will not guess.

``--suggest`` names a correction. This applies the ones the payload determines,
to a copy, and re-validates the copy. The half worth testing hardest is the
same half as everywhere else in this tool: what it declines to do. A finding
reaches an operation only when the run derived exactly one candidate *and*
exactly one place in the source carries the reported value, and every finding
that fails either condition is printed with the reason rather than dropped.

Issue #64's four acceptance cases are named individually below, because three
of the four are about a refusal and only one is about a repair.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest

from ctdl_validate.cli import main
from ctdl_validate.findings import Finding, Rule, Severity, Suggestion
from ctdl_validate.repair import (
    NO_CANDIDATE,
    NOT_IN_THE_SOURCE,
    SEVERAL_CANDIDATES,
    Draft,
    Located,
    Operation,
    apply_patch,
    draft,
    locate,
    operations_for,
    positions,
)
from ctdl_validate.schema import load_schema
from ctdl_validate.validator import build_session, validate

from .conftest import FIXTURES, fixture_path, load_fixture

RESOLVE = FIXTURES / "resolve"


def _repair(tmp_path: Path, name: str, *extra: str) -> tuple[int, Path, Any]:
    """Run the verb through the real CLI dispatch and return the written copy."""
    out = tmp_path / "draft.json"
    code = main(["repair", str(fixture_path(name)), "--draft", "--out", str(out), *extra])
    written = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    return code, out, written


def _finding(*, entity: str, prop: str, value: str) -> Finding:
    """A finding with the three fields ``locate`` matches on, and nothing real.

    Built rather than taken out of a run: the point is to drive ``locate``'s
    matching, and a finding scavenged from a validation would tie these
    assertions to whichever rule happened to fire on the fixture.
    """
    return Finding(
        code="A_CODE",
        severity=Severity.WARNING,
        entity=entity,
        prop=prop,
        value=value,
        message="not read by locate",
        rule=Rule(citation="a rule", url="https://example.invalid/", retrieved="2026-01-01"),
    )


def _drafted(name: str) -> Draft:
    result, _ = draft(load_fixture(name))
    return result


# -- issue #64's acceptance cases ---------------------------------------------


def test_the_uppercase_ctid_is_resolved_with_nothing_introduced(tmp_path: Path) -> None:
    """ "`ctid_warnings.json` … `repair --draft` on it resolves `CTID_UPPERCASE`
    with 0 introduced.\""""
    code, _, written = _repair(tmp_path, "ctid_warnings.json")
    assert code == 0
    result = _drafted("ctid_warnings.json")
    assert [f.code for f in result.resolved] == ["CTID_UPPERCASE"]
    assert result.introduced == ()
    assert [op.pointer for op in result.operations] == ["/@graph/0/ceterms:ctid"]
    assert written["@graph"][0]["ceterms:ctid"] == "ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4"


def test_a_bare_uuid_produces_no_operation_and_says_why(tmp_path: Path) -> None:
    """ "A bare UUID produces no suggestion." It must also produce no *patch*:
    prefixing `ce-` would assert that a generated UUID names a Registry
    resource, which is the claim the finding disputes."""
    code, _, written = _repair(tmp_path, "bug_class_250_bare_uuid_for_ctid.json")
    assert code == 0
    assert written == load_fixture("bug_class_250_bare_uuid_for_ctid.json"), (
        "nothing was determined here, so the draft must be the document"
    )
    result = _drafted("bug_class_250_bare_uuid_for_ctid.json")
    assert result.operations == ()
    assert {skip.finding.code for skip in result.skipped} == {
        "CTID_BARE_UUID",
        "REGISTRY_URI_MALFORMED",
    }
    assert {skip.reason for skip in result.skipped} == {NO_CANDIDATE}


def test_a_patch_that_introduces_a_finding_says_so_and_is_still_written(
    tmp_path: Path,
) -> None:
    """ "A patch that would introduce a finding is reported as such and the file
    still written with the counts."

    The fixture is the honest case rather than a contrived one. A
    ``ceterms:ownedBy`` written as a bare CTID is `REF_BARE_CTID`, and the
    correction the payload determines is the `@id` of the entity that declares
    that CTID. Once the reference resolves, the range check can see what it
    points at -- a `ceterms:Certification` where `ceterms:ownedBy` requires an
    organization -- and raises the ERROR the unresolvable reference had been
    hiding. The re-spelling is right and the document is worse by the exit
    code, which is exactly why this verb writes a draft.
    """
    code, _, written = _repair(tmp_path, "repair_introduces_a_range_violation.json")
    assert code == 0, "an introduced finding is a report, not a refusal to write"
    assert written is not None and written != load_fixture(
        "repair_introduces_a_range_violation.json"
    )
    result = _drafted("repair_introduces_a_range_violation.json")
    assert [f.code for f in result.resolved] == ["REF_BARE_CTID"]
    assert [f.code for f in result.introduced] == ["RANGE_VIOLATION"]
    assert result.as_dict()["counts"] == {
        "operations": 1,
        "skipped": 0,
        "resolved": 1,
        "untouched": 0,
        "introduced": 1,
    }


def test_the_default_command_is_untouched_by_this_verb(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "Default output is byte-identical to today." A new verb dispatched by
    name must not move one byte of the command that has no verb."""
    main([str(fixture_path("ctid_warnings.json"))])
    without = capsys.readouterr().out
    _repair(tmp_path, "ctid_warnings.json")
    capsys.readouterr()
    main([str(fixture_path("ctid_warnings.json"))])
    assert capsys.readouterr().out == without


# -- the input is never written -----------------------------------------------


def test_the_input_file_is_not_touched(tmp_path: Path) -> None:
    source = fixture_path("ctid_warnings.json")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    _repair(tmp_path, "ctid_warnings.json")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_writing_over_the_input_is_refused_before_anything_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The input is a *copy* of the fixture, not the fixture.

    That is not fastidiousness. Running the negative control for this refusal
    -- deleting the ``target == source`` comparison -- made an earlier version
    of this test write the draft over ``tests/fixtures/ctid_warnings.json``
    itself, lower-casing the CTID that four other tests in this file depend on
    being upper case. The control fired correctly on this test and then
    reddened four more for a reason that had nothing to do with the sabotage,
    and `git checkout HEAD -- <the module>` restored the module and not the
    fixture. A test that proves a write-guard must not be the thing that
    exercises the write on a tracked file.
    """
    source = tmp_path / "payload.json"
    source.write_bytes(fixture_path("ctid_warnings.json").read_bytes())
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    assert main(["repair", str(source), "--draft", "--out", str(source)]) == 2
    assert "the input" in capsys.readouterr().err
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_writing_over_a_resolve_path_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    supplied = RESOLVE / "owner_organization.json"
    before = hashlib.sha256(supplied.read_bytes()).hexdigest()
    code = main(
        [
            "repair",
            str(fixture_path("external_reference.json")),
            "--draft",
            "--out",
            str(supplied),
            "--resolve",
            str(supplied),
        ]
    )
    assert code == 2
    assert "--resolve" in capsys.readouterr().err
    assert hashlib.sha256(supplied.read_bytes()).hexdigest() == before


def test_the_refusal_compares_paths_and_not_strings(tmp_path: Path) -> None:
    """``./x.json`` and ``x.json`` are one file on disk and must be one here."""
    source = tmp_path / "payload.json"
    source.write_text(json.dumps(load_fixture("ctid_warnings.json")), encoding="utf-8")
    spelled_differently = tmp_path / "." / "payload.json"
    assert main(["repair", str(source), "--draft", "--out", str(spelled_differently)]) == 2


# -- locating a value, which is where a guess would enter ---------------------


def test_a_pointer_is_produced_for_every_shape_a_value_takes() -> None:
    schema = load_schema()
    document = {
        "@id": "https://credentialengineregistry.org/graph/ce-1",
        "@graph": [
            {
                "@id": "urn:a",
                "ceterms:name": "scalar",
                "ceterms:keyword": ["first", "second"],
                "ceterms:ownedBy": {"@id": "urn:owner"},
                "ceterms:description": {"@value": "typed"},
            }
        ],
    }
    pointers = {(p.prop, p.value): p.pointer for p in positions(document, schema)}
    assert pointers[("ceterms:name", "scalar")] == "/@graph/0/ceterms:name"
    assert pointers[("ceterms:keyword", "second")] == "/@graph/0/ceterms:keyword/1"
    assert pointers[("ceterms:ownedBy", "urn:owner")] == "/@graph/0/ceterms:ownedBy/@id"
    assert pointers[("ceterms:description", "typed")] == "/@graph/0/ceterms:description/@value"
    envelope = [p for p in positions(document, schema) if p.prop == "@id"]
    assert [p.pointer for p in envelope] == ["/@id"], (
        "the @graph envelope's own @id is where CTID_URI_MISMATCH lands on a graph URI, "
        "and it is not a node, so the entity walk never reaches it"
    )


def test_a_key_needing_escaping_is_escaped() -> None:
    schema = load_schema()
    document = {"@id": "urn:x", "weird/key": "v", "tilde~key": "w"}
    pointers = {p.value: p.pointer for p in positions(document, schema)}
    assert pointers["v"] == "/weird~1key"
    assert pointers["w"] == "/tilde~0key"


def test_a_single_entity_with_no_graph_is_not_indexed() -> None:
    """``parse_document`` labels it ``$``, not ``$[0]``, and the pointer has to
    agree or every correction in a single-entity document is skipped."""
    located = positions({"ceterms:name": "only"}, load_schema())
    assert [position.pointer for position in located] == ["/ceterms:name"]
    assert [position.label for position in located] == ["$"]


def test_a_value_written_twice_under_one_identifier_is_declined(tmp_path: Path) -> None:
    """The refusal this module adds on top of ``suggest``'s.

    An ``@id`` declared by two objects is a defect this tool *reports* rather
    than refuses to read, so a finding against that identifier can name a value
    that is written in two places. Patching one is a guess about which the
    finding meant.
    """
    document = {
        "@context": "https://credreg.net/ctdl/schema/context/json",
        "@graph": [
            {
                "@id": "https://credentialengineregistry.org/resources/ce-11111111-1111-4111-8111-111111111111",
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-11111111111A",
            },
            {
                "@id": "https://credentialengineregistry.org/resources/ce-11111111-1111-4111-8111-111111111111",
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-11111111111A",
            },
        ],
    }
    result, patched = draft(document)
    assert patched == document, "nothing may be written when the position is a guess"
    declined = [skip for skip in result.skipped if skip.finding.code == "CTID_UPPERCASE"]
    assert declined, "the uppercase CTID should have been a candidate and then declined"
    assert "2 positions" in declined[0].reason
    assert result.operations == ()


def test_locate_matches_on_all_three_identity_fields() -> None:
    """One string written under two properties must not be patched at the wrong one."""
    document = {"@id": "urn:a", "ceterms:name": "same", "ceterms:description": "same"}
    located = positions(document, load_schema())
    named = _finding(entity="urn:a", prop="ceterms:name", value="same")
    assert locate(named, located) == ["/ceterms:name"]
    described = _finding(entity="urn:a", prop="ceterms:description", value="same")
    assert locate(described, located) == ["/ceterms:description"]
    elsewhere = _finding(entity="urn:b", prop="ceterms:name", value="same")
    assert locate(elsewhere, located) == []


def test_a_value_the_source_does_not_carry_is_declined() -> None:
    located = positions({"@id": "urn:a", "ceterms:name": "written"}, load_schema())
    absent = _finding(entity="urn:a", prop="ceterms:name", value="never written")
    assert locate(absent, located) == []


def test_a_non_string_value_is_never_matched() -> None:
    """A finding renders a non-string value through ``repr``; matching that
    rendering against the object it came from would be comparing a string to a
    number and calling the result a location."""
    located = positions({"@id": "urn:a", "ceterms:name": 7}, load_schema())
    assert [position.value for position in located] == [7]
    numeric = _finding(entity="urn:a", prop="ceterms:name", value="7")
    assert locate(numeric, located) == []


# -- the skips are data, not omissions ----------------------------------------


def test_every_finding_is_either_applied_or_skipped_with_a_reason() -> None:
    """No finding may fall out of the report between the two lists."""
    for name in (
        "ctid_warnings.json",
        "bug_class_250_bare_uuid_for_ctid.json",
        "bug_class_252_wrong_framework_identifier.json",
        "domain_violation.json",
        "inverse_mismatch.json",
        "external_reference.json",
        "unresolved_bnode.json",
    ):
        result = _drafted(name)
        accounted = len(result.operations) + len(result.skipped)
        assert accounted == len(result.before), (
            f"{name}: {len(result.before)} findings, {accounted} accounted for"
        )
        assert all(skip.reason for skip in result.skipped)


def test_two_candidates_are_declined_rather_than_picked() -> None:
    """``suggest._sole`` refuses to offer two today, so this drives the guard
    directly. A future suggester that offers a pair must not have one taken."""
    document = load_fixture("ctid_warnings.json")
    session = build_session(document)
    findings = validate(session, suggest=True)
    target = next(f for f in findings if f.code == "CTID_UPPERCASE")
    two = dataclasses.replace(
        target,
        suggestions=(
            Suggestion(value="ce-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", difference="one"),
            Suggestion(value="ce-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", difference="two"),
        ),
    )
    operations, skipped = operations_for(session, document, [two])
    assert operations == ()
    assert [skip.reason for skip in skipped] == [SEVERAL_CANDIDATES]


def test_the_reason_vocabulary_is_the_one_the_module_declares() -> None:
    """Each reason is a named constant so a skip cannot be given an ad-hoc
    sentence that nothing else in the suite has ever read."""
    reasons = {NO_CANDIDATE, SEVERAL_CANDIDATES, NOT_IN_THE_SOURCE}
    seen = {
        skip.reason
        for name in ("bug_class_250_bare_uuid_for_ctid.json", "domain_violation.json")
        for skip in _drafted(name).skipped
    }
    assert seen <= reasons, f"a skip carries an unnamed reason: {sorted(seen - reasons)}"
    assert seen, "no skip was produced, so this asserts nothing"


# -- properties of the output --------------------------------------------------


def test_the_draft_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    for out in (first, second):
        main(
            [
                "repair",
                str(fixture_path("bug_class_252_wrong_framework_identifier.json")),
                "--draft",
                "--out",
                str(out),
            ]
        )
    assert first.read_bytes() == second.read_bytes()


def test_the_draft_is_byte_identical_across_processes(tmp_path: Path) -> None:
    """Two runs in one interpreter share every cache and every set's iteration
    order. A determinism claim has to cross a process boundary."""
    outputs = []
    for index, seed in enumerate(("0", "1")):
        out = tmp_path / f"p{index}.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ctdl_validate",
                "repair",
                str(fixture_path("bug_class_252_wrong_framework_identifier.json")),
                "--draft",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            cwd=Path(__file__).resolve().parent.parent,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1]


def test_the_patch_file_is_the_operations_the_report_names(tmp_path: Path) -> None:
    out = tmp_path / "draft.json"
    patch = tmp_path / "patch.json"
    main(
        [
            "repair",
            str(fixture_path("ctid_warnings.json")),
            "--draft",
            "--out",
            str(out),
            "--patch-out",
            str(patch),
        ]
    )
    operations = json.loads(patch.read_text(encoding="utf-8"))
    assert operations == [
        {
            "op": "replace",
            "path": "/@graph/0/ceterms:ctid",
            "value": "ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4",
        }
    ]
    assert {op["op"] for op in operations} == {"replace"}, (
        "replace only: these codes are re-spellings, so a patch that added or removed "
        "anything would be changing the document's shape rather than its spelling"
    )


def test_applying_the_patch_reproduces_the_written_draft(tmp_path: Path) -> None:
    """The patch and the copy are two statements about one change."""
    document = load_fixture("bug_class_252_wrong_framework_identifier.json")
    result, patched = draft(document)
    assert apply_patch(document, result.operations) == patched
    assert document == load_fixture("bug_class_252_wrong_framework_identifier.json"), (
        "apply_patch must not write through to its argument"
    )


def test_the_json_report_carries_both_lists_and_the_counts(tmp_path: Path) -> None:
    out = tmp_path / "draft.json"
    code = main(
        [
            "repair",
            str(fixture_path("ctid_warnings.json")),
            "--draft",
            "--out",
            str(out),
            "--format",
            "json",
        ]
    )
    assert code == 0


# -- refusals of the command itself -------------------------------------------


def test_draft_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    """The word is the contract. Without it there is no mode at all, so no
    future mode can become the default by omission."""
    with pytest.raises(SystemExit) as exit_info:
        main(["repair", str(fixture_path("ctid_warnings.json")), "--out", "/dev/null"])
    assert exit_info.value.code == 2
    assert "--draft" in capsys.readouterr().err


def test_an_unreadable_input_is_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["repair", str(tmp_path / "absent.json"), "--draft", "--out", str(tmp_path / "o")])
        == 2
    )
    assert "cannot read" in capsys.readouterr().err


def test_a_document_that_is_not_json_is_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "bad.json"
    source.write_text("{not json", encoding="utf-8")
    assert main(["repair", str(source), "--draft", "--out", str(tmp_path / "o.json")]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_a_shape_the_tool_does_not_read_is_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "scalar.json"
    source.write_text('"just a string"', encoding="utf-8")
    assert main(["repair", str(source), "--draft", "--out", str(tmp_path / "o.json")]) == 2
    assert capsys.readouterr().err


# -- the posture the default path has -----------------------------------------


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("this code path must not open a socket")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.mark.usefixtures("no_network")
def test_the_repair_verb_opens_no_socket(tmp_path: Path) -> None:
    assert _repair(tmp_path, "bug_class_252_wrong_framework_identifier.json")[0] == 0


def test_running_repair_loads_no_fetching_code(tmp_path: Path) -> None:
    """The default path does not import the module that fetches, and neither
    does this one. Checked in a fresh interpreter, because the suite has
    certainly imported it by now."""
    out = tmp_path / "draft.json"
    program = (
        "import sys;"
        "from ctdl_validate.cli import main;"
        f"main(['repair', {str(fixture_path('ctid_warnings.json'))!r},"
        f" '--draft', '--out', {str(out)!r}]);"
        "print('extract' if 'ctdl_validate.extract.fetch' in sys.modules else 'clean')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().endswith("clean")


def test_located_is_a_value_object() -> None:
    """Frozen, so a locator cannot be edited between being found and being used."""
    located = Located(pointer="/a", label="urn:a", prop="ceterms:name", value="v")
    with pytest.raises(Exception, match="cannot assign|frozen"):
        located.pointer = "/b"  # type: ignore[misc]


# -- the shapes the coverage report named ------------------------------------
#
# Every test below exists because `pytest --cov` reported the line it drives as
# unexecuted on the first complete run of this module. Three of the six were
# real gaps rather than untested refusals: a nested inline object, a bare-array
# document, and a patch to an element of a list are all shapes `graph.py`
# handles and this module had never been run against. A locator that disagrees
# with the walk fails silently -- every finding is skipped as "not in the
# source" and the draft is the document -- so an untested shape here is an
# untested silence.


def test_a_value_inside_a_nested_inline_object_is_located() -> None:
    """`graph.walk` gives a nested object its own node at
    ``$.@graph[0].<prop>[<i>]``, and a finding against it carries that path as
    its entity. The pointer has to reach the same place by the JSON route."""
    document = {
        "@graph": [
            {
                "@id": "urn:outer",
                "ceterms:address": [{"ceterms:streetAddress": "1 Example Way"}],
            }
        ]
    }
    located = positions(document, load_schema())
    nested = [p for p in located if p.prop == "ceterms:streetAddress"]
    assert [p.pointer for p in nested] == ["/@graph/0/ceterms:address/0/ceterms:streetAddress"]
    assert [p.label for p in nested] == ["$.@graph[0].ceterms:address[0]"], (
        "the label must be the path graph.py builds, or a finding against this nested "
        "entity matches nothing and is skipped as if the value were absent"
    )


def test_the_label_of_a_nested_object_that_carries_an_id_is_that_id() -> None:
    document = {
        "@graph": [
            {
                "@id": "urn:outer",
                "ceterms:address": {"@id": "urn:inner", "ceterms:streetAddress": "1 Example Way"},
            }
        ]
    }
    located = positions(document, load_schema())
    nested = [p for p in located if p.prop == "ceterms:streetAddress"]
    assert [(p.label, p.pointer) for p in nested] == [
        ("urn:inner", "/@graph/0/ceterms:address/ceterms:streetAddress")
    ]


def test_a_bare_array_document_is_indexed() -> None:
    """The third shape ``parse_document`` accepts. Two entities in a bare array
    are ``$[0]`` and ``$[1]``, and their pointers are ``/0`` and ``/1``."""
    document = [{"ceterms:name": "first"}, {"ceterms:name": "second"}]
    located = positions(document, load_schema())
    assert [(p.label, p.pointer) for p in located] == [
        ("$[0]", "/0/ceterms:name"),
        ("$[1]", "/1/ceterms:name"),
    ]


def test_a_patch_replaces_an_element_of_a_list_and_leaves_its_siblings() -> None:
    """The most dangerous line the coverage report named. A multi-valued
    property is an array, the pointer's last token is an integer, and writing
    ``target["1"]`` instead of ``target[1]`` would either raise or add a key."""
    document = {"@graph": [{"@id": "urn:a", "ceterms:keyword": ["first", "second", "third"]}]}
    operation = Operation(
        pointer="/@graph/0/ceterms:keyword/1",
        value="replaced",
        finding=_finding(entity="urn:a", prop="ceterms:keyword", value="second"),
    )
    patched = apply_patch(document, [operation])
    assert patched["@graph"][0]["ceterms:keyword"] == ["first", "replaced", "third"]
    assert document["@graph"][0]["ceterms:keyword"] == ["first", "second", "third"]


def test_a_patch_reaches_a_value_inside_a_nested_object() -> None:
    document = {"@graph": [{"@id": "urn:a", "ceterms:address": [{"ceterms:postalCode": "0"}]}]}
    operation = Operation(
        pointer="/@graph/0/ceterms:address/0/ceterms:postalCode",
        value="95814",
        finding=_finding(entity="x", prop="ceterms:postalCode", value="0"),
    )
    assert apply_patch(document, [operation])["@graph"][0]["ceterms:address"][0] == {
        "ceterms:postalCode": "95814"
    }


def test_a_finding_whose_value_is_not_in_the_source_is_skipped_with_that_reason() -> None:
    """`NOT_IN_THE_SOURCE` had a unit test on ``locate`` and had never been
    produced by ``operations_for``, so nothing proved the reason reaches a
    report."""
    document = load_fixture("ctid_warnings.json")
    session = build_session(document)
    target = next(f for f in validate(session, suggest=True) if f.code == "CTID_UPPERCASE")
    moved = dataclasses.replace(target, value="a value this document does not carry")
    operations, skipped = operations_for(session, document, [moved])
    assert operations == ()
    assert [skip.reason for skip in skipped] == [NOT_IN_THE_SOURCE]


def test_a_resolve_path_that_is_not_the_output_is_not_refused(tmp_path: Path) -> None:
    """The loop over ``--resolve`` has to be able to *not* match, or the
    refusal is a rule that fires on every supplied document."""
    out = tmp_path / "draft.json"
    code = main(
        [
            "repair",
            str(fixture_path("external_reference.json")),
            "--draft",
            "--out",
            str(out),
            "--resolve",
            str(RESOLVE / "owner_organization.json"),
        ]
    )
    assert code == 0
    assert out.exists()


def test_a_draft_that_cannot_be_written_is_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    unwritable = tmp_path / "no-such-directory" / "draft.json"
    code = main(
        ["repair", str(fixture_path("ctid_warnings.json")), "--draft", "--out", str(unwritable)]
    )
    assert code == 2
    assert "cannot write" in capsys.readouterr().err


def test_supplying_a_neighbour_can_settle_a_reference_without_patching_anything(
    tmp_path: Path,
) -> None:
    """ADR 0004 in this verb: resolution is additive. Supplying the owner turns
    an UNVERIFIABLE non-answer into an answer and must not turn it into an
    operation -- there is nothing misspelled in ``external_reference.json``."""
    out = tmp_path / "draft.json"
    code = main(
        [
            "repair",
            str(fixture_path("external_reference.json")),
            "--draft",
            "--out",
            str(out),
            "--resolve",
            str(RESOLVE / "owner_organization.json"),
        ]
    )
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == load_fixture("external_reference.json")
