"""Every code this package can emit must fire against a document that trips it.

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

**And it has to count the whole package, out loud.** For its first year this
file read its universe from ``CHECKS.glob("*.py")`` alone. That is 28 of the
48 finding codes ``src/`` constructs; the other 20 are extraction notes under
``extract/``, and one of them -- ``JSONLD_CONTEXT_UNRESOLVED`` -- appeared in
exactly one file in the whole repository, its own emit site. Deleting its
branch left 582 tests green at 95.73% coverage. Nothing was wrong with the
rules this file listed; the problem was that the gate never said what share of
the package it had examined, so a whole directory being outside its universe
looked identical to a directory with nothing in it. That is the defect this
tool exists to report, in the gate that reports it.

So there are now two tripwire tables and one reconciliation between them:

- ``TRIPWIRES`` -- validation rules, from ``checks/``, each a JSON-LD payload
  run through :func:`ctdl_validate.validate_document`;
- ``EXTRACT_TRIPWIRES`` -- extraction notes, from ``extract/``, each an HTML
  page run through :func:`ctdl_validate.extract.extract_from_html`;
- :func:`test_every_finding_code_in_the_package_is_inside_one_of_these_tables`,
  which walks **the whole package** and fails on any code neither table's
  universe covers. A new module that starts emitting codes fails the gate
  rather than silently shrinking the denominator.

Each table fails in four independent directions:

1. a code its modules can emit that the table does not list;
2. a code the table lists that its modules no longer emit, so a stale entry
   cannot outlive the rule it was written for;
3. a code whose listed document does not produce it, at the listed severity;
4. a code the README does not list, or lists and the source does not emit.

Direction 3 is the one that matters. The table is not a list of strings that
agrees with another list of strings; it is a list of *payloads*, each of which
is run, so an entry can only stay green while the rule it names still does
something.

Direction 4 is here because it has already gone wrong once:
``VERSION_RANGE_CONFLICT`` shipped implemented and undocumented, and nothing
related the README's table to the code.

Reading the codes out of the source is by AST, not by regex. A ``[A-Z_]+``
scan silently omits ``CTID_NOT_UUIDV4``, because the code carries a digit --
which is how a rule goes missing from a list of rules.

The census both tables produce is printed on every run by
``tests/conftest.py``, passing or failing, because a green line that does not
say what it examined is how this went unnoticed for a year.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document
from ctdl_validate.extract import extract_from_html
from ctdl_validate.extract.crosswalk import load_crosswalk

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "ctdl_validate"
CHECKS = PACKAGE / "checks"
EXTRACT = PACKAGE / "extract"
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

#: Modules that carry a ``code=`` keyword whose value is *not* a string
#: literal, each with the written reason it declares no rule. Self-limiting in
#: both directions: an entry naming a module that no longer has one fails, and
#: a module that grows one without an entry fails.
#:
#: This list exists because widening the scan from ``checks/`` to the whole
#: package brought a deserializer into scope. It is not an exemption from
#: firing; it is a statement that there is no rule here to fire.
CODE_IS_NOT_A_DECLARATION: dict[str, str] = {
    "compare.py": (
        "``diff`` rebuilds Finding objects out of a report it is handed, so this "
        "``code=`` carries whatever that report said. It declares no rule, and a "
        "code reaching a reader only through here is a code nothing emits."
    ),
}


def _scan(paths: list[Path]) -> tuple[dict[str, set[str]], set[str]]:
    """Finding codes constructed under ``paths``, and the modules that build one
    at run time rather than writing it as a string literal.

    By AST rather than by regex, because a ``[A-Z_]+`` scan omits
    ``CTID_NOT_UUIDV4`` -- the code carries a digit.
    """
    found: dict[str, set[str]] = {}
    unreadable: set[str] = set()
    assert paths, "this scan was handed no modules at all, so it can only report nothing"
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.keyword) or node.arg != "code":
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                found.setdefault(node.value.value, set()).add(path.name)
            else:
                unreadable.add(path.name)
    return found, unreadable


def _modules(directory: Path) -> list[Path]:
    paths = sorted(p for p in directory.glob("*.py") if p.name != "__init__.py")
    assert paths, f"{directory} holds no modules, so a scan of it cannot fail on anything"
    return paths


def rule_codes_in_source() -> set[str]:
    """Every finding code the check modules construct, read out of the source."""
    found, unreadable = _scan(_modules(CHECKS))
    assert not unreadable, (
        f"{sorted(unreadable)}: a finding code built at run time rather than written as a "
        "string literal cannot be enumerated from the source, so this gate would "
        "not be able to see it"
    )
    return set(found)


def note_codes_in_source() -> set[str]:
    """Every extraction note code the extract modules construct."""
    found, unreadable = _scan(_modules(EXTRACT))
    assert not unreadable, (
        f"{sorted(unreadable)}: an extraction note code built at run time cannot be "
        "enumerated from the source, so this gate would not be able to see it"
    )
    return set(found)


def codes_in_package() -> dict[str, set[str]]:
    """Every finding code any module in the package constructs, by module name."""
    found, _ = _scan(sorted(PACKAGE.rglob("*.py")))
    return found


def census() -> str:
    """One line per universe, for the terminal summary. Printed on every run."""
    rules, notes, package = rule_codes_in_source(), note_codes_in_source(), codes_in_package()
    return (
        f"rule codes: {len(TRIPWIRES)} of {len(rules)} tripped by a validated payload; "
        f"note codes: {len(EXTRACT_TRIPWIRES)} of {len(notes)} tripped by an extracted page; "
        f"{len(rules | notes)} of {len(package)} finding codes in src/ctdl_validate "
        f"are inside one of the two universes"
    )


def _readme_table(header: str, column: int, cells_per_row: int) -> set[str]:
    """The codes written in one column of one README table, by its header row."""
    text = README.read_text(encoding="utf-8")
    table = text.split(header, 1)
    assert len(table) == 2, f"the README table headed {header!r} has moved or changed"
    rows = []
    for line in table[1].splitlines():
        if not line.strip():
            continue  # the newline the header split leaves behind
        if not line.startswith("|"):
            break
        rows.append(line)
    assert rows, f"the README table headed {header!r} has no rows under its header"
    cells = [line.split("|") for line in rows if line.count("|") >= cells_per_row]
    codes = {code for row in cells for code in re.findall(r"`([A-Z0-9_]+)`", row[column])}
    assert codes, f"the README table headed {header!r} names no codes at all"
    return codes


def codes_in_readme() -> set[str]:
    """Every code named in the README's 'What it checks' rule table."""
    return _readme_table("| # | Check | Codes | Rule source |", 3, 5)


