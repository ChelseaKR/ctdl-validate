"""The ``pre-commit`` hook (#63): its exit codes, and what it refuses to imply.

Three of these tests are about a number that is not a verdict. ``0 finding(s)``
over ``package.json`` is not the same fact as ``0 finding(s)`` over a clean
CTDL payload, and a hook declaring ``types: [json]`` is handed the first far
more often than the second. The counts the hook prints, and the sentence it
prints when it checked nothing, are the whole reason this entry point exists
rather than a loop around the CLI.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate.cli import main as cli_main
from ctdl_validate.hook import inspect, main

from .conftest import fixture_path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_FILE = ROOT / ".pre-commit-hooks.yaml"

CLEAN = "clean_framework.json"
BROKEN = "bug_class_250_bare_uuid_for_ctid.json"


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# -- the issue's own acceptance criterion -------------------------------------


def test_the_hook_passes_the_clean_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(fixture_path(CLEAN))]) == 0
    assert "1 checked, 0 not CTDL, 0 unreadable" in capsys.readouterr().out


def test_the_hook_fails_the_broken_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(fixture_path(BROKEN))]) == 1
    assert "CTID_BARE_UUID" in capsys.readouterr().out


# -- the reason this is not a flag on the CLI ---------------------------------


def test_the_hook_reads_every_file_pre_commit_hands_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pre-commit appends *all* matching staged paths to one invocation."""
    assert main([str(fixture_path(CLEAN)), str(fixture_path(BROKEN))]) == 1
    out = capsys.readouterr().out
    assert "2 staged file(s) -- 2 checked" in out
    assert CLEAN in out and BROKEN in out


def test_the_cli_still_refuses_a_second_file(capsys: pytest.CaptureFixture[str]) -> None:
    """The guard on the tempting simplification.

    ``entry: ctdl-validate`` in ``.pre-commit-hooks.yaml`` would look right and
    would work for every contributor who happened to stage one payload. This
    pins the fact that makes it wrong, so that if the CLI ever does grow
    multi-document support, the decision to fold the two together is taken
    deliberately here rather than discovered by a user.
    """
    with pytest.raises(SystemExit) as exc:
        cli_main([str(fixture_path(CLEAN)), str(fixture_path(BROKEN))])
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


# -- a file that is not CTDL is named, never rendered as a clean payload ------


def test_a_file_that_is_not_ctdl_is_counted_apart_and_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_ctdl = write(tmp_path, "package.json", json.dumps({"name": "x", "version": "1.0.0"}))
    assert main([str(fixture_path(CLEAN)), str(not_ctdl)]) == 0
    out = capsys.readouterr().out
    assert "1 checked, 1 not CTDL, 0 unreadable" in out
    assert "package.json" in out
    # It gets no report of its own: a "0 finding(s)" line under its name is
    # exactly the sentence this hook must not print about it.
    assert f"== {not_ctdl}" not in out


def test_a_run_that_checked_nothing_says_so_and_still_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absence is reported, not scored.

    Exit 0, because failing every commit in a repository that merely holds
    JSON would be absurd -- and a sentence saying the run is not evidence
    about any payload, because that is the true statement about it.
    """
    a = write(tmp_path, "tsconfig.json", json.dumps({"compilerOptions": {}}))
    b = write(tmp_path, "empty.json", "{}")
    assert main([str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "0 checked, 2 not CTDL" in out
    assert "Nothing was checked." in out
    assert "not evidence that any CTDL payload is clean" in out


def test_the_nothing_was_checked_line_is_absent_when_something_was_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The control on the test above: the sentence must not be unconditional.

    Paired with a presence assertion, because "the sentence is absent" is
    satisfied by any fixture that never reaches the branch.
    """
    not_ctdl = write(tmp_path, "package.json", json.dumps({"name": "x"}))
    assert main([str(fixture_path(CLEAN)), str(not_ctdl)]) == 0
    out = capsys.readouterr().out
    assert "not CTDL (valid JSON" in out, "the not-CTDL branch was never reached"
    assert "Nothing was checked." not in out


# -- unreadable is its own outcome, and it gates ------------------------------


