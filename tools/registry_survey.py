"""Run the validator over a random sample of what is already in the Registry.

Everything this tool checks, it checks before publication. Nothing had ever
asked what the published corpus looks like. The Credential Registry serves it
publicly, so this harness draws a sample and validates it, twice: once
document by document, and once with the documents each reference names in
hand, which is the difference `--resolve` exists to make.

**The access story, verified 2026-08-15, re-verified 2026-08-21, and
re-verified at run time.**

- ``https://credentialengineregistry.org/robots.txt`` returns HTTP 404. RFC
  9309 section 2.3.1.3 treats an unavailable robots.txt as permission to
  proceed, and that is the branch ``extract/fetch.py`` already implements.
  This harness re-checks it every run through the same code rather than
  trusting the sentence above.
- ``GET /ce-registry/envelopes?page=N&per_page=1`` returns HTTP 200 with no
  credential, and the response header ``X-Total`` gives the size of the
  corpus. That is the sampling frame: page N with one item per page is the
  Nth envelope, so uniformly random page numbers give a uniformly random
  sample of envelopes. The endpoint ignores ``resource_type`` and
  ``envelope_ctdl_type`` query parameters (same ``X-Total`` either way,
  checked 2026-08-21), so there is no keyless per-type frame and no
  stratified draw; the per-type breakdown in the evidence comes from each
  envelope's own ``envelope_ctdl_type`` label, after the fact.
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
time, no concurrency, no retries.

**Every drawn page is accounted for.** A page number that was drawn appears in
the evidence exactly once: as a document row, or as an exclusion carrying one
of the reasons enumerated in ``EXCLUSION_REASONS``. A sample that quietly
shrinks is a sample whose denominator cannot be trusted.

**What is recorded, and what is not.** The evidence file holds CTIDs, the
Registry's own type label for each envelope, declared classes, finding codes
and counts, and one example location per code. Every recorded value passes
``identifier_only``: a JSON pointer, a CTID, a blank node id, a Registry or
credreg.net IRI, or a prefixed term is kept, and anything else is replaced by
its length. It holds no name, description, price, address, contact detail, or
any other value from anybody's record, and no third-party URL. Publishers are
labelled ``P001, P002, ...`` in order of first appearance so concentration can
be measured without recording who anyone is. Registry documents do carry
personal contact details, and a survey about structural validity has no
business republishing them. The fetched documents themselves are written to a
cache directory for reproducibility and are not committed.

**Reproducibility.** The draw (seed, size, corpus size, robots outcome, the
page numbers) and the fetch outcomes (request count, every failure with its
message) are written to ``<cache>/provenance.json`` as they happen, so
``--from-dir`` re-derives the whole evidence file from the cache, byte for
byte, with no network. A cache written before this file existed can be
re-analysed with ``--provenance <earlier evidence json>``.

    uv run python tools/registry_survey.py --sample 1200 --seed 20260821 \\
        --cache .registry-cache-2026-08-21 --out docs/findings/<name>.json

Add ``--from-dir`` to re-run against the cache without touching the network.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ctdl_validate import __version__  # noqa: E402
from ctdl_validate.extract.fetch import Fetcher, FetchError, Headers  # noqa: E402
from ctdl_validate.findings import Finding, counts  # noqa: E402
from ctdl_validate.graph import DocumentError, Graph, parse_document  # noqa: E402
from ctdl_validate.schema import SchemaIndex, load_schema  # noqa: E402
from ctdl_validate.session import Session, Supplied, build_supplied  # noqa: E402
from ctdl_validate.validator import validate  # noqa: E402

REGISTRY = "https://credentialengineregistry.org"
COMMUNITY = "ce-registry"
SURVEY_INTERVAL = 2.0
JSON_TYPES = ("application/json", "application/ld+json")
PROVENANCE = "provenance.json"

#: The only reasons a drawn page may be absent from the validated sample. Fixed
#: before any draw is analysed; a page that fits none of them is a bug in this
#: harness, not a silent omission.
EXCLUSION_REASONS = {
    "fetch-failed": "the envelope page could not be fetched (message recorded)",
    "empty-page": "the page returned no envelope",
    "not-resource-data": "the envelope's type is not resource_data",
    "no-document": "the envelope carries no CTID or no decoded_resource",
    "duplicate-ctid": "a page drawn earlier carried the same CTID",
    "unreadable": "the document is not a shape the validator reads (exit 2)",
}

#: Shapes a recorded value may take. Anything else is withheld by length.
IDENTIFIER_SHAPES = (
    re.compile(r"\$([.[].*)?"),  # JSON pointer into the payload
    re.compile(r"_:\S+"),  # blank node id
    re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
    re.compile(r"ce-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
    re.compile(r"https?://(www\.)?(credentialengineregistry\.org|credreg\.net)/\S*"),
    re.compile(r"[A-Za-z]+:[A-Za-z0-9_.-]+"),  # prefixed term
    re.compile(r"@type=\[.*\]"),
    re.compile(r"-"),
)


def identifier_only(text: str) -> str:
    """Keep an identifier; withhold anything that could be someone's content."""
    if any(shape.fullmatch(text) for shape in IDENTIFIER_SHAPES):
        return text
    return f"<withheld: {len(text)} characters>"


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
                "entity": identifier_only(finding.entity),
                "property": finding.prop,
                "value": identifier_only(finding.value),
            },
        )
    return {
        "severities": counts(findings),
        "codes": dict(sorted(by_code.items())),
        "examples": dict(sorted(example.items())),
    }


