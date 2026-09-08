"""The ``pre-commit`` entry point: validate the staged CTDL payloads (#63).

Why this is not the CLI
-----------------------

``tools/action_runner.py`` opens by stating the division this project keeps:
the CLI is the gate and validates **one** document; expanding a set of
documents and collapsing their exit codes into one is somebody else's job.
``pre-commit`` appends every matching staged path to a single invocation, so a
hook whose ``entry`` were ``ctdl-validate`` would exit 2 with
``unrecognized arguments`` the first time a contributor staged two files. This
module is the other side of that division for ``pre-commit``, the way the
runner is for GitHub Actions: it re-implements no rule, no severity and no
report, and it reads its verdict out of :func:`ctdl_validate.validator.validate`
exactly as the CLI does.

What a wide file set does to a gate
-----------------------------------

The hook declares ``types: [json]``, so it is handed every staged ``.json``
file, and most repositories hold JSON that is not CTDL. Before the fix landed
on 2026-09-07 a run over ``package.json`` was **byte-identical** to a run over
a clean CTDL payload -- ``0 finding(s): 0 ERROR, ...``, exit 0 -- so a wall of
those reads as a passing gate over files nothing examined. Narrowing the
default ``files:`` pattern instead is the same failure the other way round: a
pattern narrow enough to exclude ``package.json`` can just as easily match
nothing in a user's repository, and a gate that ran over zero files also
reports success.

Neither is fixable by choosing a better pattern, so this module counts the
three outcomes separately and says all three in words:

- **checked** -- the document declared at least one ``ceterms:`` or ``ceasn:``
  term, so the rules had jurisdiction over it and the findings are a verdict;
- **not CTDL** -- valid JSON declaring no term this tool checks. Named and
  counted, never rendered as a clean report;
- **unreadable** -- missing, undecodable, not JSON, or not a shape the graph
  reader accepts.

An unreadable file exits 2 even when every other file is clean, which is the
posture ``action_runner`` already takes: a gate that could not read its input
is not a gate that passed. A ``.json`` file that does not parse is broken on
any reading, and this hook names it and the parse error. Repositories carrying
JSON-with-comments under a ``.json`` extension should exclude those paths in
``.pre-commit-config.yaml``; the README says so beside the hook.

When **nothing** was checked -- every staged file was not CTDL -- the run still
exits 0, because failing every commit in a repository that happens to hold
JSON would be absurd. It says so on its own line instead. That sentence is the
whole point: the difference between "your payloads are clean" and "none of
these files were payloads" is not something a reader should have to infer from
a zero.

Exit codes are the CLI's own: 0 nothing gating, 1 at least one ERROR finding,
2 a file could not be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .findings import Finding, Severity, render_findings_text
from .graph import DocumentError, scope_of
from .validator import build_session, validate

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_UNREADABLE = 2


@dataclass(frozen=True)
class Outcome:
    """What one staged file turned out to be.

    Exactly one of ``findings`` and ``unreadable`` is meaningful: a file this
    run could not read has no findings, and the absence of findings on such a
    file is not evidence about it. ``checked`` is false both for an unreadable
    file and for one that carried no term this tool has jurisdiction over, and
    those two are counted apart because they call for different actions from a
    reader -- fix the file, versus point the hook somewhere else.
    """

    path: Path
    checked: bool
    findings: tuple[Finding, ...] = ()
    report: str = ""
    unreadable: str | None = None

    @property
    def gating(self) -> bool:
        return any(f.severity is Severity.ERROR for f in self.findings)


def inspect(path: Path, resolve: Sequence[Path]) -> Outcome:
    """Read and validate one staged file, refusing rather than guessing.

    Mirrors ``cli.validate_main``'s three refusals in the same order, so the
    hook and the CLI disagree about no file: unreadable bytes, invalid JSON,
    and a payload the graph reader will not accept are each named, and none of
    them is reported as an absence of findings.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Outcome(path=path, checked=False, unreadable=f"cannot read: {exc}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return Outcome(path=path, checked=False, unreadable=f"is not valid JSON: {exc}")
    try:
        session = build_session(data, list(resolve))
        findings = validate(session)
    except DocumentError as exc:
        return Outcome(path=path, checked=False, unreadable=str(exc))
    scope = scope_of(session.graph)
    return Outcome(
        path=path,
        checked=scope.checked_entities > 0,
        findings=tuple(findings),
        report=render_findings_text(findings, scope=scope),
    )


def summarise(outcomes: Sequence[Outcome]) -> list[str]:
    """The three counts, in words, and the sentence that says a run checked nothing.

    Written as a count of files rather than a count of findings on purpose. A
    findings total cannot distinguish "every payload is clean" from "no file
    here was a payload", and that distinction is the reason this hook exists
    rather than a loop around the CLI.
    """
    checked = [o for o in outcomes if o.checked]
    unreadable = [o for o in outcomes if o.unreadable is not None]
    not_ctdl = [o for o in outcomes if not o.checked and o.unreadable is None]
    lines = [
        f"ctdl-validate {__version__}: {len(outcomes)} staged file(s) -- "
        f"{len(checked)} checked, {len(not_ctdl)} not CTDL, {len(unreadable)} unreadable"
    ]
    if not_ctdl:
        lines.append(
            "  not CTDL (valid JSON declaring no ceterms: or ceasn: term, so nothing "
            "in them was checked):"
        )
        lines.extend(f"    {o.path}" for o in not_ctdl)
    if not checked and not_ctdl and not unreadable:
        # The line this module exists for. Without it a run over a repository
        # of ordinary JSON is indistinguishable from a run over clean CTDL.
        lines.append(
            "Nothing was checked. None of the staged files declared a term this tool "
            "validates, so this run is not evidence that any CTDL payload is clean. "
            "Set `files:` in .pre-commit-config.yaml to the paths that hold your CTDL."
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate-pre-commit",
        description=(
            "Validate staged CTDL JSON-LD payloads. Invoked by pre-commit, which "
            "appends the staged filenames. Reports how many files it checked, how "
            "many were not CTDL, and how many it could not read -- a run that "
            "examined nothing does not report success on the merits."
        ),
    )
    parser.add_argument("files", nargs="+", metavar="FILE", help="a staged file to validate")
    parser.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "a further CTDL document, or a directory of them, whose entities every "
            "staged document may resolve references against. Repeatable. Nothing is "
            "fetched, and the supplied documents are never themselves validated."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    resolve = [Path(p) for p in args.resolve]
    outcomes = [inspect(Path(name), resolve) for name in args.files]

    for outcome in outcomes:
        if outcome.unreadable is not None:
            print(f"ctdl-validate: {outcome.path}: {outcome.unreadable}", file=sys.stderr)
        elif outcome.checked:
            print(f"== {outcome.path}")
            print(outcome.report)
            print()

    for line in summarise(outcomes):
        print(line)

    if any(o.unreadable is not None for o in outcomes):
        return EXIT_UNREADABLE
    return EXIT_FINDINGS if any(o.gating for o in outcomes) else EXIT_CLEAN


def entrypoint() -> None:
    raise SystemExit(main())
