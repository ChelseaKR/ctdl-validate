"""The 1,200-document Registry survey: every published number, recomputed.

The write-up's protocol section was committed before the draw and promises
what will be published whatever the run shows. These tests hold the results
sections to that promise: the draw is the seed's draw, every drawn page is a
row or an exclusion, every table is the per-document records summed again,
every ERROR document is named, and the evidence carries nothing that could be
somebody's content.
"""

from __future__ import annotations

import importlib.util
import json
import random
import re
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs" / "findings" / "2026-08-21-registry-survey-at-scale.json"
WRITEUP = ROOT / "docs" / "findings" / "2026-08-21-registry-survey-at-scale.md"
EARLIER = (
    ROOT / "docs" / "findings" / "2026-08-15-published-registry-survey.revalidated-2026-08-21.json"
)
README = ROOT / "README.md"
HARNESS = ROOT / "tools" / "registry_survey.py"

SEVERITIES = ("ERROR", "WARNING", "INFO", "UNVERIFIABLE")

#: Everything a document row may carry. Identifiers, labels, codes and counts;
#: never a value from the record.
DOCUMENT_KEYS = {
    "alone",
    "classes",
    "ctid",
    "entities",
    "page",
    "publisher",
    "registry_references",
    "residue",
    "resolved",
    "type",
}
EXCLUSION_KEYS = {"detail", "page", "reason"}
ALLOWED_HOSTS = {"credentialengineregistry.org", "credreg.net"}


