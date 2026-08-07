"""Command line interface.

Exit codes: 0 = no ERROR findings; 1 = at least one ERROR finding;
2 = the input could not be read or parsed at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .findings import Finding, Severity
from .graph import DocumentError
from .validator import validate_document

_SEVERITY_ORDER = (Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.UNVERIFIABLE)


def _counts(findings: list[Finding]) -> dict[str, int]:
    return {
        severity.value: sum(1 for f in findings if f.severity is severity)
        for severity in _SEVERITY_ORDER
    }


def _render_json(findings: list[Finding]) -> str:
    payload = {
        "tool": {"name": "ctdl-validate", "version": __version__},
        "findings": [f.to_dict() for f in findings],
        "summary": _counts(findings),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _render_text(findings: list[Finding]) -> str:
    lines = [f.render_text() + "\n" for f in findings]
    counts = _counts(findings)
    summary = ", ".join(f"{counts[s.value]} {s.value}" for s in _SEVERITY_ORDER)
    lines.append(f"{len(findings)} finding(s): {summary}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate",
        description=(
            "Deterministic structural validation of CTDL JSON-LD payloads before "
            "publication. Reads an object with @graph, a single entity, or an array "
            "of entities."
        ),
    )
    parser.add_argument("file", help="path to a CTDL JSON-LD document")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        raw = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ctdl-validate: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ctdl-validate: {args.file} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    try:
        findings = validate_document(data)
    except DocumentError as exc:
        print(f"ctdl-validate: {args.file}: {exc}", file=sys.stderr)
        return 2

    print(_render_json(findings) if args.format == "json" else _render_text(findings))
    return 1 if any(f.severity is Severity.ERROR for f in findings) else 0


def entrypoint() -> None:
    raise SystemExit(main())
