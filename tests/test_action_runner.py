"""Break the action's gate on purpose, before anyone depends on it.

`action.yml` is a gate other repositories will put in front of their own
publication step, and a gate that cannot fail is worse than no gate at all.
These tests run the action's entry point exactly as the composite step runs
it, same interpreter and same environment variables, and assert the exit code
it hands back to GitHub: 0 clean, 1 gated findings, 2 unusable input.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "action_runner.py"
FIXTURES = Path("tests") / "fixtures"


def _run(tmp_path: Path, **inputs: str) -> tuple[int, str, dict[str, str]]:
    """Invoke the runner the way the composite step does, from the repo root."""
    written = tmp_path / "outputs.txt"
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "GITHUB_OUTPUT": str(written),
        **inputs,
    }
    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=environment,
        check=False,
    )
    # Nothing is written when the run rejects its inputs before validating.
    raw = written.read_text(encoding="utf-8") if written.exists() else ""
    outputs = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    return completed.returncode, completed.stdout, outputs


def test_a_clean_document_passes(tmp_path: Path) -> None:
    code, _, outputs = _run(tmp_path, CTDL_PATH=str(FIXTURES / "clean_framework.json"))
    assert code == 0
    assert outputs["error-count"] == "0"
    assert outputs["files-validated"] == "1"


def test_an_error_finding_fails_the_job(tmp_path: Path) -> None:
    code, stdout, outputs = _run(tmp_path, CTDL_PATH=str(FIXTURES / "domain_violation.json"))
    assert code == 1, "an ERROR finding must fail the job"
    assert outputs["error-count"] == "1"
    assert "::error file=" in stdout, "the failing finding must be annotated on the file"


def test_a_warning_only_document_passes_at_the_default_threshold(tmp_path: Path) -> None:
    code, _, outputs = _run(tmp_path, CTDL_PATH=str(FIXTURES / "ctid_warnings.json"))
    assert code == 0
    assert outputs["warning-count"] == "2"


def test_the_same_document_fails_when_the_threshold_is_lowered(tmp_path: Path) -> None:
    code, _, _ = _run(
        tmp_path, CTDL_PATH=str(FIXTURES / "ctid_warnings.json"), CTDL_FAIL_ON="warning"
    )
    assert code == 1


def test_unverifiable_never_gates_at_any_threshold(tmp_path: Path) -> None:
    # UNVERIFIABLE is neither a pass nor a fail for the CLI, and the action
    # does not quietly promote it into one.
    for threshold in ("error", "warning", "info"):
        code, _, outputs = _run(
            tmp_path,
            CTDL_PATH=str(FIXTURES / "external_reference.json"),
            CTDL_FAIL_ON=threshold,
        )
        assert code == 0, threshold
        assert outputs["unverifiable-count"] == "1"


def test_resolve_reaches_the_cli_and_can_turn_a_run_red(tmp_path: Path) -> None:
    owner = FIXTURES / "resolve" / "variants" / "owner_is_not_an_organization.json"
    document = str(FIXTURES / "external_reference.json")
    assert _run(tmp_path, CTDL_PATH=document)[0] == 0
    assert _run(tmp_path, CTDL_PATH=document, CTDL_RESOLVE=str(owner))[0] == 1


def test_a_document_that_cannot_be_read_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    code, _, _ = _run(tmp_path, CTDL_PATH=str(FIXTURES / "no-such-document.json"))
    assert code == 2


def test_a_path_matching_nothing_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    code, stdout, _ = _run(tmp_path, CTDL_PATH=str(FIXTURES / "*.no-such-suffix"))
    assert code == 2
    assert "not a pass" in stdout


def test_an_unusable_fail_on_is_rejected_rather_than_ignored(tmp_path: Path) -> None:
    code, _, _ = _run(
        tmp_path, CTDL_PATH=str(FIXTURES / "clean_framework.json"), CTDL_FAIL_ON="whenever"
    )
    assert code == 2


def test_a_directory_is_validated_recursively_and_one_bad_file_fails_it(tmp_path: Path) -> None:
    code, _, outputs = _run(tmp_path, CTDL_PATH=str(FIXTURES))
    assert code == 1
    assert int(outputs["files-validated"]) > 1
    assert int(outputs["error-count"]) > 0