def _harness() -> ModuleType:
    """The survey harness itself, so the allow-list checked is the one that ran."""
    spec = importlib.util.spec_from_file_location("registry_survey", HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evidence() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    return payload


def _earlier() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(EARLIER.read_text(encoding="utf-8"))
    return payload


def _text() -> str:
    return " ".join(WRITEUP.read_text(encoding="utf-8").split())


def _rollup(documents: list[dict[str, Any]], run: str) -> dict[str, Any]:
    codes: Counter[str] = Counter()
    severities = dict.fromkeys(SEVERITIES, 0)
    with_error = clean = 0
    for document in documents:
        record = document[run]
        codes.update(record["codes"])
        for severity in SEVERITIES:
            severities[severity] += record["severities"].get(severity, 0)
        with_error += 1 if record["severities"].get("ERROR") else 0
        clean += 0 if record["codes"] else 1
    return {
        "documents": len(documents),
        "documents_with_no_findings": clean,
        "documents_with_at_least_one_error": with_error,
        "severities": {k: v for k, v in sorted(severities.items()) if v},
        "codes": dict(sorted(codes.items())),
    }


def _pct(part: int, whole: int) -> str:
    return f"{part} of {whole} ({round(100 * part / whole)}%)"


# -- the draw and the denominator ---------------------------------------------


def test_the_draw_is_the_seeds_draw_and_every_page_is_accounted_for() -> None:
    payload = _evidence()
    access = payload["access"]
    expected = sorted(
        random.Random(access["seed"]).sample(
            range(1, access["corpus_envelopes"] + 1), access["pages_drawn"]
        )
    )
    rows = [d["page"] for d in payload["documents"]] + [e["page"] for e in payload["exclusions"]]
    assert sorted(rows) == expected
    assert len(rows) == len(set(rows)), "a page appears twice"
    assert payload["sampled"] == len(payload["documents"])
    assert payload["excluded"] == len(payload["exclusions"])


def test_every_exclusion_carries_a_reason_fixed_before_the_draw() -> None:
    payload = _evidence()
    reasons = set(payload["protocol"]["exclusion_reasons"])
    assert reasons == set(_harness().EXCLUSION_REASONS)
    for row in payload["exclusions"]:
        assert set(row) <= EXCLUSION_KEYS, row
        assert row["reason"] in reasons, row


def test_the_header_rollups_are_the_documents_summed_again() -> None:
    payload = _evidence()
    for run in ("alone", "resolved"):
        assert _rollup(payload["documents"], run) == payload[f"rollup_{run}"], run
    by_type: dict[str, list[dict[str, Any]]] = {}
    for document in payload["documents"]:
        by_type.setdefault(str(document["type"]), []).append(document)
    assert set(by_type) == set(payload["by_type"])
    for label, group in by_type.items():
        for run in ("alone", "resolved"):
            assert _rollup(group, run) == payload["by_type"][label][run], (label, run)


# -- what the evidence may and may not carry ----------------------------------


def test_the_evidence_carries_no_record_content() -> None:
    payload = _evidence()
    identifier_only = _harness().identifier_only
    for document in payload["documents"]:
        unexpected = set(document) - DOCUMENT_KEYS
        assert not unexpected, f"{document['ctid']}: unexpected keys {sorted(unexpected)}"
        assert re.fullmatch(r"P\d{3}", document["publisher"]), document["publisher"]
        for run in ("alone", "resolved"):
            for example in document[run]["examples"].values():
                assert identifier_only(example["entity"]) == example["entity"], example
                assert identifier_only(example["value"]) == example["value"], example
    hosts = {
        host.lower().removeprefix("www.")
        for host in re.findall(r"https?://([^/\"\s]+)", EVIDENCE.read_text(encoding="utf-8"))
    }
    assert hosts <= ALLOWED_HOSTS, hosts - ALLOWED_HOSTS


# -- the headline and the per-code table ---------------------------------------


def test_the_headline_table_matches_the_evidence() -> None:
    payload = _evidence()
    text = _text()
    alone, resolved = payload["rollup_alone"], payload["rollup_resolved"]
    rows = {
        "Documents validated": (alone["documents"], resolved["documents"]),
        "Documents with no findings": (
            alone["documents_with_no_findings"],
            resolved["documents_with_no_findings"],
        ),
        "Documents with at least one ERROR": (
            alone["documents_with_at_least_one_error"],
            resolved["documents_with_at_least_one_error"],
        ),
    }
    for severity in SEVERITIES:
        rows[f"{severity} findings"] = (
            alone["severities"].get(severity, 0),
            resolved["severities"].get(severity, 0),
        )
    for label, (was, now) in rows.items():
        assert f"| {label} | {was:,} | {now:,} |" in text, label


def test_the_per_code_table_is_complete_and_correct() -> None:
    payload = _evidence()
    text = _text()
    severity_of: dict[str, str] = {}
    for document in payload["documents"]:
        for run in ("alone", "resolved"):
            for code, example in document[run]["examples"].items():
                severity_of.setdefault(code, example["severity"])
    codes = set(payload["rollup_alone"]["codes"]) | set(payload["rollup_resolved"]["codes"])
    assert codes == set(severity_of)
    published = {
        code: (severity, int(a.replace(",", "")), int(b.replace(",", "")))
        for code, severity, a, b in re.findall(
            r"\| `([A-Z_]+)` \| (ERROR|WARNING|INFO|UNVERIFIABLE) \| ([\d,]+) \| ([\d,]+) \|", text
        )
    }
    assert set(published) == codes, set(published) ^ codes
    for code in codes:
        expected = (
            severity_of[code],
            payload["rollup_alone"]["codes"].get(code, 0),
            payload["rollup_resolved"]["codes"].get(code, 0),
        )
        assert published[code] == expected, code


# -- the per-type table ---------------------------------------------------------


def test_the_per_type_table_matches_the_evidence() -> None:
    payload = _evidence()
    text = _text()
    groups = sorted(
        payload["by_type"].items(), key=lambda kv: (-kv[1]["alone"]["documents"], kv[0])
    )
    interpreted = [(label, g) for label, g in groups if g["alone"]["documents"] >= 20]
    rest = [(label, g) for label, g in groups if g["alone"]["documents"] < 20]
    for label, group in interpreted:
        resolved = group["resolved"]
        unsettled = resolved["severities"].get("UNVERIFIABLE", 0)
        row = (
            f"| `{label}` | {resolved['documents']} | {resolved['documents_with_no_findings']} "
            f"| {resolved['documents_with_at_least_one_error']} | {unsettled} |"
        )
        assert row in text, row
    if rest:
        documents = sum(g["alone"]["documents"] for _, g in rest)
        clean = sum(g["resolved"]["documents_with_no_findings"] for _, g in rest)
        errors = sum(g["resolved"]["documents_with_at_least_one_error"] for _, g in rest)
        unsettled = sum(g["resolved"]["severities"].get("UNVERIFIABLE", 0) for _, g in rest)
        row = f"| all other types ({len(rest)}) | {documents} | {clean} | {errors} | {unsettled} |"
        assert row in text, row


# -- every ERROR document, named ------------------------------------------------


def test_every_error_document_is_named_with_its_location() -> None:
    payload = _evidence()
    text = _text()
    rows = []
    for document in payload["documents"]:
        record = document["resolved"]
        for code, count in record["codes"].items():
            example = record["examples"][code]
            if example["severity"] != "ERROR":
                continue
            rows.append(
                f"| `{document['ctid']}` | `{code}` | `{example['property']}` "
                f"| `{example['entity']}` | {count} |"
            )
    total = payload["rollup_resolved"]["severities"].get("ERROR", 0)
    if total == 0:
        assert "no ERROR finding in any of the" in text
        return
    for row in rows:
        assert row in text, row
    assert text.count("| `ce-") >= len(rows)


def test_every_exclusion_is_named() -> None:
    payload = _evidence()
    text = _text()
    if not payload["exclusions"]:
        assert "there were no exclusions" in text
        return
    for row in payload["exclusions"]:
        assert f"| {row['page']} | `{row['reason']}` |" in text, row


# -- residue, publishers, and the change against the 120-document run -----------


def test_the_residue_table_matches_the_evidence() -> None:
    payload = _evidence()
    text = _text()
    kinds: Counter[str] = Counter()
    for document in payload["documents"]:
        kinds.update(document["residue"])
    assert sum(kinds.values()) == payload["rollup_resolved"]["severities"].get("UNVERIFIABLE", 0)
    for kind, count in kinds.items():
        assert f"| {kind} | {count} |" in text, kind


def test_the_publisher_concentration_is_recomputed() -> None:
    payload = _evidence()
    text = _text()
    counts = Counter(d["publisher"] for d in payload["documents"])
    n = len(payload["documents"])
    top = counts.most_common(5)
    assert f"{len(counts)} distinct publishers" in text
    assert f"the most frequent accounts for {_pct(top[0][1], n)}" in text
    assert f"the five most frequent for {_pct(sum(c for _, c in top), n)}" in text


def test_the_change_against_the_120_document_run_is_recomputed() -> None:
    earlier, now = _earlier(), _evidence()
    text = _text()

    def measures(payload: dict[str, Any]) -> dict[str, str]:
        documents = payload["documents"]
        n = len(documents)
        alone = _rollup(documents, "alone")
        resolved = _rollup(documents, "resolved")
        unverifiable_alone = alone["severities"].get("UNVERIFIABLE", 0)
        settled = unverifiable_alone - resolved["severities"].get("UNVERIFIABLE", 0)
        carrying = {
            code: sum(1 for d in documents if code in d["alone"]["codes"])
            for code in ("CONCEPT_RANGE_CONFLICT", "CTID_NOT_UUIDV4")
        }
        return {
            "Documents with no findings, alone": _pct(alone["documents_with_no_findings"], n),
            "Documents with at least one ERROR, with `--resolve`": _pct(
                resolved["documents_with_at_least_one_error"], n
            ),
            "Documents carrying `CONCEPT_RANGE_CONFLICT`": _pct(
                carrying["CONCEPT_RANGE_CONFLICT"], n
            ),
            "Documents carrying `CTID_NOT_UUIDV4`": _pct(carrying["CTID_NOT_UUIDV4"], n),
            "Share of findings that were UNVERIFIABLE, alone": (
                f"{round(100 * unverifiable_alone / sum(alone['severities'].values()))}%"
            ),
            "UNVERIFIABLE findings settled by `--resolve`": _pct(settled, unverifiable_alone),
        }

    before, after = measures(earlier), measures(now)
    for label in before:
        assert f"| {label} | {before[label]} | {after[label]} |" in text, label


def test_the_writeup_never_claims_conformance_from_a_clean_run() -> None:
    text = _text()
    assert "has not been shown to conform" in text
    assert "No percentage here is a population estimate" in text
    assert "Nothing is filed with anyone" in text


def test_the_writeup_has_no_unfilled_section() -> None:
    """The results sections were drafted with markers while the draw ran."""
    assert "{{" not in WRITEUP.read_text(encoding="utf-8")


def test_the_readme_quotes_this_run_from_the_evidence() -> None:
    payload = _evidence()
    text = " ".join(README.read_text(encoding="utf-8").split())
    n = payload["sampled"]
    resolved = payload["rollup_resolved"]
    assert f"{n:,} documents drawn uniformly at random" in text
    assert (
        f"{resolved['documents_with_at_least_one_error']} of {n:,} carried an ERROR finding" in text
    )