def note_codes_in_readme() -> set[str]:
    """Every code named in the README's 'What extraction reports' note table."""
    return _readme_table("| Code | Severity | What it says |", 1, 4)


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
    missing = sorted(rule_codes_in_source() - set(TRIPWIRES))
    assert missing == [], (
        "these rules are emitted by the check modules and no document in this "
        f"file trips them, so nothing would notice if they stopped firing: {missing}"
    )


def test_no_tripwire_outlives_the_rule_it_was_written_for() -> None:
    """Direction 2: a stale entry cannot sit here naming a deleted rule."""
    stale = sorted(set(TRIPWIRES) - rule_codes_in_source())
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
    source, documented = rule_codes_in_source(), codes_in_readme()
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


# -- extraction notes: a page per note ----------------------------------------
#
# The second universe. Extraction reads a page's own structured markup and
# reports what it could not carry across; every one of those reports is a note
# code, and until this table existed twenty of them were outside the only gate
# that counts codes rather than lines.


EXTRACT_SOURCE = "https://example.edu/programs/welding"


@dataclass(frozen=True)
class PageTripwire:
    """A page that trips exactly one named extraction note, and its severity."""

    severity: Severity
    body: str
    #: The vendored crosswalk holds no ambiguous class today, so the one note
    #: that needs one substitutes a crosswalk rather than pretending a real
    #: page can reach it. Stated here rather than hidden in a fixture.
    equivalent_class: dict[str, tuple[str, ...]] | None = None


