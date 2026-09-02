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

from ctdl_validate import validate_document
from ctdl_validate.schema import load_schema

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "EXPANSION-PLAN.md"

VOCABULARIES = ("ctdl", "ctdlasn")


CONCEPT_PROBE = {
    "@graph": [
        {
            "@id": "https://credentialengineregistry.org/resources/"
            "ce-11111111-1111-4111-8111-111111111111",
            "@type": "ceterms:CostProfile",
            # A real CTDL concept, from a scheme this property
            # does not name.
            "ceterms:directCostType": {
                "@type": "ceterms:CredentialAlignmentObject",
                "ceterms:targetNode": "credentialStat:Active",
            },
        }
    ]
}

DATE_PROBE = {
    "@graph": [
        {
            "@id": "https://credentialengineregistry.org/resources/"
            "ce-11111111-1111-4111-8111-111111111111",
            "@type": "ceterms:Credential",
            # ceterms:dateEffective is coerced to xsd:date.
            "ceterms:dateEffective": "the fourteenth of never",
        }
    ]
}

LANGUAGE_PROBE = {
    "@graph": [
        {
            "@id": "https://credentialengineregistry.org/resources/"
            "ce-11111111-1111-4111-8111-111111111111",
            "@type": "ceterms:Credential",
            # ceterms:name is a language map; this is a bare literal.
            "ceterms:name": "an untagged string",
        }
    ]
}

#: The class and property TERM_STATUS_PROBE is built from. Named here so
#: ``test_the_term_status_probe_names_terms_the_snapshot_calls_unstable`` can
#: hold them to the snapshot: a probe whose terms have since been stabilised
#: would stop exercising the declaration and say nothing about it.
#:
#: The probe this replaced named ``ceterms:audienceLevelType`` and
#: ``audLevel:BeginnerLevel``, neither of which the vendored snapshot declares
#: unstable. It could never have produced a term-status finding. That went
#: unnoticed because the row it probes claimed zero, and a probe for a
#: zero row is only ever asserted *not* to fire.
UNSTABLE_CLASS = "ceterms:Collection"
UNSTABLE_PROPERTY = "ceterms:lifeCycleStatusType"

TERM_STATUS_PROBE = {
    "@graph": [
        {
            "@id": "https://credentialengineregistry.org/resources/"
            "ce-11111111-1111-4111-8111-111111111111",
            # Both of these are declared vs:term_status vs:unstable in the
            # vendored encoding; the class check and the property check are
            # separate paths, so the probe uses one of each.
            "@type": UNSTABLE_CLASS,
            UNSTABLE_PROPERTY: {
                "@type": "ceterms:CredentialAlignmentObject",
                "ceterms:targetNode": "lifeCycle:Active",
            },
        }
    ]
}


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


def _read_column() -> dict[str, int]:
    """Label -> the "Read by a check today" column of the same table."""
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
        if len(cells) != 5 or not re.fullmatch(r"[0-9]+", cells[3]):
            continue
        found[cells[1]] = int(cells[3])
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


#: Row label -> the key a check would have to name in its own source to read
#: that declaration. Only consulted for a row whose "Read by a check today"
#: column still claims zero; a row that has moved off zero is held to the
#: behavioural probe below instead, which is the stronger instrument.
SOURCE_KEYS: dict[str, str] = {
    "Concepts declaring `skos:inScheme`": "skos:inScheme",
    "Terms declaring `vs:term_status`": "vs:term_status",
    'Context `{"@container": "@language"}` declarations': "@container",
}