def is_registry_resource(iri: str) -> bool:
    return (
        iri.startswith(f"{REGISTRY}/resources/")
        and urlparse(iri).netloc == urlparse(REGISTRY).netloc
    )


def registry_references(findings: list[Finding]) -> list[str]:
    """Unresolved references that the Registry itself would serve."""
    return sorted(
        {
            f.value
            for f in findings
            if f.code == "REF_OUTSIDE_PAYLOAD" and is_registry_resource(f.value)
        }
    )


def residue(findings: list[Finding]) -> dict[str, int]:
    """What stays unsettled after ``--resolve``, by kind and never by name.

    The harness follows references into ``credentialengineregistry.org/resources/``
    only. Anything else is counted here: a CTDL vocabulary term on credreg.net,
    some other path on the Registry host, or a page on somebody's own website,
    which is recorded as "other host" and nothing more specific.
    """
    kinds: Counter[str] = Counter()
    for finding in findings:
        if finding.code != "REF_OUTSIDE_PAYLOAD":
            continue
        host = urlparse(finding.value).netloc.lower().removeprefix("www.")
        if host == "credreg.net":
            kinds["credreg.net term"] += 1
        elif host == urlparse(REGISTRY).netloc:
            kinds["registry, not a /resources/ URI"] += 1
        else:
            kinds["other host"] += 1
    return dict(sorted(kinds.items()))


def cache_name(iri: str) -> str:
    return f"{iri.rstrip('/').rsplit('/', 1)[-1]}.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def draw_pages(total: int, size: int, seed: int) -> list[int]:
    """The pre-registered draw: ``size`` page numbers from 1..total, sorted."""
    return sorted(random.Random(seed).sample(range(1, total + 1), size))


