"""Command line interface.

Two commands with two different postures, and the grammar keeps them apart:

- ``ctdl-validate <file.json>`` validates. Offline, no model calls, same input
  and same output byte for byte. This is the default and only shape the tool
  had before ``extract`` existed, and it is unchanged. ``--resolve`` adds more
  local documents to what the run can see; it is the difference between "this
  reference points at something I cannot check" and "this reference points at
  an entity of the wrong class". It reads files. It fetches nothing.
- ``ctdl-validate extract <url>`` fetches one page and reads its structured
  markup. It is the only command that opens a network connection, and it
  documents that posture in :mod:`ctdl_validate.extract.fetch`.

Validation exit codes: 0 = no ERROR findings; 1 = at least one ERROR finding;
2 = the input could not be read or parsed at all. The ``extract`` subcommand
documents its own, in :mod:`ctdl_validate.extract.command`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .extract.command import main as extract_main
from .findings import Severity, render_findings_json, render_findings_text
from .graph import DocumentError
from .validator import validate_document

EXTRACT_COMMAND = "extract"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == EXTRACT_COMMAND:
        return extract_main(args[1:])
    return validate_main(args)


def validate_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate",
        description=(
            "Deterministic structural validation of CTDL JSON-LD payloads before "
            "publication. Reads an object with @graph, a single entity, or an array "
            "of entities. No network calls, no model calls. Run "
            "`ctdl-validate extract --help` for the extraction subcommand, which is "
            "the only part of this tool that fetches anything."
        ),
    )
    parser.add_argument("file", help="path to a CTDL JSON-LD document")
    parser.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "a further CTDL document, or a directory of them, whose entities this run "
            "can resolve references against. Repeatable. Nothing is fetched, and the "
            "supplied documents are never themselves validated."
        ),
    )
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
        findings = validate_document(data, [Path(p) for p in args.resolve])
    except DocumentError as exc:
        print(f"ctdl-validate: {args.file}: {exc}", file=sys.stderr)
        return 2

    print(
        render_findings_json(findings, __version__)
        if args.format == "json"
        else render_findings_text(findings)
    )
    return 1 if any(f.severity is Severity.ERROR for f in findings) else 0


def entrypoint() -> None:
    raise SystemExit(main())
