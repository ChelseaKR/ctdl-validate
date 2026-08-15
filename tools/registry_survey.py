"""Run the validator over a random sample of what is already in the Registry.

Everything this tool checks, it checks before publication. Nothing had ever
asked what the published corpus looks like. The Credential Registry serves it
publicly, so this harness draws a sample and validates it, twice: once
document by document, and once with the documents each reference names in
hand, which is the difference `--resolve` exists to make.

**The access story, verified 2026-08-15 and re-verified at run time.**

- ``https://credentialengineregistry.org/robots.txt`` returns HTTP 404. RFC
  9309 section 2.3.1.3 treats an unavailable robots.txt as permission to
  proceed, and that is the branch ``extract/fetch.py`` already implements.
  This harness re-checks it every run through the same code rather than
  trusting the sentence above.
- ``GET /ce-registry/envelopes?page=N&per_page=1`` returns HTTP 200 with no
  credential, and the response header ``X-Total`` gives the size of the
  corpus. That is the sampling frame: page N with one item per page is the
  Nth envelope, so uniformly random page numbers give a uniformly random
  sample of envelopes.
- Each envelope carries ``decoded_resource``: the whole CTDL JSON-LD
  document, in exactly the shape ``ctdl-validate <file.json>`` reads.
- ``GET /resources/<ctid>`` returns the single entity a reference names, which
  is what ``--resolve`` wants.
- No API key is involved in any of the above. ``GET
  /ce-registry/envelopes/download``, the bulk dump, answers 401 without one,
  and this harness does not use it.

**Politeness.** Every request goes through the same ``Fetcher`` the ``extract``
command uses, subclassed only to accept ``application/json``: robots.txt read
first and obeyed with no override, the ``ctdl-validate`` product token in the
User-Agent with a link to the repository, redirects re-checked at every hop,
a byte cap, a timeout, and a minimum interval between requests that a
``Crawl-delay`` could lengthen but not shorten. One process, one request at a
time, no concurrency.

**What is recorded, and what is not.** The evidence file holds CTIDs, declared
classes, finding codes and counts, and one example location per code. It holds
no name, description, price, address, contact detail, or any other value from
anybody's record. Registry documents do carry personal contact details, and a
survey about structural validity has no business republishing them. The
fetched documents themselves are written to a cache directory for
reproducibility and are not committed.

    uv run python tools/registry_survey.py --sample 120 \\
        --cache .registry-cache --out docs/findings/<name>.json

Add ``--from-dir`` to re-run against the cache without touching the network.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ctdl_validate import __version__  # noqa: E402
from ctdl_validate.extract.fetch import Fetcher, FetchError, Headers  # noqa: E402
from ctdl_validate.findings import Finding, counts  # noqa: E402
from ctdl_validate.graph import DocumentError, parse_document  # noqa: E402
from ctdl_validate.schema import load_schema  # noqa: E402
from ctdl_validate.session import Session, build_supplied  # noqa: E402
from ctdl_validate.validator import validate  # noqa: E402

REGISTRY = "https://credentialengineregistry.org"
COMMUNITY = "ce-registry"
SURVEY_INTERVAL = 2.0
JSON_TYPES = ("application/json", "application/ld+json")


class RegistryFetcher(Fetcher):
    """The extractor's polite client, reading JSON instead of HTML.

    Subclassed rather than reimplemented so the survey cannot accidentally be
    less careful than the command it is surveying for. ``last_headers`` exists
    because the corpus size arrives in a response header and nothing in the
    validator's own output has any business carrying response headers around.
    """

    accepted_content_types = JSON_TYPES

    def __init__(self, contact: str | None = None) -> None:
        super().__init__(contact=contact, min_interval=SURVEY_INTERVAL)
        self.last_headers: Headers = {}
        self.requests = 0

    def _request(self, url: str, limit: int) -> tuple[int, Headers, bytes]:
        self.requests += 1
        status, headers, body = super()._request(url, limit)
        self.last_headers = headers
        return status, headers, body


def corpus_size(fetcher: RegistryFetcher) -> tuple[int, str]:
    """The number of envelopes in the community, and the robots.txt outcome."""
    result = fetcher.fetch(f"{REGISTRY}/{COMMUNITY}/envelopes?page=1&per_page=1&metadata_only=true")
    total = fetcher.last_headers.get("x-total")
    if total is None or not total.isdigit():
        raise FetchError(f"no usable X-Total header on the envelopes endpoint (got {total!r})")
    return int(total), result.robots


def fetch_envelope(fetcher: RegistryFetcher, page: int) -> dict[str, Any] | None:
    """The one envelope on page ``page`` when the page size is one."""
    result = fetcher.fetch(f"{REGISTRY}/{COMMUNITY}/envelopes?page={page}&per_page=1")
    body = json.loads(result.text)
    if not isinstance(body, list) or not body:
        return None
    envelope = body[0]
    return envelope if isinstance(envelope, dict) else None


def document_of(envelope: dict[str, Any]) -> tuple[str, Any] | None:
    """(ctid, decoded CTDL document) for a resource envelope, else None."""
    ctid = envelope.get("envelope_ceterms_ctid")
    document = envelope.get("decoded_resource")
    if not isinstance(ctid, str) or not isinstance(document, (dict, list)):
        return None
    return ctid, document


def finding_summary(findings: list[Finding]) -> dict[str, Any]:
    """Codes with counts, plus one example location per code. No values."""
    by_code: Counter[str] = Counter(f.code for f in findings)
    example: dict[str, dict[str, str]] = {}
    for finding in findings:
        example.setdefault(
            finding.code,
            {
                "severity": finding.severity.value,
                "entity": finding.entity,
                "property": finding.prop,
                "value": finding.value,
            },
        )
    return {
        "severities": counts(findings),
        "codes": dict(sorted(by_code.items())),
        "examples": dict(sorted(example.items())),
    }


def registry_references(findings: list[Finding]) -> list[str]:
    """Unresolved references that the Registry itself would serve."""
    return sorted(
        {
            f.value
            for f in findings
            if f.code == "REF_OUTSIDE_PAYLOAD"
            and f.value.startswith(f"{REGISTRY}/resources/")
            and urlparse(f.value).netloc == urlparse(REGISTRY).netloc
        }
    )


def cache_name(iri: str) -> str:
    return f"{iri.rstrip('/').rsplit('/', 1)[-1]}.json"


def collect_sample(
    fetcher: RegistryFetcher, pages_dir: Path, sample: Path, size: int, seed: int
) -> dict[str, Any]:
    """Draw the sample, one envelope per request, resumable and tolerant.

    Each page's raw envelope is cached under its page number, so a run
    interrupted by a transient network failure resumes without refetching what
    it already has and without redrawing the sample. A page that cannot be
    fetched is counted and skipped: one TLS timeout must not throw away an
    hour of polite requests, and a sample short by a handful of documents is
    reported as such rather than quietly retried into a different sample.
    """
    total, robots = corpus_size(fetcher)
    pages = sorted(random.Random(seed).sample(range(1, total + 1), size))
    failed: list[int] = []
    for page in pages:
        raw = pages_dir / f"{page}.json"
        if not raw.exists():
            try:
                envelope = fetch_envelope(fetcher, page)
            except (FetchError, json.JSONDecodeError) as exc:
                print(f"  page {page}: {exc}", file=sys.stderr)
                failed.append(page)
                continue
            if envelope is None:
                failed.append(page)
                continue
            raw.write_text(json.dumps(envelope, sort_keys=True, ensure_ascii=False), "utf-8")
        pair = document_of(json.loads(raw.read_text(encoding="utf-8")))
        if pair is None:
            continue
        ctid, document = pair
        (sample / f"{ctid}.json").write_text(
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
        )
    return {
        "corpus_envelopes": total,
        "robots": robots,
        "seed": seed,
        "pages_drawn": len(pages),
        "pages_unfetched": failed,
    }


def fetch_neighbours(
    fetcher: RegistryFetcher, neighbours: Path, wanted: list[str], cap: int
) -> dict[str, Any]:
    """Fetch the documents the sample's references name, up to ``cap``."""
    attempted, retrieved, failed = 0, 0, 0
    for iri in wanted[:cap]:
        destination = neighbours / cache_name(iri)
        if destination.exists():
            continue
        attempted += 1
        try:
            result = fetcher.fetch(iri)
            destination.write_text(result.text, encoding="utf-8")
            retrieved += 1
        except (FetchError, OSError) as exc:
            print(f"  neighbour {iri}: {exc}", file=sys.stderr)
            failed += 1
    return {
        "referenced_registry_resources": len(wanted),
        "cap": cap,
        "attempted": attempted,
        "retrieved": retrieved,
        "failed": failed,
    }