def collect_sample(fetcher: RegistryFetcher, cache: Path, size: int, seed: int) -> dict[str, Any]:
    """Draw the sample and fetch it, one envelope per request, resumably.

    Each page's raw envelope is cached under its page number, so a run
    interrupted by a transient network failure resumes without refetching what
    it already has and without redrawing the sample. A page that cannot be
    fetched is recorded with its message and skipped, never retried: one TLS
    timeout must not throw away an hour of polite requests, and a sample short
    by a handful of documents is reported as such rather than quietly retried
    into a different sample.
    """
    pages_dir = cache / "pages"
    provenance_path = cache / PROVENANCE
    if provenance_path.exists():
        provenance: dict[str, Any] = read_json(provenance_path)
        draw: dict[str, Any] = provenance["draw"]
        if (draw["seed"], draw["size"]) != (seed, size):
            raise SystemExit(
                f"{provenance_path} records seed {draw['seed']} and size {draw['size']}; "
                f"refusing to redraw in the same cache"
            )
    else:
        total, robots = corpus_size(fetcher)
        draw = {
            "seed": seed,
            "size": size,
            "corpus_envelopes": total,
            "robots": robots,
            "pages": draw_pages(total, size, seed),
        }
        provenance = {"draw": draw, "fetch": {"requests": 0, "pages_failed": {}}}
        write_json(provenance_path, provenance)

    failed: dict[str, str] = provenance["fetch"]["pages_failed"]
    for page in draw["pages"]:
        raw = pages_dir / f"{page}.json"
        if raw.exists() or str(page) in failed:
            continue
        try:
            envelope = fetch_envelope(fetcher, page)
        except (FetchError, json.JSONDecodeError, OSError) as exc:
            print(f"  page {page}: {exc}", file=sys.stderr)
            failed[str(page)] = str(exc)
            continue
        if envelope is None:
            failed[str(page)] = "empty-page"
            continue
        raw.write_text(json.dumps(envelope, sort_keys=True, ensure_ascii=False), "utf-8")
    provenance["fetch"]["requests"] += fetcher.requests
    fetcher.requests = 0
    write_json(provenance_path, provenance)
    return provenance


def fetch_neighbours(
    fetcher: RegistryFetcher, cache: Path, provenance: dict[str, Any], wanted: list[str], cap: int
) -> None:
    """Fetch the documents the sample's references name, up to ``cap``."""
    neighbours = cache / "neighbours"
    failed: dict[str, str] = provenance["fetch"].setdefault("neighbours_failed", {})
    attempted = 0
    for iri in wanted[:cap]:
        destination = neighbours / cache_name(iri)
        if destination.exists() or iri in failed:
            continue
        attempted += 1
        try:
            result = fetcher.fetch(iri)
            destination.write_text(result.text, encoding="utf-8")
        except (FetchError, OSError) as exc:
            print(f"  neighbour {iri}: {exc}", file=sys.stderr)
            failed[iri] = str(exc)
    provenance["fetch"]["neighbours"] = {
        "referenced": len(wanted),
        "cap": cap,
        "attempted": attempted,
        "failed": len(failed),
    }
    provenance["fetch"]["requests"] += fetcher.requests
    fetcher.requests = 0
    write_json(cache / PROVENANCE, provenance)


