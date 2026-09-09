"""``ctdl-validate diff``: what changed between two runs, with no model and no network.

Each side is either a CTDL payload, validated on the spot with its own
``--resolve`` set, or a saved ``--format json`` report. The output names every
finding that appeared, disappeared, changed or moved, and states the severity
counts before and after.

Exit code is 0 whether or not anything changed, because a diff is data rather
than a verdict; ``--fail-on-new`` gates on newly added ERROR findings for a CI
job that wants one. 2 is reserved, as everywhere else in this tool, for an
input that could not be read.

**What a saved report cannot tell you.** A report records the tool version and
the report schema version, and nothing about which vendored CTDL snapshot
produced it. Two reports can therefore be compared without either side knowing
whether the same schema and context documents were behind them, and this
command prints that in the header rather than letting the silence read as
agreement. A side validated here is stamped with the running tool and the
vendored retrieval date it actually used.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .compare import Comparison, ReportError, compare, findings_from_report, is_report
from .findings import SEVERITY_ORDER, Finding, Severity
from .graph import DocumentError
from .report import REPORT_SCHEMA_VERSION
from .rules import RETRIEVED as VENDOR_RETRIEVED
from .validator import validate_document

#: What a saved report does not record, said in the place a reader would look
#: for it. Printing the vendored snapshot for one side and nothing for the
#: other would invite the reader to assume they matched.
UNRECORDED = "not recorded in a saved report"


@dataclass(frozen=True)
class Side:
    """One side of a diff, and where its findings and provenance came from."""

    path: Path
    findings: list[Finding]
    #: "payload" or "report": whether this side was validated here.
    origin: str
    tool_version: str
    #: The retrieval date of the vendored CTDL snapshot behind these findings,
    #: or :data:`UNRECORDED`.
    snapshot: str

    @property
    def label(self) -> str:
        return f"{self.path.name} ({self.origin})"


def load_side(path: Path, resolve: list[Path]) -> Side:
    """Read one side: a saved report if it is one, otherwise a payload to validate."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DocumentError(f"{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DocumentError(f"{path} is not JSON: {exc}") from exc
    if is_report(payload):
        if resolve:
            raise DocumentError(
                f"{path} is a saved report; --resolve applies to a payload that is "
                "validated here, and a report's findings were produced under whatever "
                "resolve set its own run used"
            )
        tool = payload.get("tool") or {}
        return Side(
            path=path,
            findings=findings_from_report(payload),
            origin="report",
            tool_version=str(tool.get("version", "")) or "unstated",
            snapshot=UNRECORDED,
        )
    return Side(
        path=path,
        findings=validate_document(payload, resolve or None),
        origin="payload",
        tool_version=__version__,
        snapshot=VENDOR_RETRIEVED,
    )


def provenance_notes(before: Side, after: Side) -> list[str]:
    """Every reason these two sides may not be comparable, stated up front.

    A diff between runs made by different tool versions can show a finding
    appearing because the tool changed rather than because the payload did.
    That does not make the diff useless and it is not an error, so the
    comparison still runs -- it makes the diff something the reader has to
    interpret, which they can only do if they are told.

    **There is deliberately no "the two snapshots differ" note.** There was
    one, and it could not fire: a side validated here is stamped with the
    running process's own :data:`VENDOR_RETRIEVED`, and a saved report is
    stamped :data:`UNRECORDED`, so two *known* snapshots are the same
    constant read twice and can never disagree. It read as a provenance guard
    and was a branch nothing could reach.
    :func:`ctdl_validate.snapshot.identity` is what a report would have to
    carry for the question to become answerable -- SARIF already carries it,
    a ``--format json`` report does not --- and
    ``tests/test_diff.py::test_a_validated_side_is_always_stamped_with_the_running_snapshot``
    fails on the day that changes, which is the day this note has something
    to say.
    """
    notes: list[str] = []
    if before.tool_version != after.tool_version:
        notes.append(
            f"tool version differs: {before.tool_version} -> {after.tool_version}. A "
            "finding may have appeared or disappeared because the tool changed."
        )
    unknown = [side for side in (before, after) if side.snapshot == UNRECORDED]
    if unknown:
        which = " and ".join(side.path.name for side in unknown)
        notes.append(
            f"vendored CTDL snapshot unknown for {which}: a saved report does not record "
            "it, so whether both sides were produced against the same schema and context "
            "documents cannot be determined here."
        )
    return notes


#: The fields of a :class:`~ctdl_validate.findings.Finding` that
#: :data:`~ctdl_validate.compare.IDENTITY` holds equal across a changed pair.
#: Named here so :func:`comparable_fields` can be the *remainder* rather than a
#: second hand-kept list beside it.
IDENTICAL_ACROSS_A_CHANGED_PAIR = ("code", "entity", "prop", "rule")


def comparable_fields() -> tuple[str, ...]:
    """Every field a ``changed`` pair can actually differ on.

    Derived from the dataclass, not listed. A list would go stale exactly
    where it hurts: ``message`` was a field this report could not show, and
    ``suggestions`` was added to ``Finding`` later and would have been the
    next one. Deriving it means a new field is named by the report the moment
    it exists, and ``tests/test_diff.py`` asserts that this and
    :data:`IDENTICAL_ACROSS_A_CHANGED_PAIR` together account for every field
    of ``Finding``, so neither half can quietly stop covering it.
    """
    fields = tuple(
        field.name
        for field in dataclasses.fields(Finding)
        if field.name not in IDENTICAL_ACROSS_A_CHANGED_PAIR
    )
    assert fields, "a changed pair would have no field to differ on, so nothing could be reported"
    return fields


def _shown(value: object) -> str:
    """One field of a finding, as a reader sees it."""
    if isinstance(value, Severity):
        return value.value
    if isinstance(value, tuple):
        return ", ".join(f"{item.value} ({item.difference})" for item in value) or "(none)"
    return str(value)


def _differences(old: Finding, new: Finding) -> list[str]:
    """What a changed pair really differs on, field by field.

    This is the half of the report that was missing. ``_line`` prints the
    severity, the code, the entity, the property, the value and the citation
    --- deliberately not the message, because a diff is scanned rather than
    read --- and the only other line printed for a changed pair was
    ``was: <value> / <severity>``. So a pair that differed **only in its
    wording** rendered as a change followed by two identical strings, and the
    message appeared nowhere on either side. That is the ordinary case for
    this verb rather than an exotic one: the header note says in terms that
    "a finding may have appeared or disappeared because the tool changed",
    and a reworded message under an unchanged identity is what a tool-version
    bump most often produces.

    Naming each differing field also takes away the reader's other job, which
    was to work out which half of ``a / b`` had moved.
    """
    lines: list[str] = []
    for field in comparable_fields():
        was, now = _shown(getattr(old, field)), _shown(getattr(new, field))
        if was == now:
            continue
        lines.append(f"      {field} now: {now}")
        lines.append(f"      {field} was: {was}")
    return lines


def _line(finding: Finding) -> str:
    return (
        f"  {finding.severity.value:12} {finding.code}  entity={finding.entity}\n"
        f"      {finding.prop} = {finding.value}\n"
        f"      rule: {finding.rule.citation}"
    )


def render_text(before: Side, after: Side, result: Comparison) -> str:
    lines = [f"before: {before.label}", f"after:  {after.label}"]
    lines += [f"note: {note}" for note in provenance_notes(before, after)]
    lines.append("")
    for heading, findings in (
        ("added: present after, absent before", result.added),
        ("removed: present before, absent after", result.removed),
    ):
        lines.append(f"{heading} ({len(findings)})")
        lines += [_line(finding) for finding in findings] or ["  (none)"]
        lines.append("")
    lines.append(f"changed: same finding, different value or message ({len(result.changed)})")
    for old, new in result.changed:
        lines.append(_line(new))
        lines += _differences(old, new)
    if not result.changed:
        lines.append("  (none)")
    lines.append("")
    lines.append(
        f"moved: same code, property, value and rule on a different entity ({len(result.moved)})"
    )
    for old, new in result.moved:
        lines.append(_line(new))
        lines.append(f"      was on: {old.entity}")
    if not result.moved:
        lines.append("  (none)")
    for key in result.ambiguous_moves:
        lines.append(
            f"  not paired: several findings removed and several added for {key[0]} "
            f"{key[1]}={key[2]}; which moved where is not decidable, so they are counted "
            "above as removed and added"
        )
    lines.append("")
    for name, summary in (("before", result.before), ("after", result.after)):
        counted = ", ".join(f"{summary[s.value]} {s.value}" for s in SEVERITY_ORDER)
        lines.append(f"{name}: {sum(summary.values())} finding(s): {counted}")
    lines.append(
        f"{result.unchanged} unchanged. A removed finding is a finding this run did not "
        "report; it is not evidence that it was fixed."
    )
    return "\n".join(lines)


def render_json(before: Side, after: Side, result: Comparison) -> str:
    payload: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "ctdl-validate", "version": __version__},
        "before": {
            "path": str(before.path),
            "origin": before.origin,
            "tool_version": before.tool_version,
            "ctdl_snapshot": before.snapshot,
        },
        "after": {
            "path": str(after.path),
            "origin": after.origin,
            "tool_version": after.tool_version,
            "ctdl_snapshot": after.snapshot,
        },
        "notes": provenance_notes(before, after),
        "diff": result.to_dict(),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate diff",
        description=(
            "Compare two runs. Each side is a CTDL JSON-LD payload, validated here, or "
            "a saved --format json report. No model call and no network access."
        ),
        epilog=(
            "A finding present before and absent after is reported as removed, not as "
            "resolved: two finding lists cannot tell a repair from a run that read a "
            "different payload or could not get far enough to report it."
        ),
    )
    parser.add_argument("before", help="a CTDL JSON-LD payload, or a saved JSON report")
    parser.add_argument("after", help="a CTDL JSON-LD payload, or a saved JSON report")
    parser.add_argument(
        "--resolve-before",
        action="append",
        default=[],
        metavar="PATH",
        help="a document or directory to resolve the BEFORE side against. Repeatable.",
    )
    parser.add_argument(
        "--resolve-after",
        action="append",
        default=[],
        metavar="PATH",
        help="a document or directory to resolve the AFTER side against. Repeatable.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--fail-on-new",
        action="store_true",
        help=(
            "exit 1 when an ERROR finding is present after and absent before. Without "
            "it a diff exits 0 whatever it found, because a diff is data."
        ),
    )
    return parser


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(list(argv))
    try:
        before = load_side(Path(args.before), [Path(p) for p in args.resolve_before])
        after = load_side(Path(args.after), [Path(p) for p in args.resolve_after])
    except (DocumentError, ReportError) as exc:
        print(f"ctdl-validate diff: {exc}", file=sys.stderr)
        return 2
    except RecursionError:
        print("ctdl-validate diff: an input nests too deeply to read safely", file=sys.stderr)
        return 2
    result = compare(before.findings, after.findings)
    print(
        render_json(before, after, result)
        if args.format == "json"
        else render_text(before, after, result)
    )
    return 1 if args.fail_on_new and result.new_errors else 0
