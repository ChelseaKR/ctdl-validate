"""Keep the Semgrep exception narrow and bound to the supported Python floor."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMGREP_WORKFLOW = ROOT / ".github" / "workflows" / "semgrep.yml"
PYTHON_COMPATIBILITY_RULE = "python.lang.compatibility.python37.python37-compatibility-importlib2"


def test_python_policy_is_aligned_on_312() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["project"]["requires-python"] == ">=3.12"
    assert config["tool"]["mypy"]["python_version"] == "3.12"
    assert config["tool"]["ruff"]["target-version"] == "py312"
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_semgrep_exception_is_exact_and_the_gate_stays_blocking() -> None:
    workflow = SEMGREP_WORKFLOW.read_text(encoding="utf-8")
    command = " ".join(workflow.split())

    assert command.count("semgrep ci --config auto") == 1
    assert workflow.count("--exclude-rule") == 1
    assert workflow.count(PYTHON_COMPATIBILITY_RULE) == 1
    assert "semgrep ci --config auto --exclude-rule " + PYTHON_COMPATIBILITY_RULE in command

    broad_bypasses = (
        "continue-on-error",
        "|| true",
        "|| :",
        "--no-error",
        "--severity",
        "--suppress-errors",
    )
    assert all(bypass not in workflow for bypass in broad_bypasses)
    assert re.search(r"--exclude(?:\s|=)", workflow) is None
