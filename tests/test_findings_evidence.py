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