def _block(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


EXTRACT_TRIPWIRES: dict[str, PageTripwire] = {
    # -- reading the markup ---------------------------------------------------
    "NO_STRUCTURED_DATA": PageTripwire(
        Severity.WARNING,
        "<h1>Welding Certificate</h1><p>Sixteen weeks, evenings.</p>",
    ),
    "JSONLD_PARSE_ERROR": PageTripwire(
        Severity.WARNING,
        _block('{"@context":"https://schema.org", "@type": "Course",'),
    ),
    "JSONLD_CONTEXT_UNRESOLVED": PageTripwire(
        Severity.WARNING,
        # A @context this tool does not recognize. Its unprefixed keys are left
        # unread rather than resolved against a vocabulary nobody declared.
        _block('{"@context":"https://example.org/ctx/v1","@type":"Course","name":"Welding"}'),
    ),
    "MICRODATA_NAME_UNRESOLVED": PageTripwire(
        Severity.WARNING,
        # A bare itemprop on an item with no itemtype: proprietary to the
        # author by the HTML standard, so there is no vocabulary to read it in.
        '<div itemscope><span itemprop="name">Widgetry College</span></div>',
    ),
    "MICRODATA_ITEMREF": PageTripwire(
        Severity.WARNING,
        '<div itemscope itemtype="https://schema.org/Organization" itemref="extra">'
        '<span itemprop="name">Widgetry College</span></div><p id="extra"></p>',
    ),
    "EMPTY_VALUE": PageTripwire(
        Severity.INFO,
        '<div itemscope itemtype="https://schema.org/Organization">'
        '<span itemprop="name"></span></div>',
    ),
    "RDFA_TERM_UNRESOLVED": PageTripwire(
        Severity.WARNING,
        # typeof resolves absolutely; the bare property has no vocab in scope.
        '<div typeof="https://schema.org/Organization">'
        '<span property="name">Widgetry College</span></div>',
    ),
    "RDFA_BEYOND_LITE": PageTripwire(
        Severity.WARNING,
        # `about` is RDFa 1.1 Core, not Lite, and is not interpreted here.
        '<div vocab="https://schema.org/" typeof="Organization" about="#org">'
        '<span property="name">Widgetry College</span></div>',
    ),
    # -- mapping it onto CTDL -------------------------------------------------
    "ITEM_UNTYPED": PageTripwire(
        Severity.WARNING,
        _block('{"@context":"https://schema.org","name":"An item that declares no type"}'),
    ),
    "CLASS_NOT_MAPPED": PageTripwire(
        Severity.WARNING,
        _block('{"@context":"https://schema.org","@type":"CourseInstance","name":"Fall term"}'),
    ),
    "CLASS_RELATED_NOT_EQUIVALENT": PageTripwire(
        Severity.INFO,
        # ceterms:CredentialPerson is declared a subclass of schema:Person.
        # That relation runs from CTDL outward and licenses nothing inward.
        _block('{"@context":"https://schema.org","@type":"Person","name":"A Registrar"}'),
    ),
    "CLASS_AMBIGUOUS": PageTripwire(
        Severity.WARNING,
        _block('{"@context":"https://schema.org","@type":"Course","name":"Welding"}'),
        equivalent_class={"schema:Course": ("ceterms:Course", "ceterms:LearningProgram")},
    ),
    "PROPERTY_NOT_MAPPED": PageTripwire(
        Severity.WARNING,
        _block('{"@context":"https://schema.org","@type":"Course","about":"welding"}'),
    ),
    "PROPERTY_RELATED_NOT_EQUIVALENT": PageTripwire(
        Severity.INFO,
        # ceterms:keyword and ceterms:subject are subproperties of schema:about.
        _block('{"@context":"https://schema.org","@type":"Course","about":"welding"}'),
    ),
    "PROPERTY_AMBIGUOUS": PageTripwire(
        Severity.WARNING,
        # schema:startDate is equivalent to two CTDL properties and neither
        # declares ceterms:Course in its domain.
        _block('{"@context":"https://schema.org","@type":"Course","startDate":"2026-09-01"}'),
    ),
    "NESTED_ITEM_DROPPED": PageTripwire(
        Severity.WARNING,
        _block(
            '{"@context":"https://schema.org","@type":"Course",'
            '"hasPart":{"@type":"CourseInstance","name":"Fall term"}}'
        ),
    ),
    "VALUE_NOT_LITERAL": PageTripwire(
        Severity.WARNING,
        _block(
            '{"@context":"https://schema.org","@type":"Course",'
            '"name":{"@type":"Thing","name":"an object where a name belongs"}}'
        ),
    ),
    "VALUE_NOT_IDENTIFIER": PageTripwire(
        Severity.WARNING,
        # ceterms:ownedBy takes an identifier; the page published a name.
        _block('{"@context":"https://schema.org","@type":"Course","provider":"Widgetry College"}'),
    ),
    "LANGUAGE_UNDECLARED": PageTripwire(
        Severity.INFO,
        # ceterms:name is a language map and the JSON-LD declares no @language.
        _block('{"@context":"https://schema.org","@type":"Organization","name":"Widgetry"}'),
    ),
    "CTID_ABSENT": PageTripwire(
        Severity.INFO,
        _block('{"@context":"https://schema.org","@type":"Organization","name":"Widgetry"}'),
    ),
}


def _notes(tripwire: PageTripwire, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    if tripwire.equivalent_class is not None:
        crosswalk = load_crosswalk()
        substituted = replace(
            crosswalk,
            equivalent_class={**crosswalk.equivalent_class, **tripwire.equivalent_class},
        )
        monkeypatch.setattr(
            "ctdl_validate.extract.markup.load_crosswalk", lambda: substituted, raising=True
        )
    page = f"<!doctype html><html lang='en'><body>{tripwire.body}</body></html>"
    return list(extract_from_html(page, EXTRACT_SOURCE).notes)


def test_every_note_code_the_source_emits_has_a_page_that_trips_it() -> None:
    """Direction 1, for extraction. ``JSONLD_CONTEXT_UNRESOLVED`` was here."""
    missing = sorted(note_codes_in_source() - set(EXTRACT_TRIPWIRES))
    assert missing == [], (
        "these notes are emitted by the extract modules and no page in this file "
        f"trips them, so nothing would notice if they stopped firing: {missing}"
    )


def test_no_page_tripwire_outlives_the_note_it_was_written_for() -> None:
    """Direction 2, for extraction."""
    stale = sorted(set(EXTRACT_TRIPWIRES) - note_codes_in_source())
    assert stale == [], (
        "these codes are listed here and no extract module emits them any more: "
        f"{stale}. Remove the entry, or the note was deleted by accident."
    )


@pytest.mark.parametrize("code", sorted(EXTRACT_TRIPWIRES))
def test_the_note_fires_at_the_severity_it_is_documented_at(
    code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direction 3, for extraction: each page is extracted, not just named."""
    tripwire = EXTRACT_TRIPWIRES[code]
    notes = _notes(tripwire, monkeypatch)
    hits = [note for note in notes if note.code == code]
    assert hits, (
        f"{code} did not fire against the page written to trip it. "
        f"What did fire: {sorted({note.code for note in notes})}"
    )
    assert all(note.severity is tripwire.severity for note in hits), (
        f"{code} fired at {sorted({n.severity.value for n in hits})}, not {tripwire.severity.value}"
    )


def test_the_readme_note_table_lists_exactly_the_notes_the_source_emits() -> None:
    """Direction 4, for extraction. All twenty were undocumented by code."""
    source, documented = note_codes_in_source(), note_codes_in_readme()
    undocumented = sorted(source - documented)
    unimplemented = sorted(documented - source)
    assert undocumented == [], (
        "the extract modules emit these and the README's note table does not list "
        f"them: {undocumented}"
    )
    assert unimplemented == [], (
        f"the README's note table lists these and no extract module emits them: {unimplemented}"
    )


def test_every_note_a_page_tripwire_produces_carries_its_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No note may reach a report without saying where it came from."""
    for code, tripwire in sorted(EXTRACT_TRIPWIRES.items()):
        for note in _notes(tripwire, monkeypatch):
            assert note.rule.citation.strip(), f"{code}: {note.code} cites nothing"
            assert note.rule.url.strip(), f"{code}: {note.code} has no source URL"
            assert note.rule.retrieved.strip(), f"{code}: {note.code} has no retrieval date"


# -- the reconciliation, which is the point ------------------------------------


def test_every_finding_code_in_the_package_is_inside_one_of_these_tables() -> None:
    """The denominator. A directory outside both universes fails here.

    This is the check that was missing. ``checks/`` and ``extract/`` are the
    only two places a finding code is *declared*, and this asserts that by
    walking the whole package rather than by believing it. A new module that
    starts constructing findings does not quietly shrink what the two tables
    above are measured against; it fails until it is given a universe and a
    tripwire table of its own.
    """
    package = codes_in_package()
    covered = rule_codes_in_source() | note_codes_in_source()
    outside = sorted(set(package) - covered)
    assert outside == [], (
        "these finding codes are constructed in src/ctdl_validate and neither "
        "TRIPWIRES nor EXTRACT_TRIPWIRES is measured against the module that "
        f"builds them, so no gate here can tell whether they still fire: "
        f"{ {code: sorted(package[code]) for code in outside} }"
    )
    # A universe cannot cover a code the package does not construct.
    assert covered <= set(package), sorted(covered - set(package))
    assert len(package) >= len(TRIPWIRES) + len(EXTRACT_TRIPWIRES), (
        "fewer codes were found in the package than the two tables list, which "
        "means the scan stopped reading part of src/ rather than that rules were "
        "deleted -- the tables' own staleness tests would have caught the latter"
    )


def test_a_module_that_builds_a_code_at_run_time_carries_a_written_reason() -> None:
    """The self-limiting half of ``CODE_IS_NOT_A_DECLARATION``.

    A code assembled at run time cannot be enumerated, so it is invisible to
    every gate in this file. That is acceptable exactly where the module is
    reading a code back rather than declaring one, and each such module says
    so here in words. The list fails in both directions: an entry for a module
    that no longer has such a site must be deleted, and a module that grows one
    must be added or fixed.
    """
    _, unreadable = _scan(sorted(PACKAGE.rglob("*.py")))
    undeclared = sorted(unreadable - set(CODE_IS_NOT_A_DECLARATION))
    assert undeclared == [], (
        f"{undeclared} build a finding code at run time and give no reason. A code "
        "that is not a string literal cannot be enumerated, so no gate in this "
        "file can see whether it fires."
    )
    stale = sorted(set(CODE_IS_NOT_A_DECLARATION) - unreadable)
    assert stale == [], (
        f"{stale} are listed as building a code at run time and no longer do. "
        "Delete the entry: an exemption that exempts nothing reads as a live "
        "exception in the gate's own output."
    )
    for module, reason in sorted(CODE_IS_NOT_A_DECLARATION.items()):
        assert reason.strip(), f"{module} is exempted with no written reason"
