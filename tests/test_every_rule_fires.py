"""Every rule the validator can emit must fire against a document that trips it.

A rule that never fires against input that should trip it is the sharpest form
of a check that cannot fail. Three of this tool's rules were in exactly that
state when this file was written: ``CTID_MALFORMED`` (ERROR),
``REF_BARE_CTID`` (WARNING) and ``REF_NOT_IRI`` (WARNING) were documented in
the README's rule table, emitted by the source, and asserted by no test in the
suite. Deleting any one of them left the whole gate set green. The 90% coverage
floor could not see it, because three missing rules are four missing lines out
of eighteen hundred.

Line coverage is the wrong instrument for that question. This file uses the
right one: it counts *rules*, and every count is backed by a document the tool
is actually run over.

It fails in four independent directions:

1. a code the check modules can emit that ``TRIPWIRES`` does not list;
2. a code ``TRIPWIRES`` lists that the check modules no longer emit, so a
   stale entry cannot outlive the rule it was written for;
3. a code whose listed document does not produce it, at the listed severity;
4. a code the README's rule table does not list, or lists and the source does
   not emit.

Direction 3 is the one that matters. The table is not a list of strings that
agrees with another list of strings; it is a list of *payloads*, each of which
is validated, so an entry can only stay green while the rule it names still
does something.

Direction 4 is here because it has already gone wrong once:
``VERSION_RANGE_CONFLICT`` shipped implemented and undocumented, and nothing
related the README's table to the code.

Reading the codes out of the source is by AST, not by regex. A ``[A-Z_]+``
scan silently omits ``CTID_NOT_UUIDV4``, because the code carries a digit --
which is how a rule goes missing from a list of rules.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "src" / "ctdl_validate" / "checks"
README = ROOT / "README.md"

FRAMEWORK = "https://credentialengineregistry.org/resources/ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37"
COMPETENCY = (
    "https://credentialengineregistry.org/resources/ce-5e3de882-3b49-421b-b623-695c63587f4f"
)
COURSE = "https://credentialengineregistry.org/resources/ce-59e8d15f-7895-4346-a5a8-7a0739a3d344"
ORGANIZATION = (
    "https://credentialengineregistry.org/resources/ce-79298677-d0e4-4799-853a-a633d9071826"
)


# -- what the source can emit --------------------------------------------------


def codes_in_source() -> set[str]:
    """Every finding code the check modules construct, read out of the source."""
    found: set[str] = set()
    for path in sorted(CHECKS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.keyword) or node.arg != "code":
                continue
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str), (
                f"{path.name}: a finding code built at run time rather than written as a "
                "string literal cannot be enumerated from the source, so this gate would "
                "not be able to see it"
            )
            found.add(node.value.value)
    return found


def codes_in_readme() -> set[str]:
    """Every code named in the README's 'What it checks' rule table."""
    text = README.read_text(encoding="utf-8")
    table = text.split("| # | Check | Codes | Rule source |", 1)
    assert len(table) == 2, "the README's rule table has moved or changed its header"
    rows = []
    for line in table[1].splitlines():
        if not line.strip():
            continue  # the newline the header split leaves behind
        if not line.startswith("|"):
            break
        rows.append(line)
    assert rows, "the README's rule table has no rows under its header"
    cells = [line.split("|") for line in rows if line.count("|") >= 5]
    return {code for row in cells for code in re.findall(r"`([A-Z0-9_]+)`", row[3])}


# -- a document per rule -------------------------------------------------------


@dataclass(frozen=True)
class Tripwire:
    """A document that trips exactly one named rule, and the severity it earns."""

    severity: Severity
    payload: Any
    #: A neighbouring document, written to a file and passed with ``--resolve``.
    #: Only the resolution rules need one.
    resolve: Any = field(default=None)


def _entity(**fields: Any) -> dict[str, Any]:
    return {"@graph": [fields]}


def _competency_pointing_at(value: Any) -> dict[str, Any]:
    """A competency whose ``isPartOf`` carries whatever is handed in.

    The identifier-kind and reference rules all turn on the *kind* of thing
    written where an entity identifier belongs, so one shape reaches all six.
    """
    return _entity(
        **{
            "@id": COMPETENCY,
            "@type": "ceasn:Competency",
            "ceterms:ctid": "ce-5e3de882-3b49-421b-b623-695c63587f4f",
            "ceasn:isPartOf": value,
        }
    )