@pytest.mark.parametrize(
    ("name", "text", "because"),
    [
        ("trailing.json", '{"a": 1,}', "is not valid JSON"),
        ("scalar.json", "42", "expected a JSON-LD object"),
        ("graph.json", '{"@graph": 3}', "@graph must be an array"),
    ],
)
def test_an_unreadable_file_exits_two_even_beside_a_clean_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str, text: str, because: str
) -> None:
    bad = write(tmp_path, name, text)
    assert main([str(fixture_path(CLEAN)), str(bad)]) == 2
    captured = capsys.readouterr()
    assert because in captured.err
    assert "0 not CTDL, 1 unreadable" in captured.out


def test_a_missing_file_is_unreadable_rather_than_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "gone.json")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_undecodable_bytes_are_unreadable_rather_than_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "latin1.json"
    path.write_bytes(b'{"name": "\xff\xfe"}')
    assert main([str(path)]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_an_unreadable_file_reports_no_findings_of_its_own(tmp_path: Path) -> None:
    """A file this run could not read has no findings, and that is not a fact
    about it. The dataclass keeps the two apart so no caller can read the
    empty tuple as a verdict."""
    outcome = inspect(write(tmp_path, "bad.json", "{oops"), [])
    assert outcome.unreadable is not None
    assert outcome.findings == ()
    assert outcome.checked is False
    assert outcome.gating is False


# -- --resolve reaches the session --------------------------------------------


def test_resolve_settles_a_reference_the_staged_file_cannot_see(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without the neighbour the reference is UNVERIFIABLE; with it, answered.

    Asserted on the severity the run reports rather than on the two outputs
    merely differing: "the strings are not equal" is satisfied by any
    incidental change, including one that made the answer worse.
    """
    competency = fixture_path("resolve") / "competency_only.json"
    framework = fixture_path("resolve") / "framework_only.json"

    assert main([str(competency)]) == 0
    without = capsys.readouterr().out
    assert "1 finding(s): 0 ERROR, 0 WARNING, 0 INFO, 1 UNVERIFIABLE" in without

    assert main([str(competency), "--resolve", str(framework)]) == 0
    with_neighbour = capsys.readouterr().out
    assert "1 finding(s): 0 ERROR, 0 WARNING, 1 INFO, 0 UNVERIFIABLE" in with_neighbour


# -- the hooks file is a contract with other repositories ---------------------


def _hooks() -> list[dict[str, Any]]:
    """Parse ``.pre-commit-hooks.yaml`` without adding a YAML dependency.

    The file is a three-key-per-entry list this repository writes; a hand
    reader is enough and keeps the runtime dependency count at zero. The
    assertions below fail loudly if its shape stops matching what is parsed.
    """
    entries: list[dict[str, Any]] = []
    for raw in HOOKS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("- "):
            entries.append({})
            line = line[2:]
        if ":" in line and entries:
            key, _, value = line.partition(":")
            entries[-1][key.strip()] = value.strip()
    return entries


def test_the_hook_entry_is_a_console_script_this_package_declares() -> None:
    """The failure this catches is silent: pre-commit builds the venv, the
    entry point is not there, and the hook dies with a command-not-found that
    names nothing about this repository."""
    (hook,) = _hooks()
    assert hook["id"] == "ctdl-validate"
    entry = hook["entry"]
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = scripts["project"]["scripts"]
    assert entry in declared, f"{entry} is not in [project.scripts]: {sorted(declared)}"
    module, _, attr = declared[entry].partition(":")
    assert module == "ctdl_validate.hook" and attr == "entrypoint"


def test_the_hook_declares_json_and_no_default_files_pattern() -> None:
    """Both halves are deliberate and are argued in the file's own comment.

    A default ``files:`` pattern would trade a gate that reports on files it
    has nothing to say about for one that silently selects nothing -- and a
    gate that ran over zero files reports success just as readily.
    """
    (hook,) = _hooks()
    assert hook["types"] == "[json]"
    assert "files" not in hook
    assert hook["language"] == "python"


def test_the_readme_documents_the_files_pattern_the_hook_does_not_default_to() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pre-commit" in readme
    assert "ChelseaKR/ctdl-validate" in readme
    assert "files:" in readme