def test_nothing_the_gap_table_still_claims_is_unread_is_read_by_a_check() -> None:
    """A row still claiming zero, held to the source tree.

    Each declaration the plan counts is named by the key a check would have to
    look up. While a row claims nothing reads it, no check module may name its
    key; the assertion turns itself off for a row that has moved off zero, so
    a landed phase does not have to delete a guard to go green.

    This is deliberately the weaker of the two guards on this column. A check
    can read every ``skos:inScheme`` declaration in the snapshot without the
    string appearing anywhere in it -- check 7 does exactly that -- so a row
    passing here proves little. ``test_the_read_column_says_what_the_validator
    _actually_does`` is what actually holds the number, in both directions.
    """
    checks = ROOT / "src" / "ctdl_validate" / "checks"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(checks.glob("*.py")))
    read = _read_column()
    for label, key in SOURCE_KEYS.items():
        assert label in read, f"the plan's table has no row for {label}"
        if read[label]:
            continue
        assert key not in source, f"a check now reads {key}; update the expansion plan's gap table"


#: Row label -> (a payload exercising the declaration, a string that a finding
#: resting on that declaration would have to cite).
#:
#: The marker is looked for in the *rule citation of a finding the validator
#: actually produced*, not in the source tree. That is sound here because of
#: the project's first invariant: every check traces to a vendored declaration
#: or a quoted prose rule, and the finding carries that citation in its output.
#: A check that starts reading one of these declarations cannot report on it
#: without naming it.
#:
#: This replaced a version that searched the check modules for the term name.
#: That guard could not fail: a check can read every ``skos:inScheme``
#: declaration in the snapshot without the string ``skos:inScheme`` appearing
#: anywhere in it, so it would have stayed green through exactly the change it
#: existed to catch.
PROBES: dict[str, tuple[dict[str, Any], str]] = {
    "Properties declaring `meta:targetScheme`": (
        CONCEPT_PROBE,
        "meta:targetScheme",
    ),
    "Concept schemes": (CONCEPT_PROBE, "meta:targetScheme"),
    "Concepts declaring `skos:inScheme`": (CONCEPT_PROBE, "skos:inScheme"),
    "Context datatype coercions": (DATE_PROBE, "xsd:date"),
    'Context `{"@container": "@language"}` declarations': (LANGUAGE_PROBE, "@language"),
    "Terms declaring `vs:term_status`": (TERM_STATUS_PROBE, "term_status"),
}


def _cites(payload: dict[str, Any], marker: str) -> bool:
    """Did any finding this payload produced cite ``marker``?"""
    return any(marker in f.rule.citation for f in validate_document(payload))


def test_the_read_column_says_what_the_validator_actually_does() -> None:
    """A row claiming zero must produce no finding resting on that declaration.

    When a phase lands and starts reading one of these, this fails, which is
    the reminder to move that row's Read column off zero rather than leaving
    the plan claiming a gap it closed.
    """
    read = _read_column()
    for label, (payload, marker) in PROBES.items():
        assert label in read, f"the plan's table has no row for {label}"
        cited = _cites(payload, marker)
        if read[label] == 0:
            assert not cited, (
                f"the plan says nothing reads {label}, but a finding cites {marker}. "
                "Move that row's Read column off zero."
            )
        else:
            assert cited, (
                f"the plan says {read[label]} for {label}, but no finding cites "
                f"{marker}. Either the check went away or the row claims work that "
                "is not there."
            )


def test_the_term_status_probe_names_terms_the_snapshot_calls_unstable() -> None:
    """A probe built on a term that is not unstable proves nothing about check 9.

    The probes for the rows still claiming zero are only ever asserted *not*
    to fire, so a payload that could never have fired looks identical to one
    the validator correctly ignores. This is the direct check: the two terms
    the probe is built from are the ones the vendored encoding declares
    ``vs:unstable``, read from the index rather than trusted.
    """
    unstable = load_schema().unstable
    for term in (UNSTABLE_CLASS, UNSTABLE_PROPERTY):
        assert term in unstable, (
            f"TERM_STATUS_PROBE is built from {term}, which the vendored encoding does "
            "not declare vs:unstable. The probe would exercise nothing."
        )


def test_every_row_of_the_table_has_a_probe() -> None:
    """A row nobody probes is a claim nothing is holding to account."""
    unprobed = set(_published_table()) - set(PROBES)
    assert not unprobed, f"the plan's table has rows with no probe: {unprobed}"