#: A term from one of CTDL's own concept schemes, encoded the way the Registry
#: encodes it: as a CredentialAlignmentObject, on a property CTDL ranges on
#: skos:Concept. See rules.concept_range_conflict_rule.
ALIGNMENT_VALUE = {
    "@type": "ceterms:CredentialAlignmentObject",
    "ceterms:framework": "https://credreg.net/ctdl/terms/CreditUnit",
    "ceterms:targetNode": "creditUnit:SemesterHour",
}

TRIPWIRES: dict[str, Tripwire] = {
    # -- check 1: CTID grammar -------------------------------------------------
    "CTID_BARE_UUID": Tripwire(
        Severity.ERROR,
        _entity(
            **{
                "@type": "ceasn:CompetencyFramework",
                "ceterms:ctid": "177f4c85-4efe-401d-acdd-1ea4adeeaf37",
            }
        ),
    ),
    "CTID_MALFORMED": Tripwire(
        Severity.ERROR,
        _entity(**{"@type": "ceasn:CompetencyFramework", "ceterms:ctid": "not-a-ctid"}),
    ),
    "CTID_UPPERCASE": Tripwire(
        Severity.WARNING,
        _entity(
            **{
                "@type": "ceterms:Certification",
                "ceterms:ctid": "ce-B55F88E3-DFD4-430B-AB47-3E5F9986E1E4",
            }
        ),
    ),
    "CTID_NOT_UUIDV4": Tripwire(
        Severity.WARNING,
        _entity(
            **{
                "@type": "ceterms:Certification",
                # Version nibble 1 where the published grammar says 4.
                "ceterms:ctid": "ce-59e8d15f-7895-1346-a5a8-7a0739a3d344",
            }
        ),
    ),
    "REGISTRY_URI_MALFORMED": Tripwire(
        Severity.ERROR,
        _entity(
            **{
                "@id": "https://credentialengineregistry.org/resources/not-a-ctid-at-all",
                "@type": "ceasn:CompetencyFramework",
            }
        ),
    ),
    "CTID_URI_MISMATCH": Tripwire(
        Severity.ERROR,
        _entity(
            **{
                "@id": COURSE,
                "@type": "ceterms:Course",
                # A shape-valid CTID that is not the one in this entity's @id.
                "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
            }
        ),
    ),
    # -- check 2: identifier kind ---------------------------------------------
    "REF_BARE_UUID": Tripwire(
        Severity.ERROR,
        _competency_pointing_at("177f4c85-4efe-401d-acdd-1ea4adeeaf37"),
    ),
    "REF_BARE_CTID": Tripwire(
        Severity.WARNING,
        _competency_pointing_at("ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37"),
    ),
    "REF_NOT_IRI": Tripwire(
        Severity.WARNING,
        _competency_pointing_at("Example Widgetry Competency Framework"),
    ),
    # -- check 3: reference resolution ----------------------------------------
    "REF_UNRESOLVED_BNODE": Tripwire(
        Severity.ERROR,
        _competency_pointing_at("_:a-framework-this-payload-never-defines"),
    ),
    "REF_OUTSIDE_PAYLOAD": Tripwire(
        Severity.UNVERIFIABLE,
        _competency_pointing_at(FRAMEWORK),
    ),
    "REF_RESOLVED_SUPPLIED": Tripwire(
        Severity.INFO,
        _competency_pointing_at(FRAMEWORK),
        resolve=_entity(
            **{
                "@id": FRAMEWORK,
                "@type": "ceasn:CompetencyFramework",
                "ceterms:ctid": "ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37",
            }
        ),
    ),
    # -- check 4: domain and range --------------------------------------------
    "UNKNOWN_CLASS": Tripwire(
        Severity.WARNING,
        _entity(**{"@id": FRAMEWORK, "@type": "ceterms:NotADeclaredClass"}),
    ),
    "UNKNOWN_PROPERTY": Tripwire(
        Severity.WARNING,
        _entity(
            **{
                "@id": FRAMEWORK,
                "@type": "ceasn:CompetencyFramework",
                "ceterms:notADeclaredProperty": "anything",
            }
        ),
    ),
    "DOMAIN_VIOLATION": Tripwire(
        Severity.ERROR,
        # ceasn:competencyText is declared for ceasn:Competency, not for a
        # framework.
        _entity(
            **{
                "@id": FRAMEWORK,
                "@type": "ceasn:CompetencyFramework",
                "ceasn:competencyText": {"en-US": "A framework is not a competency"},
            }
        ),
    ),
    "RANGE_VIOLATION": Tripwire(
        Severity.ERROR,
        {
            "@graph": [
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    "ceasn:isPartOf": ORGANIZATION,
                },
                {"@id": ORGANIZATION, "@type": "ceterms:Organization"},
            ]
        },
    ),
    "ISPARTOF_FRAMEWORK_MISMATCH": Tripwire(
        Severity.WARNING,
        {
            "@graph": [
                {"@id": FRAMEWORK, "@type": "ceasn:CompetencyFramework"},
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    # A Registry IRI that is not the framework sitting beside it.
                    "ceasn:isPartOf": ORGANIZATION,
                },
            ]
        },
    ),
    "RANGE_DOCS_CONFLICT": Tripwire(
        Severity.INFO,
        {
            "@graph": [
                {"@id": FRAMEWORK, "@type": "ceasn:CompetencyFramework"},
                # isChildOf does not declare CompetencyFramework in its range,
                # and Credential Engine's own guidance points it there.
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    "ceasn:isChildOf": FRAMEWORK,
                },
            ]
        },
    ),
    "CONCEPT_RANGE_CONFLICT": Tripwire(
        Severity.INFO,
        _entity(
            **{
                "@id": COURSE,
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:creditValue": [
                    {
                        "@type": "ceterms:ValueProfile",
                        "ceterms:creditUnitType": [ALIGNMENT_VALUE],
                        "schema:value": 3.0,
                    }
                ],
            }
        ),
    ),
    "VERSION_RANGE_CONFLICT": Tripwire(
        Severity.INFO,
        {
            "@graph": [
                {
                    "@id": COURSE,
                    "@type": "ceterms:TransferValueProfile",
                    "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                    "ceterms:previousVersion": [ORGANIZATION],
                },
                {
                    "@id": ORGANIZATION,
                    "@type": "ceterms:TransferValueProfile",
                    "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
                },
            ]
        },
    ),
    # -- check 5: inverses -----------------------------------------------------
    "INVERSE_ONE_DIRECTION": Tripwire(
        Severity.INFO,
        # ceasn:hasChild/ceasn:isChildOf, which the encoding does declare with
        # owl:inverseOf. hasTopChild/isTopChildOf read like a pair and carry no
        # such declaration, so the tool does not treat them as one and a
        # tripwire built on them would never fire (README, conflict 2).
        {
            "@graph": [
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    "ceasn:hasChild": [ORGANIZATION],
                },
                # Says nothing about isChildOf, which hasChild's declared
                # inverse would have it say.
                {"@id": ORGANIZATION, "@type": "ceasn:Competency"},
            ]
        },
    ),
    "INVERSE_MISMATCH": Tripwire(
        Severity.ERROR,
        {
            "@graph": [
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    "ceasn:hasChild": [ORGANIZATION],
                },
                {
                    "@id": ORGANIZATION,
                    "@type": "ceasn:Competency",
                    # Points back at something other than the competency that
                    # claims it as a child.
                    "ceasn:isChildOf": COURSE,
                },
                {"@id": COURSE, "@type": "ceasn:Competency"},
            ]
        },
    ),
    # -- check 6, identity ------------------------------------------------
    "ID_DECLARED_MORE_THAN_ONCE": Tripwire(
        Severity.INFO,
        # One identifier claimed by two node objects. The parser reads them as
        # a single entity, the union of their @type values and properties, and
        # says so rather than silently keeping whichever parsed first
        # (ADR-0005). INFO: the merge is a disclosure, not a defect.
        {
            "@graph": [
                {
                    "@id": COMPETENCY,
                    "@type": "ceasn:Competency",
                    "ceterms:ctid": "ce-5e3de882-3b49-421b-b623-695c63587f4f",
                },
                {"@id": COMPETENCY, "@type": "ceasn:Competency"},
            ]
        },
    ),
    # -- check 7, concept scheme membership ------------------------------------
    "CONCEPT_OUTSIDE_SCHEME": Tripwire(
        Severity.WARNING,
        # credentialStat:Active is a real CTDL concept the snapshot declares,
        # in ceterms:CredentialStatus. ceterms:directCostType draws from
        # ceterms:CostType. Both declarations are vendored, so this is a term
        # from the wrong vocabulary rather than a term the tool cannot place.
        _entity(
            **{
                "@id": ORGANIZATION,
                "@type": "ceterms:CostProfile",
                "ceterms:directCostType": {
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:targetNode": "credentialStat:Active",
                },
            }
        ),
    ),
    "CONCEPT_OUTSIDE_SNAPSHOT": Tripwire(
        Severity.UNVERIFIABLE,
        # The common shape in published documents: a scheme-bound property
        # naming an external framework the tool has not vendored. UNVERIFIABLE
        # because the tool did not check it, not because it is wrong.
        _entity(
            **{
                "@id": ORGANIZATION,
                "@type": "ceterms:Occupation",
                "ceterms:occupationType": {
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:targetNode": "https://www.onetonline.org/link/summary/15-1244.00",
                },
            }
        ),
    ),
    "CONCEPT_NOT_IDENTIFIED": Tripwire(
        Severity.UNVERIFIABLE,
        # An alignment object that names its term in words and carries no
        # ceterms:targetNode, so there is no identifier to place in a scheme.
        _entity(
            **{
                "@id": ORGANIZATION,
                "@type": "ceterms:CostProfile",
                "ceterms:directCostType": {
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:targetNodeName": {"en-US": "Tuition"},
                },
            }
        ),
    ),
    # -- check 8, language-map shape -------------------------------------------
    "LANGUAGE_MAP_EXPECTED": Tripwire(
        Severity.WARNING,
        # ceterms:name is declared {"@container": "@language"} in the vendored
        # context, and this value is a bare literal, so it states no language.
        _entity(
            **{
                "@id": COURSE,
                "@type": "ceterms:Course",
                "ceterms:ctid": "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344",
                "ceterms:name": "Introduction to Widgetry",
            }
        ),
    ),
    # -- check 9, term status --------------------------------------------------
    "TERM_UNSTABLE": Tripwire(
        Severity.INFO,
        # ceterms:Collection is declared vs:term_status vs:unstable in the
        # published encoding. Disclosed as a fact about the vocabulary, not a
        # defect in the document.
        _entity(
            **{
                "@id": ORGANIZATION,
                "@type": "ceterms:Collection",
                "ceterms:ctid": "ce-79298677-d0e4-4799-853a-a633d9071826",
            }
        ),
    ),
}


