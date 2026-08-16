"""The version must have exactly one source of truth (REL-02).

At v0.2.0 `pyproject.toml` said 0.2.0 while `__init__.py` hard-coded 0.1.0, so
`--version`, the JSON report stamp and the fetch User-Agent all announced a
release that was not the one running.

Asserting that `__version__` equals the version in `pyproject.toml` does *not*
catch this: the test runner reinstalls the distribution from `pyproject.toml`
before running, so the two agree by construction and the check can never fail.
That is a gate that cannot fail, which is worse than no gate.

The property that actually holds the fix is structural: there is no version
literal in the package to drift in the first place.
"""

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "ctdl_validate"


def _assignments_to_dunder_version(tree: ast.Module) -> list[ast.expr]:
    """Every value assigned to ``__version__``, from plain and annotated assignments."""

    found: list[ast.expr] = []
    for node in ast.walk(tree):
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if value is None:
            continue
        if any(isinstance(t, ast.Name) and t.id == "__version__" for t in targets):
            found.append(value)
    return found


def test_no_module_hardcodes_a_version_literal() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for value in _assignments_to_dunder_version(ast.parse(path.read_text())):
            # A literal fallback for "not installed" is fine; a real version is not.
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value[:1].isdigit()
                and "unknown" not in value.value
            ):
                rel = path.relative_to(PACKAGE_ROOT.parent.parent)
                offenders.append(f"{rel}: __version__ = {value.value!r}")
    assert offenders == [], (
        "__version__ must be read from the installed distribution, not hard-coded: "
        + "; ".join(offenders)
    )