def screen_neighbours(
    neighbours: Path, schema: SchemaIndex
) -> tuple[list[Path], list[dict[str, str]]]:
    """Split cached neighbours into the ones the validator can index and the rest.

    ``build_supplied`` treats an unreadable supplied document as a hard stop,
    which is right for an operator and wrong for a survey: one malformed
    neighbour must not abort the resolved pass for 1,200 documents. The
    rejected ones are recorded by CTID and reason, never silently dropped.
    """
    accepted: list[Path] = []
    rejected: list[dict[str, str]] = []
    for path in sorted(neighbours.glob("*.json")) if neighbours.is_dir() else []:
        try:
            parse_document(read_json(path), schema)
        except (DocumentError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            rejected.append({"ctid": path.stem, "reason": str(exc)})
            continue
        accepted.append(path)
    return accepted, rejected


class Labeller:
    """Opaque publisher labels, assigned in order of first appearance."""

    def __init__(self) -> None:
        self._labels: dict[str, str] = {}

    def label(self, publisher: Any) -> str | None:
        if not isinstance(publisher, str):
            return None
        return self._labels.setdefault(publisher, f"P{len(self._labels) + 1:03d}")


@dataclass(frozen=True)
class Run:
    """What every document in one pass is validated against."""

    schema: SchemaIndex
    supplied: Supplied | None


def document_row(
    run: Run, page: int, ctid: str, envelope: dict[str, Any], graph: Graph
) -> dict[str, Any]:
    alone = validate(Session(graph=graph, schema=run.schema))
    record: dict[str, Any] = {
        "page": page,
        "ctid": ctid,
        "type": envelope.get("envelope_ctdl_type"),
        "entities": len(graph.nodes),
        "classes": sorted({t for node in graph.nodes for t in node.types}),
        "alone": finding_summary(alone),
        "registry_references": registry_references(alone),
    }
    if run.supplied is not None:
        resolved = validate(Session(graph=graph, schema=run.schema, supplied=run.supplied))
        record["resolved"] = finding_summary(resolved)
        record["residue"] = residue(resolved)
    return record


def exclusion(page: int, reason: str, detail: str | None = None) -> dict[str, Any]:
    assert reason in EXCLUSION_REASONS, reason
    row: dict[str, Any] = {"page": page, "reason": reason}
    if detail is not None:
        row["detail"] = detail
    return row


def classify_page(
    page: int, cache: Path, failed: dict[str, str], seen: dict[str, int]
) -> tuple[dict[str, Any], str, Any] | dict[str, Any]:
    """Either (envelope, ctid, document) for a validatable page, or its exclusion."""
    if str(page) in failed:
        reason = "empty-page" if failed[str(page)] == "empty-page" else "fetch-failed"
        return exclusion(page, reason, None if reason == "empty-page" else failed[str(page)])
    raw = cache / "pages" / f"{page}.json"
    if not raw.exists():
        return exclusion(page, "fetch-failed", "no cached envelope and no recorded failure")
    envelope: dict[str, Any] = read_json(raw)
    if envelope.get("envelope_type") != "resource_data":
        return exclusion(page, "not-resource-data", str(envelope.get("envelope_type")))
    pair = document_of(envelope)
    if pair is None:
        return exclusion(page, "no-document")
    ctid, document = pair
    if ctid in seen:
        return exclusion(page, "duplicate-ctid", f"first drawn on page {seen[ctid]}")
    seen[ctid] = page
    return envelope, ctid, document


def survey(cache: Path, provenance: dict[str, Any], resolve: bool) -> dict[str, Any]:
    """Validate every drawn page, alone and then with neighbours in hand."""
    schema = load_schema()
    accepted, rejected = screen_neighbours(cache / "neighbours", schema)
    run = Run(schema=schema, supplied=build_supplied(accepted, schema) if resolve else None)
    failed: dict[str, str] = provenance["fetch"].get("pages_failed", {})
    labeller = Labeller()
    seen: dict[str, int] = {}
    documents: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for page in provenance["draw"]["pages"]:
        outcome = classify_page(page, cache, failed, seen)
        if isinstance(outcome, dict):
            exclusions.append(outcome)
            continue
        envelope, ctid, document = outcome
        try:
            graph = parse_document(document, schema)
        except DocumentError as exc:
            exclusions.append(exclusion(page, "unreadable", str(exc)))
            continue
        record = document_row(run, page, ctid, envelope, graph)
        record["publisher"] = labeller.label(envelope.get("published_by"))
        documents.append(record)
    supplied = run.supplied
    return {
        "supplied_documents": 0 if supplied is None else len(supplied.documents),
        "supplied_entities": 0 if supplied is None else len(supplied.entities),
        "supplied_rejected": rejected,
        "documents": documents,
        "exclusions": exclusions,
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
        "documents": sum(1 for record in documents if record.get(key) is not None),
        "documents_with_no_findings": clean,
        "documents_with_at_least_one_error": with_error,
        "severities": dict(sorted(severities.items())),
        "codes": dict(sorted(codes.items())),
    }


def by_type(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """The same rollups, per Registry ``envelope_ctdl_type`` label."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in documents:
        groups.setdefault(str(record["type"]), []).append(record)
    return {
        label: {"alone": roll_up(group, "alone"), "resolved": roll_up(group, "resolved")}
        for label, group in sorted(groups.items())
    }


def access_block(provenance: dict[str, Any], from_cache: bool) -> dict[str, Any]:
    draw = provenance["draw"]
    fetch = provenance["fetch"]
    return {
        "from_cache": from_cache,
        "corpus_envelopes": draw["corpus_envelopes"],
        "robots": draw["robots"],
        "seed": draw["seed"],
        "pages_drawn": len(draw["pages"]),
        "pages_failed": len(fetch.get("pages_failed", {})),
        "requests": fetch.get("requests"),
        "neighbours": fetch.get("neighbours"),
        "carried_from": provenance.get("carried_from"),
    }


def legacy_provenance(cache: Path, evidence: Path) -> dict[str, Any]:
    """Rebuild a provenance record for a cache written before this file existed.

    The 2026-08-15 cache predates ``provenance.json``. Its draw is recoverable
    from the earlier evidence file's seed and corpus size, and its page set is
    the cache's own ``pages/`` directory; the two must agree or the cache is
    not the one that evidence describes.
    """
    earlier: dict[str, Any] = read_json(evidence)
    access = earlier["access"]
    pages = draw_pages(access["corpus_envelopes"], access["pages_drawn"], access["seed"])
    cached = sorted(int(p.stem) for p in (cache / "pages").glob("*.json"))
    if cached != pages:
        raise SystemExit(f"{cache} holds pages that are not the draw {evidence} describes")
    return {
        "draw": {
            "seed": access["seed"],
            "size": access["pages_drawn"],
            "corpus_envelopes": access["corpus_envelopes"],
            "robots": access["robots"],
            "pages": pages,
        },
        "fetch": {
            "requests": access["requests"],
            "pages_failed": {str(p): "fetch-failed" for p in access.get("pages_unfetched", [])},
            "neighbours": {
                "referenced": access["referenced_registry_resources"],
                "cap": access["cap"],
                "attempted": access["attempted"],
                "failed": access["failed"],
            },
        },
        "carried_from": evidence.name,
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
    parser.add_argument(
        "--provenance",
        type=Path,
        default=None,
        help="earlier evidence JSON to carry the access record from (legacy caches only)",
    )
    parser.add_argument("--contact", default=None, help="contact detail for the User-Agent")
    args = parser.parse_args(argv)

    cache: Path = args.cache
    for name in ("pages", "neighbours"):
        (cache / name).mkdir(parents=True, exist_ok=True)

    if args.from_dir:
        if args.provenance is not None:
            provenance = legacy_provenance(cache, args.provenance)
        elif (cache / PROVENANCE).exists():
            provenance = read_json(cache / PROVENANCE)
        else:
            parser.error(f"{cache / PROVENANCE} is missing; pass --provenance <earlier evidence>")
    else:
        fetcher = RegistryFetcher(contact=args.contact)
        print(f"drawing {args.sample} of the corpus...", file=sys.stderr)
        provenance = collect_sample(fetcher, cache, args.sample, args.seed)
        first_pass = survey(cache, provenance, resolve=False)
        wanted = sorted(
            {iri for d in first_pass["documents"] for iri in d.get("registry_references", [])}
        )
        print(f"fetching up to {args.resolve_cap} of {len(wanted)} neighbours...", file=sys.stderr)
        fetch_neighbours(fetcher, cache, provenance, wanted, args.resolve_cap)

    result = survey(cache, provenance, resolve=True)
    documents = result["documents"]
    payload = {
        "tool": {"name": "ctdl-validate", "version": __version__},
        "registry": REGISTRY,
        "community": COMMUNITY,
        "protocol": {
            "frame": f"GET {REGISTRY}/{COMMUNITY}/envelopes?page=N&per_page=1, N in 1..X-Total",
            "draw": "random.Random(seed).sample(range(1, X-Total + 1), size), sorted",
            "resolve": (
                "one hop; every referenced /resources/ URI on the Registry host, nothing else"
            ),
            "exclusion_reasons": EXCLUSION_REASONS,
        },
        "access": access_block(provenance, from_cache=args.from_dir),
        "sampled": len(documents),
        "excluded": len(result["exclusions"]),
        "supplied_documents": result["supplied_documents"],
        "supplied_entities": result["supplied_entities"],
        "supplied_rejected": result["supplied_rejected"],
        "rollup_alone": roll_up(documents, "alone"),
        "rollup_resolved": roll_up(documents, "resolved"),
        "by_type": by_type(documents),
        "documents": documents,
        "exclusions": result["exclusions"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, payload)
    headline = {k: payload[k] for k in ("sampled", "excluded", "rollup_alone", "rollup_resolved")}
    print(json.dumps(headline, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
