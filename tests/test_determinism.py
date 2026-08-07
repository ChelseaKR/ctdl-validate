"""Same input, byte-identical findings output. Twice."""

from __future__ import annotations

import json
import subprocess
import sys

from ctdl_validate import validate_document
from ctdl_validate.cli import _render_json

from .conftest import fixture_path, load_fixture

FIXTURES = [
    "clean_framework.json",
    "bug_class_250_bare_uuid_for_ctid.json",
    "bug_class_252_wrong_framework_identifier.json",
    "inverse_mismatch.json",
]


def test_validate_twice_gives_identical_findings() -> None:
    for name in FIXTURES:
        first = validate_document(load_fixture(name))
        second = validate_document(load_fixture(name))
        assert first == second, name


def test_json_rendering_is_byte_identical_across_runs() -> None:
    for name in FIXTURES:
        first = _render_json(validate_document(load_fixture(name))).encode("utf-8")
        second = _render_json(validate_document(load_fixture(name))).encode("utf-8")
        assert first == second, name


def test_cli_output_is_byte_identical_across_processes() -> None:
    # Two separate interpreter processes: catches any hidden ordering that
    # depends on hash randomization or import order.
    path = str(fixture_path("bug_class_252_wrong_framework_identifier.json"))
    runs = [
        subprocess.run(
            [sys.executable, "-m", "ctdl_validate", path, "--format", "json"],
            capture_output=True,
            check=False,
        )
        for _ in range(2)
    ]
    assert runs[0].stdout == runs[1].stdout
    assert runs[0].stdout, "expected findings output"
    json.loads(runs[0].stdout)  # and it is valid JSON