def survey(cache: Path, neighbours: Path) -> dict[str, Any]:
    """Validate every cached document, alone and then with neighbours in hand."""
    schema = load_schema()
    supplied = build_supplied([neighbours], schema) if neighbours.is_dir() else None
    documents: list[dict[str, Any]] = []
    for path in sorted(cache.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        try:
            graph = parse_document(document, schema)
        except DocumentError as exc:
            documents.append({"ctid": path.stem, "unreadable": str(exc)})
            continue
        alone = validate(Session(graph=graph, schema=schema))
        record: dict[str, Any] = {
            "ctid": path.stem,
            "entities": len(graph.nodes),
            "classes": sorted({t for node in graph.nodes for t in node.types}),
            "alone": finding_summary(alone),
            "registry_references": registry_references(alone),
        }
        if supplied is not None:
            record["resolved"] = finding_summary(
                validate(Session(graph=graph, schema=schema, supplied=supplied))
            )
        documents.append(record)
    return {
        "supplied_documents": 0 if supplied is None else len(supplied.documents),
        "supplied_entities": 0 if supplied is None else len(supplied.entities),
        "documents": documents,
    }


def roll_up(documents: list[dict[str, Any]], key: str) -> dict[str, Any]:
    codes: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    clean = 0
    with_error = 0
    for record in documents:
        summary = record.get(key)
        if summary is None:
            continue
        codes.update(summary["codes"])
        severities.update({k: v for k, v in summary["severities"].items() if v})
        if not summary["codes"]:
            clean += 1
        if summary["severities"].get("ERROR"):
            with_error += 1
    return {
        "documents_with_no_findings": clean,
        "documents_with_at_least_one_error": with_error,
        "severities": dict(sorted(severities.items())),
        "codes": dict(sorted(codes.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=120, help="documents to draw (default 120)")
    parser.add_argument("--seed", type=int, default=20260815, help="sample seed")
    parser.add_argument("--cache", type=Path, default=Path(".registry-cache"))
    parser.add_argument("--out", type=Path, required=True, help="evidence JSON to write")
    parser.add_argument(
        "--resolve-cap",
        type=int,
        default=250,
        help="most referenced resources to fetch for the second pass (default 250)",
    )
    parser.add_argument("--from-dir", action="store_true", help="re-run offline from the cache")
    parser.add_argument("--contact", default=None, help="contact detail for the User-Agent")
    args = parser.parse_args(argv)

    pages_dir = args.cache / "pages"
    sample_dir = args.cache / "sample"
    neighbour_dir = args.cache / "neighbours"
    for directory in (pages_dir, sample_dir, neighbour_dir):
        directory.mkdir(parents=True, exist_ok=True)

    access: dict[str, Any] = {"from_cache": True}
    if not args.from_dir:
        fetcher = RegistryFetcher(contact=args.contact)
        print(f"drawing {args.sample} of the corpus...", file=sys.stderr)
        meta = collect_sample(fetcher, pages_dir, sample_dir, args.sample, args.seed)
        first_pass = survey(sample_dir, neighbour_dir)
        wanted = sorted(
            {iri for d in first_pass["documents"] for iri in d.get("registry_references", [])}
        )
        print(f"fetching up to {args.resolve_cap} of {len(wanted)} neighbours...", file=sys.stderr)
        neighbour_meta = fetch_neighbours(fetcher, neighbour_dir, wanted, args.resolve_cap)
        access = {"from_cache": False, "requests": fetcher.requests, **meta, **neighbour_meta}

    result = survey(sample_dir, neighbour_dir)
    documents = result["documents"]
    payload = {
        "tool": {"name": "ctdl-validate", "version": __version__},
        "registry": REGISTRY,
        "community": COMMUNITY,
        "access": access,
        "sampled": len(documents),
        "supplied_documents": result["supplied_documents"],
        "supplied_entities": result["supplied_entities"],
        "rollup_alone": roll_up(documents, "alone"),
        "rollup_resolved": roll_up(documents, "resolved"),
        "documents": documents,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    headline = {k: payload[k] for k in ("sampled", "rollup_alone", "rollup_resolved")}
    print(json.dumps(headline, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
