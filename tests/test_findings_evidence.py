"""The published finding must agree with the evidence beside it.

A findings document that drifts from its own data is worse than no findings
document, so the numbers in the headline table are checked against the survey
JSON rather than trusted. The same tests guard the two things a survey run
could get wrong on its way into the repository: a malformed target list, and
page content leaking into the committed evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "tools" / "survey-urls.txt"
SURVEY = ROOT / "docs" / "findings" / "2026-08-14-provider-markup-survey.json"
WRITEUP = ROOT / "docs" / "findings" / "2026-08-14-provider-markup-survey.md"

#: Everything a survey record is allowed to carry. The survey reports on
#: whether pages publish machine-readable structure, so it records term names
#: and counts; a record holding a value read from someone's page would mean
#: this repository had quietly become a copy of their content.
RECORD_KEYS = {
    "blocks",
    "bytes",
    "category",
    "ctdl_classes",
    "declared_types",
    "entities",
    "fetch",
    "formats",
    "notes",
    "outcome",
    "reason",
    "terms_dropped",
    "url",
    "validation",
}


def _records() -> list[dict[str, Any]]:
    payload = json.loads(SURVEY.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = payload["records"]
    return records


def _summary() -> dict[str, Any]:
    payload = json.loads(SURVEY.read_text(encoding="utf-8"))
    summary: dict[str, Any] = payload["summary"]
    return summary


def _headline() -> dict[str, int]:
    """Label -> count, from the writeup's first table."""
    found: dict[str, int] = {}
    for line in WRITEUP.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) >= 4 and re.fullmatch(r"\d+", cells[2]):
            found[cells[1]] = int(cells[2])
    return found


