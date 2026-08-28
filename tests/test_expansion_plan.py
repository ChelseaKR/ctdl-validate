"""The expansion plan's measured gap table must agree with the vendored files.

The plan proposes work sized by how many published declarations no check
reads. If those counts drift from the snapshot -- because the snapshot was
refreshed, or because someone adjusted a number to suit an argument -- the
plan is arguing from figures the repository can no longer produce. So the
table is recomputed here rather than trusted, the same way
``test_findings_evidence.py`` recomputes the findings tables.

This gate deliberately says nothing about whether the counts are large enough
to justify the work. It says only that they are the counts.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "EXPANSION-PLAN.md"

VOCABULARIES = ("ctdl", "ctdlasn")


def _vendored(relpath: str) -> Any:
    path = resources.files("ctdl_validate").joinpath("vendor").joinpath(relpath)
    with path.open("rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def _nodes() -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for vocabulary in VOCABULARIES:
        graph: list[dict[str, Any]] = _vendored(f"{vocabulary}/schema.json")["@graph"]
        nodes.extend(graph)
    return nodes


def _context_terms() -> dict[str, dict[str, Any]]:
    """Term name -> its definition object, across both vendored contexts.

    Keyed by term rather than accumulated as a list because the two context
    files carry the same term definitions: counting entries would report each
    coerced property twice. ``test_the_two_contexts_do_not_disagree`` holds
    that merge to the thing that makes it safe.
    """
    terms: dict[str, dict[str, Any]] = {}
    for vocabulary in VOCABULARIES:
        context: dict[str, Any] = _vendored(f"{vocabulary}/context.json")["@context"]
        for name, value in context.items():
            if isinstance(value, dict):
                terms[name] = value
    return terms


def _is_a(node: dict[str, Any], term: str) -> bool:
    declared = node.get("@type")
    if isinstance(declared, list):
        return term in declared
    return declared == term


def _counts() -> dict[str, int]:
    nodes = _nodes()
    terms = _context_terms()
    coerced = [
        term
        for term in terms.values()
        if isinstance(term.get("@type"), str) and term["@type"] != "@id"
    ]
    return {
        # Distinct properties, not declaration nodes: CTDL and CTDL-ASN both
        # declare meta:targetScheme on three of the same ceterms: properties,
        # naming the same scheme each time, so counting nodes would report 51
        # for 48 things a check could look up.
        "Properties declaring `meta:targetScheme`": len(
            {n["@id"] for n in nodes if _is_a(n, "rdf:Property") and "meta:targetScheme" in n}
        ),
        "Concept schemes": sum(1 for n in nodes if _is_a(n, "skos:ConceptScheme")),
        "Concepts declaring `skos:inScheme`": sum(
            1 for n in nodes if _is_a(n, "skos:Concept") and "skos:inScheme" in n
        ),
        "Context datatype coercions": len(coerced),
        'Context `{"@container": "@language"}` declarations': sum(
            1 for term in terms.values() if term.get("@container") == "@language"
        ),
        "Terms declaring `vs:term_status`": sum(1 for n in nodes if "vs:term_status" in n),
    }


def _published_table() -> dict[str, int]:
    """Label -> the Published column, from the plan's measured gap table.

    Bounded to the "The measured gap" section. The plan carries a second
    three-column table (the sequencing one) whose middle cell is sometimes a
    phase number, and an unbounded scan would silently read rows out of it.
    """
    found: dict[str, int] = {}
    inside = False
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## The measured gap"
            continue
        if line.startswith("### "):
            inside = False
        if not inside:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != 5 or not re.fullmatch(r"[0-9]+", cells[2]):
            continue
        found[cells[1]] = int(cells[2])
    return found


def test_every_row_of_the_measured_gap_table_is_recomputed() -> None:
    published = _published_table()
    expected = _counts()
    assert published, "the plan's measured gap table was not found or has no numeric rows"
    for label, count in expected.items():
        assert label in published, f"the plan's table has no row for {label}"
        assert published[label] == count, (
            f"the plan says {published[label]} for {label}; the vendored files say {count}"
        )


def test_the_table_states_no_row_the_snapshot_cannot_produce() -> None:
    """A row nothing recomputes is a number nothing is holding to account."""
    unaccounted = set(_published_table()) - set(_counts())
    assert not unaccounted, f"the plan's table has rows this test does not recompute: {unaccounted}"


def test_the_two_contexts_do_not_disagree() -> None:
    """Merging the two contexts by term name is only safe while they agree.

    Phase 3 of the plan proposes reading the datatype coercions once rather
    than per vocabulary, and the gap table counts them once. Both rest on the
    vendored contexts declaring the same thing for every shared term. They do
    today: 87 coercions and 80 language maps, identical in both files. A
    re-vendoring that broke that would silently halve or double a count, so it
    fails here instead.
    """
    per_file: list[dict[str, dict[str, Any]]] = []
    for vocabulary in VOCABULARIES:
        context: dict[str, Any] = _vendored(f"{vocabulary}/context.json")["@context"]
        per_file.append({k: v for k, v in context.items() if isinstance(v, dict)})
    first, second = per_file
    shared = set(first) & set(second)
    disagreements = sorted(term for term in shared if first[term] != second[term])
    assert not disagreements, (
        f"the vendored contexts define these terms differently: {disagreements}"
    )


def test_nothing_in_the_gap_table_is_read_by_a_check_yet() -> None:
    """The table's second column claims zero. Hold it to the source tree.

    Each declaration the plan counts is named by the key a check would have to
    look up. When a phase lands and starts reading one, this test fails, which
    is the reminder to move that row's "Read by a check today" to a real
    number rather than leaving the plan claiming a gap it closed.
    """
    checks = ROOT / "src" / "ctdl_validate" / "checks"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(checks.glob("*.py")))
    for key in ("skos:inScheme", "vs:term_status", "@container"):
        assert key not in source, f"a check now reads {key}; update the expansion plan's gap table"
