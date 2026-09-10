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
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .findings import Severity, render_findings_json, render_findings_text
from .graph import DocumentError, scope_of
from .report import read_report_schema
from .sarif import render_findings_sarif
from .validator import build_session, validate

#: The one command in this tool that opens a network connection.
#:
#: Dispatched by name before the default parser sees the arguments, and
#: imported only then, by a **literal** module path. Until 2026-09-06 it was
#: imported at module scope, so every validation run loaded the fetching code
#: on its way past. Nothing was ever fetched -- ``tests/test_offline_guarantee``
#: takes the socket away and the validator still runs -- but "the default path
#: does not load the code that fetches" is a stronger claim than "the code
#: that fetches was not called", and it is checkable in a fresh process.
#:
#: Interpolating the argument into ``import_module`` would work and would let
#: this pair of names be written once, but it also means the first word of a
#: command line names a module. That is not a property worth having to save a
#: line, and semgrep's ``non-literal-import`` says so.
EXTRACT_COMMAND = "extract"

#: A verb that is as deterministic and as offline as the default path.
#: Dispatched by name, and for the same reason ``extract`` is: the default
#: parser takes a file as its first positional, so a verb name would be read
#: as a filename. Imported by a literal module path, not by interpolating the
#: argument, so the first word of a command line never names a module.
DIFF_COMMAND = "diff"

#: The third verb dispatched by name, for the same reason as the other two: the
#: default parser takes a file as its first positional, so a verb name would be
#: read as a filename. Like ``diff`` it is offline and deterministic; unlike
#: either of the others it *writes* -- to a path the caller names, never to the
#: input, which :func:`ctdl_validate.repair._refuse_output` enforces before
#: anything is opened.
REPAIR_COMMAND = "repair"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == EXTRACT_COMMAND:
        extract_cli = importlib.import_module("ctdl_validate.extract.command")
        extracted: int = extract_cli.main(args[1:])
        return extracted
    if args and args[0] == DIFF_COMMAND:
        diff_cli = importlib.import_module("ctdl_validate.diff")
        verdict: int = diff_cli.main(args[1:])
        return verdict
    if args and args[0] == REPAIR_COMMAND:
        repair_cli = importlib.import_module("ctdl_validate.repair")
        drafted: int = repair_cli.main(args[1:])
        return drafted
    return validate_main(args)


class PrintReportSchema(argparse.Action):
    """Print the published report schema and exit, the way ``--version`` does.

    An action rather than a subcommand: it takes no argument and answers
    before the required positional is missed, so ``ctdl-validate
    --report-schema`` needs no document.
    """

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: object) -> None:
        super().__init__(option_strings=list(option_strings), dest=dest, nargs=0, **kwargs)  # type: ignore[arg-type]

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        print(read_report_schema(), end="")
        parser.exit()


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
        choices=("text", "json", "sarif"),
        default="text",
        help=(
            "output format (default: text). sarif is SARIF 2.1.0 with the same findings: "
            "see src/ctdl_validate/sarif.py for how severities map and why no result is "
            "ever a pass"
        ),
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help=(
            "beneath a finding whose correction the payload itself determines, name the "
            "value it determines: the lower-cased CTID, the CTID this entity's own @id "
            "already carries, the @id of the entity that declares a bare CTID, the one "
            "framework in reach. Computed offline from this run's own input; never "
            "offered where more than one candidate exists, never for an UNVERIFIABLE "
            "finding, and never a claim about what was meant. Off by default: without "
            "it this command's bytes are unchanged"
        ),
    )
    parser.add_argument(
        "--report-schema",
        action=PrintReportSchema,
        help=(
            "print the JSON Schema that every --format json report conforms to, and exit. "
            "The report carries the schema's version in report_schema_version"
        ),
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
        # The session rather than `validate_document`, because the run has to
        # be able to say how much of the document it had jurisdiction over --
        # a report of "0 finding(s)" over a file that is not CTDL at all was
        # byte-identical to one over a clean payload. Same checks, same
        # findings, same order: `validate_document` is these two calls.
        session = build_session(data, [Path(p) for p in args.resolve])
        findings = validate(session, suggest=args.suggest)
    except DocumentError as exc:
        print(f"ctdl-validate: {args.file}: {exc}", file=sys.stderr)
        return 2
    scope = scope_of(session.graph)

    if args.format == "json":
        print(render_findings_json(findings, __version__, scope=scope))
    elif args.format == "sarif":
        print(render_findings_sarif(findings, __version__, Path(args.file)))
    else:
        print(render_findings_text(findings, scope=scope))
    return 1 if any(f.severity is Severity.ERROR for f in findings) else 0


def entrypoint() -> None:
    raise SystemExit(main())