def test_the_target_list_is_well_formed() -> None:
    lines = [
        line
        for line in TARGETS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    urls = []
    for line in lines:
        category, tab, url = line.partition("\t")
        assert tab, f"expected category<TAB>url: {line!r}"
        assert category.strip() and not category.startswith(" ")
        assert url.startswith("https://"), url
        urls.append(url)
    assert len(set(urls)) == len(urls), "a duplicate URL would double-count a provider"


def test_every_target_appears_in_the_survey_exactly_once() -> None:
    targets = [
        line.split("\t", 1)[1]
        for line in TARGETS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert [record["url"] for record in _records()] == targets


def test_the_evidence_carries_no_page_content() -> None:
    for record in _records():
        unexpected = set(record) - RECORD_KEYS
        assert not unexpected, f"{record['url']}: unexpected keys {sorted(unexpected)}"


def test_the_headline_numbers_match_the_evidence() -> None:
    summary, headline = _summary(), _headline()
    read = summary["read"]
    expected = {
        "URLs attempted": summary["targets"],
        "Pages read": read,
        "Published any structured data (JSON-LD, microdata, or RDFa)": summary[
            "published_structured_data"
        ],
        "Published none at all": read - summary["published_structured_data"],
        "Produced at least one CTDL entity": summary["produced_ctdl_entities"],
        "Published a CTID": 0,
    }
    for label, count in expected.items():
        assert headline.get(label) == count, label


def test_the_claim_that_no_page_published_a_ctid_holds() -> None:
    for record in _records():
        assert "ceterms:ctid" not in record.get("ctdl_classes", [])
        if record.get("entities"):
            assert record["notes"].get("CTID_ABSENT") == 1


def test_the_claim_that_four_pages_described_their_own_offering_holds() -> None:
    with_course = [
        record for record in _records() if "ceterms:Course" in record.get("ctdl_classes", [])
    ]
    assert len(with_course) == 4
    assert "Produced a CTDL entity for the thing being offered | 4" in WRITEUP.read_text(
        encoding="utf-8"
    )


# -- the Registry survey, whose numbers are severity counts rather than pages --

REGISTRY = ROOT / "docs" / "findings" / "2026-08-15-published-registry-survey.json"
REGISTRY_WRITEUP = ROOT / "docs" / "findings" / "2026-08-15-published-registry-survey.md"

#: Everything a Registry survey document is allowed to carry. Registry records
#: hold individual names, phone numbers and email addresses; a survey about
#: structural validity has no business republishing any of them, so the
#: evidence is restricted to identifiers, class names, codes and counts.
REGISTRY_DOCUMENT_KEYS = {
    "alone",
    "classes",
    "ctid",
    "entities",
    "registry_references",
    "resolved",
}


def _registry() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return payload


def _registry_rollup(run: str) -> dict[str, Any]:
    """Recompute a rollup from the per-document records, not from the header."""
    codes: dict[str, int] = {}
    severities = {"ERROR": 0, "INFO": 0, "UNVERIFIABLE": 0, "WARNING": 0}
    with_error = 0
    with_nothing = 0
    for document in _registry()["documents"]:
        record = document[run]
        for code, count in record["codes"].items():
            codes[code] = codes.get(code, 0) + count
        for severity, count in record["severities"].items():
            severities[severity] += count
        if record["severities"]["ERROR"]:
            with_error += 1
        if not sum(record["severities"].values()):
            with_nothing += 1
    return {
        "codes": codes,
        "severities": severities,
        "documents_with_at_least_one_error": with_error,
        "documents_with_no_findings": with_nothing,
    }


def test_the_registry_evidence_carries_no_record_content() -> None:
    for document in _registry()["documents"]:
        unexpected = set(document) - REGISTRY_DOCUMENT_KEYS
        assert not unexpected, f"{document['ctid']}: unexpected keys {sorted(unexpected)}"


def test_the_registry_rollups_are_what_the_documents_say() -> None:
    payload = _registry()
    assert len(payload["documents"]) == payload["sampled"]
    for run in ("alone", "resolved"):
        assert _registry_rollup(run) == payload[f"rollup_{run}"], run


def test_the_registry_writeup_matches_the_evidence() -> None:
    """The prose numbers, recomputed rather than trusted.

    The share of findings that were non-answers, and the split of documents by
    what the tool was able to tell them, were both typed in and both wrong: 87%
    for a share that is 86%, and 81 documents said to have produced "only
    UNVERIFIABLE findings" when 9 of the 81 also produced a warning or a note.
    """
    payload = _registry()
    text = " ".join(REGISTRY_WRITEUP.read_text(encoding="utf-8").split())
    alone = payload["rollup_alone"]
    total = sum(alone["severities"].values())

    share = round(100 * alone["severities"]["UNVERIFIABLE"] / total)
    assert f"{share}% of the {total} findings" in text

    only_unverifiable = 0
    lesser = {"WARNING": 0, "INFO": 0}
    for document in payload["documents"]:
        severities = document["alone"]["severities"]
        if severities["ERROR"] or not sum(severities.values()):
            continue
        if severities["WARNING"] or severities["INFO"]:
            for name in lesser:
                lesser[name] += 1 if severities[name] else 0
        else:
            only_unverifiable += 1
    assert f"**{only_unverifiable} produced only UNVERIFIABLE findings**" in text
    assert f"{lesser['WARNING']} a `CTID_NOT_UUIDV4` warning" in text
    assert f"{lesser['INFO']} an `INVERSE_ONE_DIRECTION` note" in text


# -- the same 120 documents, re-validated after the concept-range fix ---------

REVALIDATED = (
    ROOT / "docs" / "findings" / "2026-08-15-published-registry-survey.revalidated-2026-08-21.json"
)
README = ROOT / "README.md"


def _revalidated() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(REVALIDATED.read_text(encoding="utf-8"))
    return payload


def _rollup(documents: list[dict[str, Any]], run: str) -> dict[str, Any]:
    """Recompute a rollup from per-document records, whatever file they came from."""
    codes: dict[str, int] = {}
    severities = {"ERROR": 0, "INFO": 0, "UNVERIFIABLE": 0, "WARNING": 0}
    with_error = 0
    for document in documents:
        record = document[run]
        for code, count in record["codes"].items():
            codes[code] = codes.get(code, 0) + count
        for severity, count in record["severities"].items():
            severities[severity] += count
        with_error += 1 if record["severities"]["ERROR"] else 0
    return {"codes": codes, "severities": severities, "with_error": with_error}


def _by_ctid(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The 2026-08-15 file orders documents by CTID; the harness now orders by page."""
    indexed = {document["ctid"]: document for document in documents}
    assert len(indexed) == len(documents), "a CTID appears twice"
    return indexed


def test_the_revalidation_is_the_same_draw_with_the_same_provenance() -> None:
    before, after = _registry(), _revalidated()
    assert set(_by_ctid(before["documents"])) == set(_by_ctid(after["documents"]))
    assert after["access"]["carried_from"] == REGISTRY.name
    for key in ("seed", "corpus_envelopes", "robots", "requests"):
        assert after["access"][key] == before["access"][key], key
    assert after["excluded"] == 0 and after["exclusions"] == []


def test_the_before_and_after_table_is_the_difference_between_the_two_files() -> None:
    """The concept-range fix was measured on this corpus; the table is that measurement."""
    before, after = _registry()["documents"], _revalidated()["documents"]
    text = " ".join(REGISTRY_WRITEUP.read_text(encoding="utf-8").split())
    n = len(before)
    rows = {
        "Documents with >= 1 ERROR (alone)": (
            f"{_rollup(before, 'alone')['with_error']} / {n}",
            f"**{_rollup(after, 'alone')['with_error']} / {n}**",
        ),
        "Documents with >= 1 ERROR (`--resolve`)": (
            f"{_rollup(before, 'resolved')['with_error']} / {n}",
            f"**{_rollup(after, 'resolved')['with_error']} / {n}**",
        ),
        "ERROR findings (alone)": (
            str(_rollup(before, "alone")["severities"]["ERROR"]),
            f"**{_rollup(after, 'alone')['severities']['ERROR']}**",
        ),
        "ERROR findings (`--resolve`)": (
            str(_rollup(before, "resolved")["severities"]["ERROR"]),
            f"**{_rollup(after, 'resolved')['severities']['ERROR']}**",
        ),
        "`CONCEPT_RANGE_CONFLICT` (INFO)": (
            "—",
            str(_rollup(after, "alone")["codes"]["CONCEPT_RANGE_CONFLICT"]),
        ),
    }
    for label, (was, now) in rows.items():
        assert f"| {label} | {was} | {now} |" in text, label


def test_the_only_change_is_range_violation_becoming_concept_range_conflict() -> None:
    """ "Every other finding, at every severity, is unchanged" is checked per document."""
    before, after = _registry()["documents"], _revalidated()["documents"]
    later = _by_ctid(after)
    reclassified_total = 0
    for was in before:
        now = later[was["ctid"]]
        for run in ("alone", "resolved"):
            old = dict(was[run]["codes"])
            new = dict(now[run]["codes"])
            moved = old.pop("RANGE_VIOLATION", 0) - new.pop("RANGE_VIOLATION", 0)
            assert new.pop("CONCEPT_RANGE_CONFLICT", 0) == moved, was["ctid"]
            assert old == new, was["ctid"]
            reclassified_total += moved if run == "alone" else 0
    assert reclassified_total == _rollup(after, "alone")["codes"]["CONCEPT_RANGE_CONFLICT"]


def test_the_readme_quotes_the_measurement_not_a_memory_of_it() -> None:
    before, after = _registry()["documents"], _revalidated()["documents"]
    text = " ".join(README.read_text(encoding="utf-8").split())
    n = len(before)
    failing_before = _rollup(before, "alone")["with_error"]
    failing_after = _rollup(after, "alone")["with_error"]
    assert f"**{failing_before} of {n} documents failing became {failing_after}**" in text
    moved = _rollup(after, "alone")["codes"]["CONCEPT_RANGE_CONFLICT"]
    assert (
        f"as all {moved} `RANGE_VIOLATION` findings became `CONCEPT_RANGE_CONFLICT` (INFO)" in text
    )
    errors_before = _rollup(before, "resolved")["severities"]["ERROR"]
    errors_after = _rollup(after, "resolved")["severities"]["ERROR"]
    assert f"`--resolve`, {errors_before} ERROR findings became {errors_after}" in text
