"""``ctdl-validate extract <url>``: the command, its flags, and its exit codes.

Exit codes, deliberately distinct from validation's:

- ``0``: the page was read and at least one CTDL entity came out of it.
- ``1``: the page was read and produced no CTDL entities. Not an error; on the
  open web it is the common case, and it is reported with the reasons.
- ``2``: nothing could be read. A robots.txt disallow, an unreachable
  robots.txt, an HTTP error, a redirect loop, a non-HTML response, a page over
  the byte cap. Never a partial extract.

With ``--validate``, the extracted document is handed straight to the
validator in the same process and the exit code becomes the worse of the two,
so ``extract --validate`` fails when the extract would fail validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .. import __version__
from ..findings import Severity, render_findings_json, render_findings_text
from ..validator import validate_document
from .dom import MarkupError
from .fetch import DEFAULT_MAX_BYTES, DEFAULT_MIN_INTERVAL, DEFAULT_TIMEOUT, Fetcher, FetchError
from .markup import extract_from_html
from .report import Extraction, render_document, render_json, render_text

EXIT_OK = 0
EXIT_NOTHING_EXTRACTED = 1
EXIT_UNREADABLE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate extract",
        description=(
            "Read the structured markup a page already publishes (JSON-LD, "
            "microdata, RDFa Lite) and emit CTDL-shaped JSON-LD containing only what "
            "the markup literally asserts. Fetches robots.txt first and obeys it. No "
            "model calls; nothing is inferred from prose."
        ),
    )
    parser.add_argument("url", help="the page to read, http or https")
    parser.add_argument(
        "--format",
        choices=("text", "json", "jsonld"),
        default="text",
        help=(
            "text: the extraction report (default). json: report and document in one "
            "envelope. jsonld: the CTDL document alone on stdout, with the report on "
            "stderr so nothing is dropped silently."
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="validate the extracted document in the same run and report both",
    )
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        help=(
            "read a saved copy of the page instead of fetching it; <url> is still "
            "used as the document's base URL. Makes a run reproducible offline."
        ),
    )
    parser.add_argument(
        "--contact",
        help="contact detail to add to the User-Agent, e.g. an email address",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="request timeout in seconds"
    )
    parser.add_argument(
        "--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="cap on the response body"
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=DEFAULT_MIN_INTERVAL,
        help="minimum seconds between requests to a host; a site's Crawl-delay may raise it",
    )
    return parser


def _load_page(args: argparse.Namespace) -> tuple[str, dict[str, object]]:
    if args.from_file:
        path = Path(args.from_file)
        try:
            page = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise FetchError(f"cannot read {path}: {exc}") from exc
        return page, {"source": "file", "path": str(path), "bytes": len(page.encode("utf-8"))}
    fetcher = Fetcher(
        contact=args.contact,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        min_interval=args.min_interval,
    )
    result = fetcher.fetch(args.url)
    return result.text, result.to_dict()


def _validation_payload(extraction: Extraction) -> tuple[str, str, int]:
    findings = validate_document(extraction.document)
    code = (
        EXIT_NOTHING_EXTRACTED if any(f.severity is Severity.ERROR for f in findings) else EXIT_OK
    )
    return render_findings_text(findings), render_findings_json(findings, __version__), code


def _emit(extraction: Extraction, fetch: dict[str, object], args: argparse.Namespace) -> int:
    validation_text, validation_json, validation_code = (
        _validation_payload(extraction) if args.validate else ("", "", EXIT_OK)
    )

    if args.format == "json":
        payload = json.loads(render_json(extraction, __version__, fetch))
        if args.validate:
            payload["validation"] = json.loads(validation_json)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    elif args.format == "jsonld":
        print(render_document(extraction))
        print(render_text(extraction), file=sys.stderr)
        if args.validate:
            print("\nvalidation of the extracted document:", file=sys.stderr)
            print(validation_text, file=sys.stderr)
    else:
        print(render_text(extraction))
        if args.validate:
            print("\nvalidation of the extracted document:")
            print(validation_text)

    extraction_code = EXIT_OK if extraction.entities else EXIT_NOTHING_EXTRACTED
    return max(extraction_code, validation_code)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        page, fetch = _load_page(args)
        extraction = extract_from_html(page, args.url)
    except (FetchError, MarkupError, RecursionError) as exc:
        print(f"ctdl-validate extract: {args.url}: {exc}", file=sys.stderr)
        return EXIT_UNREADABLE
    return _emit(extraction, fetch, args)