def _findings(tripwire: Tripwire, tmp_path: Path) -> list[Any]:
    resolve = None
    if tripwire.resolve is not None:
        neighbour = tmp_path / "neighbour.json"
        neighbour.write_text(json.dumps(tripwire.resolve), encoding="utf-8")
        resolve = [neighbour]
    return validate_document(tripwire.payload, resolve)


# -- the four directions this can fail in --------------------------------------


def test_every_code_the_source_emits_has_a_document_that_trips_it() -> None:
    """Direction 1: a new rule cannot ship without a payload that reaches it."""
    missing = sorted(codes_in_source() - set(TRIPWIRES))
    assert missing == [], (
        "these rules are emitted by the check modules and no document in this "
        f"file trips them, so nothing would notice if they stopped firing: {missing}"
    )


def test_no_tripwire_outlives_the_rule_it_was_written_for() -> None:
    """Direction 2: a stale entry cannot sit here naming a deleted rule."""
    stale = sorted(set(TRIPWIRES) - codes_in_source())
    assert stale == [], (
        "these codes are listed here and no check module emits them any more: "
        f"{stale}. Remove the entry, or the rule was deleted by accident."
    )


@pytest.mark.parametrize("code", sorted(TRIPWIRES))
def test_the_rule_fires_at_the_severity_it_is_documented_at(code: str, tmp_path: Path) -> None:
    """Direction 3: the behavioural half. Each rule is run, not just named."""
    tripwire = TRIPWIRES[code]
    findings = _findings(tripwire, tmp_path)
    hits = [f for f in findings if f.code == code]
    assert hits, (
        f"{code} did not fire against the document written to trip it. "
        f"What did fire: {sorted({f.code for f in findings})}"
    )
    assert all(f.severity is tripwire.severity for f in hits), (
        f"{code} fired at {sorted({f.severity.value for f in hits})}, not {tripwire.severity.value}"
    )


def test_the_readme_rule_table_lists_exactly_the_rules_the_source_emits() -> None:
    """Direction 4: VERSION_RANGE_CONFLICT shipped implemented and undocumented."""
    source, documented = codes_in_source(), codes_in_readme()
    undocumented = sorted(source - documented)
    unimplemented = sorted(documented - source)
    assert undocumented == [], (
        f"the check modules emit these and the README's rule table does not list "
        f"them: {undocumented}"
    )
    assert unimplemented == [], (
        f"the README's rule table lists these and no check module emits them: {unimplemented}"
    )


def test_every_finding_a_tripwire_produces_carries_its_citation(tmp_path: Path) -> None:
    """No rule may reach a report without saying where it came from."""
    for code, tripwire in sorted(TRIPWIRES.items()):
        for finding in _findings(tripwire, tmp_path):
            assert finding.rule.citation.strip(), f"{code}: {finding.code} cites nothing"
            assert finding.rule.url.strip(), f"{code}: {finding.code} has no source URL"
            assert finding.rule.retrieved.strip(), f"{code}: {finding.code} has no retrieval date"
