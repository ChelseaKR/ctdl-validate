"""Run `extract` over a list of real pages and record what their markup held.

This is the harness behind `docs/findings/`. It is deliberately thin: it
fetches each page through the same `Fetcher` the CLI uses, with the same
robots.txt enforcement and the same rate limit, runs the same extraction, and
writes down what came back.

What it records is metadata only: HTTP outcome, which formats of structured
data the page carried, which vocabulary terms it declared, how many CTDL
entities came out, and which notes fired. It never records a value read from
a page. The survey is about whether provider pages publish machine-readable
structure, not about the content of anyone's course catalog, and a findings
file full of other people's copy would be both unnecessary and rude.

    uv run python tools/survey.py tools/survey-urls.txt docs/findings/<name>.json

Add --from-dir to re-run against saved copies instead of refetching.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ctdl_validate.extract.dom import MarkupError  # noqa: E402
from ctdl_validate.extract.fetch import Fetcher, FetchError  # noqa: E402
from ctdl_validate.extract.markup import extract_from_html  # noqa: E402
from ctdl_validate.findings import counts  # noqa: E402
from ctdl_validate.validator import validate_document  # noqa: E402

SURVEY_INTERVAL = 2.0


def read_targets(path: Path) -> list[tuple[str, str]]:
    """Lines of ``category<TAB>url``; blank lines and # comments ignored."""
    targets: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        category, _, url = stripped.partition("\t")
        targets.append((category.strip(), url.strip()))
    return targets


def saved_name(url: str) -> str:
    parts = urlparse(url)
    slug = (parts.path or "/").strip("/").replace("/", "_") or "index"
    return f"{parts.netloc}__{slug}.html"[:180]


def survey_page(page: str, url: str) -> dict[str, Any]:
    extraction = extract_from_html(page, url)
    note_codes = Counter(note.code for note in extraction.notes)
    dropped = sorted(
        {
            note.term
            for note in extraction.notes
            if note.code in ("CLASS_NOT_MAPPED", "PROPERTY_NOT_MAPPED", "PROPERTY_AMBIGUOUS")
        }
    )
    return {
        "blocks": [
            {"format": block.fmt, "items": block.items, "types": list(block.types)}
            for block in extraction.blocks
        ],
        "formats": sorted({block.fmt for block in extraction.blocks}),
        "declared_types": sorted({term for block in extraction.blocks for term in block.types}),
        "entities": extraction.entities,
        "ctdl_classes": sorted(
            {
                str(node.get("@type"))
                for node in extraction.document["@graph"]
                if isinstance(node, dict)
            }
        ),
        "notes": dict(sorted(note_codes.items())),
        "terms_dropped": dropped,
        "validation": _validate(extraction.document),
    }


def _validate(document: dict[str, Any]) -> dict[str, Any]:
    """What the validator says about the extract. The second half of the pipeline."""
    findings = validate_document(document)
    return {
        "summary": counts(findings),
        "codes": dict(sorted(Counter(finding.code for finding in findings).items())),
    }


def run(
    targets: list[tuple[str, str]], save_dir: Path | None, from_dir: Path | None
) -> Iterator[dict[str, Any]]:
    fetcher = Fetcher(min_interval=SURVEY_INTERVAL)
    for category, url in targets:
        record: dict[str, Any] = {"category": category, "url": url}
        try:
            if from_dir is not None:
                page = (from_dir / saved_name(url)).read_text(encoding="utf-8")
                record["outcome"] = "read from saved copy"
            else:
                result = fetcher.fetch(url)
                page = result.text
                record["outcome"] = "fetched"
                record["fetch"] = result.to_dict()
                if save_dir is not None:
                    (save_dir / saved_name(url)).write_text(page, encoding="utf-8")
            record["bytes"] = len(page.encode("utf-8"))
            record.update(survey_page(page, url))
        except (FetchError, MarkupError, OSError, RecursionError) as exc:
            record["outcome"] = "not read"
            record["reason"] = f"{type(exc).__name__}: {exc}"
        print(f"{record['outcome']:20} {url}", file=sys.stderr)
        yield record


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    read = [record for record in records if record["outcome"] != "not read"]
    with_markup = [record for record in read if record.get("formats")]
    with_entities = [record for record in read if record.get("entities")]
    formats = Counter(fmt for record in read for fmt in record.get("formats", []))
    types = Counter(term for record in read for term in record.get("declared_types", []))
    notes: Counter[str] = Counter()
    findings: Counter[str] = Counter()
    for record in read:
        notes.update(record.get("notes", {}))
        findings.update(record.get("validation", {}).get("codes", {}))
    clean = [
        record
        for record in with_entities
        if not record.get("validation", {}).get("summary", {}).get("ERROR")
    ]
    return {
        "targets": len(records),
        "read": len(read),
        "not_read": len(records) - len(read),
        "published_structured_data": len(with_markup),
        "produced_ctdl_entities": len(with_entities),
        "extracts_with_no_validation_errors": len(clean),
        "formats": dict(formats.most_common()),
        "declared_types": dict(types.most_common()),
        "note_codes": dict(notes.most_common()),
        "validation_codes": dict(findings.most_common()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path, help="category<TAB>url per line")
    parser.add_argument("output", type=Path, help="where to write the survey JSON")
    parser.add_argument("--save-dir", type=Path, help="also save each fetched page here")
    parser.add_argument("--from-dir", type=Path, help="read saved pages instead of fetching")
    args = parser.parse_args()

    if args.save_dir is not None:
        args.save_dir.mkdir(parents=True, exist_ok=True)
    records = list(run(read_targets(args.targets), args.save_dir, args.from_dir))
    payload = {"summary": summarize(records), "records": records}
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
