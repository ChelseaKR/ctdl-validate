"""``--suggest``: the corrections the payload determines, and the ones refused.

Four checks in this tool name a defect whose repair is written somewhere in
the run's own input. ``--suggest`` prints it. The value of that is obvious;
the risk is not, and it is what most of this file is about.

A suggestion is the one part of a validator's output that a reader is
inclined to apply without re-reading the finding. So the tests below hold
three properties that are easy to lose:

1. **A refusal is a written decision.** ``suggest.NEVER_SUGGESTED`` names the
   codes that must never carry one, with the reason as the value, and this
   file asserts that set is disjoint from the suggesters, that every code in
   either is a code the check modules can actually emit, and that the
   documentation states each refusal. A code cannot drift into being
   suggestible.

2. **A silent absence is not a suggestion.** Where the run holds more than one
   candidate, or none, nothing is offered — and the JSON report omits the key
   rather than writing an empty array, so "we looked and found nothing" is
   never spelled the same way as "we did not look". The schema declares
   ``minItems: 1`` to make that unwritable rather than merely unwritten.

3. **The default path does not move.** Every assertion about byte-stability
   here compares the same fixture with the flag off and on.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Rule, Severity, validate_document
from ctdl_validate import __version__ as tool_version
from ctdl_validate.compare import findings_from_report
from ctdl_validate.findings import Finding, render_findings_json, render_findings_text
from ctdl_validate.sarif import render_findings_sarif
from ctdl_validate.session import Session
from ctdl_validate.suggest import NEVER_SUGGESTED, SUGGESTERS, suggestions_for
from ctdl_validate.validator import build_session

from .conftest import fixture_path, load_fixture
from .schema_check import check
from .test_every_rule_fires import codes_in_source
from .test_report_schema import SCHEMA

ROOT = Path(__file__).resolve().parent.parent
SUGGEST_MODULE = ROOT / "src" / "ctdl_validate" / "suggest.py"
API_DOC = ROOT / "docs" / "API.md"

RESOURCE = "https://credentialengineregistry.org/resources/"
GRAPH = "https://credentialengineregistry.org/graph/"

FRAMEWORK_CTID = "ce-177f4c85-4efe-401d-acdd-1ea4adeeaf37"
OTHER_FRAMEWORK_CTID = "ce-82566cee-17f3-4a6e-8f59-b45273aac457"
COMPETENCY_CTID = "ce-5e3de882-3b49-421b-b623-695c63587f4f"
COURSE_CTID = "ce-59e8d15f-7895-4346-a5a8-7a0739a3d344"
ORG_CTID = "ce-79298677-d0e4-4799-853a-a633d9071826"

#: Every committed fixture, so the whole-corpus properties below are asserted
#: over real documents rather than over the three constructed here.
ALL_FIXTURES = sorted(p.name for p in (ROOT / "tests" / "fixtures").glob("*.json"))


def _findings(payload: Any, *args: Any, **kwargs: Any) -> list[Finding]:
    return validate_document(payload, *args, **kwargs)


def _only(findings: list[Finding], code: str) -> Finding:
    matching = [f for f in findings if f.code == code]
    assert len(matching) == 1, [f.code for f in findings]
    return matching[0]


def _framework(ctid: str) -> dict[str, Any]:
    return {
        "@id": RESOURCE + ctid,
        "@type": "ceasn:CompetencyFramework",
        "ceterms:ctid": ctid,
    }


def _competency_pointing_at(value: Any) -> dict[str, Any]:
    return {
        "@id": RESOURCE + COMPETENCY_CTID,
        "@type": "ceasn:Competency",
        "ceterms:ctid": COMPETENCY_CTID,
        "ceasn:isPartOf": value,
    }


# -- the refusal list is a decision, not an omission ---------------------------


def test_no_code_is_both_suggestible_and_refused() -> None:
    assert set(SUGGESTERS) & set(NEVER_SUGGESTED) == set()


def test_every_code_named_either_way_is_a_code_the_source_can_emit() -> None:
    """A suggester or a refusal for a rule that no longer exists is a rule
    nobody is enforcing, dressed as one somebody is."""
    emitted = codes_in_source()
    assert set(SUGGESTERS) <= emitted, set(SUGGESTERS) - emitted
    assert set(NEVER_SUGGESTED) <= emitted, set(NEVER_SUGGESTED) - emitted


def test_every_refusal_carries_a_written_reason() -> None:
    for code, reason in NEVER_SUGGESTED.items():
        assert reason.strip(), code
        assert len(reason) > 40, f"{code}: a reason has to say something"


def test_the_module_and_the_api_document_name_every_code_either_way() -> None:
    """A promise nobody can read is not a promise — the rule ``docs/API.md``
    already applies to the library surface, applied to this flag."""
    source = SUGGEST_MODULE.read_text(encoding="utf-8")
    documented = API_DOC.read_text(encoding="utf-8")
    for code in list(SUGGESTERS) + list(NEVER_SUGGESTED):
        assert code in source, code
        assert code in documented, f"docs/API.md does not mention {code}"


# -- what each suggester determines --------------------------------------------


def test_an_upper_case_ctid_suggests_itself_in_lower_case() -> None:
    findings = _findings(load_fixture("ctid_warnings.json"), suggest=True)
    finding = _only(findings, "CTID_UPPERCASE")
    assert [s.value for s in finding.suggestions] == ["ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4"]
    assert finding.suggestions[0].difference == "the same CTID in lower case"


def test_a_ctid_that_disagrees_with_its_own_id_suggests_the_id_s_ctid() -> None:
    payload = {
        "@graph": [
            {
                "@id": RESOURCE + COURSE_CTID,
                "@type": "ceterms:Course",
                "ceterms:ctid": ORG_CTID,
            }
        ]
    }
    finding = _only(_findings(payload, suggest=True), "CTID_URI_MISMATCH")
    assert [s.value for s in finding.suggestions] == [COURSE_CTID]


def test_an_envelope_uri_suggests_the_one_ctid_the_payload_declares() -> None:
    payload = {
        "@id": GRAPH + "ce-11111111-1111-4111-8111-111111111111",
        "@graph": [
            {
                "@id": RESOURCE + COURSE_CTID,
                "@type": "ceterms:Course",
                "ceterms:ctid": COURSE_CTID,
            }
        ],
    }
    finding = _only(_findings(payload, suggest=True), "CTID_URI_MISMATCH")
    assert [s.value for s in finding.suggestions] == [GRAPH + COURSE_CTID]


def test_an_envelope_uri_suggests_nothing_when_two_ctids_are_declared() -> None:
    """Two candidates is not a determined correction, and picking one would be
    the guess this whole module refuses to make."""
    payload = {
        "@id": GRAPH + "ce-11111111-1111-4111-8111-111111111111",
        "@graph": [
            {
                "@id": RESOURCE + COURSE_CTID,
                "@type": "ceterms:Course",
                "ceterms:ctid": COURSE_CTID,
            },
            _framework(FRAMEWORK_CTID),
        ],
    }
    finding = _only(_findings(payload, suggest=True), "CTID_URI_MISMATCH")
    assert finding.suggestions == ()


def test_a_bare_ctid_suggests_the_id_of_the_entity_that_declares_it() -> None:
    payload = {"@graph": [_framework(FRAMEWORK_CTID), _competency_pointing_at(FRAMEWORK_CTID)]}
    finding = _only(_findings(payload, suggest=True), "REF_BARE_CTID")
    assert [s.value for s in finding.suggestions] == [RESOURCE + FRAMEWORK_CTID]


def test_a_bare_ctid_suggests_nothing_when_nothing_in_reach_declares_it() -> None:
    """The second entity is here so the scan has to reject something: its
    ``@id`` is not a Registry URI, so it declares no CTID in that position and
    the one it declares in ``ceterms:ctid`` is not the one written."""
    payload = {
        "@graph": [
            _competency_pointing_at(FRAMEWORK_CTID),
            {
                "@id": "urn:local:course",
                "@type": "ceterms:Course",
                "ceterms:ctid": COURSE_CTID,
            },
        ]
    }
    finding = _only(_findings(payload, suggest=True), "REF_BARE_CTID")
    assert finding.suggestions == ()


def test_a_bare_ctid_resolves_against_a_document_supplied_with_resolve(
    tmp_path: Path,
) -> None:
    """``--resolve`` documents are part of what the run can see, and the
    framework check already treats them that way."""
    neighbour = tmp_path / "framework.json"
    neighbour.write_text(json.dumps({"@graph": [_framework(FRAMEWORK_CTID)]}), encoding="utf-8")
    payload = {"@graph": [_competency_pointing_at(FRAMEWORK_CTID)]}
    finding = _only(_findings(payload, [neighbour], suggest=True), "REF_BARE_CTID")
    assert [s.value for s in finding.suggestions] == [RESOURCE + FRAMEWORK_CTID]


def test_a_wrong_framework_identifier_suggests_the_one_framework_in_reach() -> None:
    findings = _findings(
        load_fixture("bug_class_252_wrong_framework_identifier.json"), suggest=True
    )
    finding = _only(findings, "ISPARTOF_FRAMEWORK_MISMATCH")
    assert [s.value for s in finding.suggestions] == [RESOURCE + FRAMEWORK_CTID]


def test_a_wrong_framework_identifier_suggests_nothing_with_two_frameworks() -> None:
    payload = {
        "@graph": [
            _framework(FRAMEWORK_CTID),
            _framework(OTHER_FRAMEWORK_CTID),
            _competency_pointing_at(RESOURCE + "ce-33333333-3333-4333-8333-333333333333"),
        ]
    }
    finding = _only(_findings(payload, suggest=True), "ISPARTOF_FRAMEWORK_MISMATCH")
    assert finding.suggestions == ()


# -- the guards, driven directly ------------------------------------------------
#
# `suggestions_for` dispatches on a finding's `code`, and `Finding` is public:
# a caller can hand it one this tool's own checks would never construct. The
# guards below are what stop that producing a confident wrong answer, and each
# is unreachable from the checks -- so without these tests they would be
# untested defensive code sitting behind a coverage floor the rest of the
# package clears for it.


def _finding(code: str, entity: str, prop: str, value: str) -> Finding:
    return Finding(
        code=code,
        severity=Severity.WARNING,
        entity=entity,
        prop=prop,
        value=value,
        message="hand-built, for the guard beneath it",
        rule=Rule(citation="c", url="https://example.invalid/", retrieved="-"),
    )


def _session(payload: Any) -> Session:
    return build_session(payload)


def test_an_uppercase_finding_over_a_value_that_is_not_a_ctid_suggests_nothing() -> None:
    session = _session({"@graph": [_framework(FRAMEWORK_CTID)]})
    finding = _finding("CTID_UPPERCASE", "x", "ceterms:ctid", "NOT-A-CTID")
    assert suggestions_for(session, finding) == ()


def test_a_mismatch_finding_naming_an_entity_the_payload_lacks_suggests_nothing() -> None:
    session = _session({"@graph": [_framework(FRAMEWORK_CTID)]})
    finding = _finding("CTID_URI_MISMATCH", "urn:not-here", "ceterms:ctid", COURSE_CTID)
    assert suggestions_for(session, finding) == ()


def test_a_mismatch_finding_on_an_entity_whose_id_is_not_a_registry_uri() -> None:
    session = _session(
        {"@graph": [{"@id": "urn:local:1", "@type": "ceterms:Course", "ceterms:ctid": COURSE_CTID}]}
    )
    finding = _finding("CTID_URI_MISMATCH", "urn:local:1", "ceterms:ctid", ORG_CTID)
    assert suggestions_for(session, finding) == ()


def test_a_mismatch_finding_on_neither_a_ctid_nor_the_envelope_suggests_nothing() -> None:
    session = _session({"@graph": [_framework(FRAMEWORK_CTID)]})
    finding = _finding("CTID_URI_MISMATCH", RESOURCE + FRAMEWORK_CTID, "ceterms:name", "x")
    assert suggestions_for(session, finding) == ()


def test_an_envelope_id_that_is_not_a_registry_uri_suggests_nothing() -> None:
    session = _session(
        {"@id": "urn:graph:1", "@graph": [{"@type": "ceterms:Course", "ceterms:ctid": COURSE_CTID}]}
    )
    finding = _finding("CTID_URI_MISMATCH", "urn:graph:1", "@id", "urn:graph:1")
    assert suggestions_for(session, finding) == ()


def test_a_supplied_entity_that_declares_a_different_ctid_is_not_a_candidate(
    tmp_path: Path,
) -> None:
    """The `--resolve` scan has to look at every supplied entity and reject the
    ones that do not carry the CTID written, not merely find the first that
    does."""
    neighbour = tmp_path / "framework.json"
    neighbour.write_text(
        json.dumps({"@graph": [_framework(OTHER_FRAMEWORK_CTID)]}), encoding="utf-8"
    )
    payload = {"@graph": [_competency_pointing_at(FRAMEWORK_CTID)]}
    finding = _only(_findings(payload, [neighbour], suggest=True), "REF_BARE_CTID")
    assert finding.suggestions == ()


# -- the refusals, exercised ---------------------------------------------------


def test_a_bare_uuid_where_a_ctid_belongs_gets_no_suggestion() -> None:
    """``ce-`` plus the UUID would be well formed, which is the problem: it
    asserts that this generated UUID names a Registry resource."""
    findings = _findings(load_fixture("bug_class_250_bare_uuid_for_ctid.json"), suggest=True)
    assert _only(findings, "CTID_BARE_UUID").suggestions == ()


def test_a_bare_uuid_reference_gets_no_suggestion() -> None:
    payload = {
        "@graph": [
            _framework(FRAMEWORK_CTID),
            _competency_pointing_at(FRAMEWORK_CTID.removeprefix("ce-")),
        ]
    }
    findings = _findings(payload, suggest=True)
    assert _only(findings, "REF_BARE_UUID").suggestions == ()


@pytest.mark.parametrize("document", ALL_FIXTURES)
def test_no_unverifiable_finding_ever_carries_a_suggestion(document: str) -> None:
    """UNVERIFIABLE means the payload alone cannot settle it. A candidate read
    out of that same payload cannot settle it either, and offering one would
    read as though it had."""
    for finding in _findings(load_fixture(document), suggest=True):
        if finding.severity is Severity.UNVERIFIABLE:
            assert finding.suggestions == (), finding.code


@pytest.mark.parametrize("document", ALL_FIXTURES)
def test_no_suggestion_ever_re_offers_the_value_that_was_written(document: str) -> None:
    for finding in _findings(load_fixture(document), suggest=True):
        for suggestion in finding.suggestions:
            assert suggestion.value != finding.value, finding.code


def test_an_unverifiable_finding_of_a_suggestible_code_still_gets_nothing() -> None:
    """The UNVERIFIABLE bar is stated as a rule about severities, not about
    codes, and today no suggestible code is ever emitted at that severity — so
    over the committed fixtures the bar is vacuous and a sabotage of it goes
    unnoticed. This drives it directly, so the rule survives the day a
    suggestible code gains an UNVERIFIABLE form.
    """
    session = _session({"@graph": [_framework(FRAMEWORK_CTID)]})
    upper = "ce-B55F88E3-DFD4-430B-AB47-3E5F9986E1E4"
    warning = _finding("CTID_UPPERCASE", "x", "ceterms:ctid", upper)
    assert len(suggestions_for(session, warning)) == 1, "the fixture must reach the suggester"
    unverifiable = dataclasses.replace(warning, severity=Severity.UNVERIFIABLE)
    assert suggestions_for(session, unverifiable) == ()


def test_a_candidate_that_is_not_itself_an_iri_is_not_offered() -> None:
    """Answering ``REF_BARE_CTID`` with another bare identifier would trip the
    rule the suggestion exists to answer. The entity here declares the written
    CTID in ``ceterms:ctid`` while its own ``@id`` is a *different* bare CTID,
    so the "not the value that was written" rule cannot cover this and the IRI
    filter is the only thing that does.
    """
    payload = {
        "@graph": [
            _competency_pointing_at(FRAMEWORK_CTID),
            {
                "@id": OTHER_FRAMEWORK_CTID,
                "@type": "ceasn:CompetencyFramework",
                "ceterms:ctid": FRAMEWORK_CTID,
            },
        ]
    }
    finding = _only(_findings(payload, suggest=True), "REF_BARE_CTID")
    assert finding.suggestions == ()


# -- the flag adds and changes nothing else ------------------------------------


@pytest.mark.parametrize("document", ALL_FIXTURES)
def test_the_default_path_carries_no_suggestion_at_all(document: str) -> None:
    findings = _findings(load_fixture(document))
    assert all(f.suggestions == () for f in findings)
    assert "suggestions" not in render_findings_json(findings, tool_version)
    assert "suggested:" not in render_findings_text(findings)


@pytest.mark.parametrize("document", ALL_FIXTURES)
def test_the_flag_changes_no_finding_s_identity_or_order(document: str) -> None:
    payload = load_fixture(document)
    plain = _findings(payload)
    suggested = _findings(payload, suggest=True)
    assert [f.sort_key() for f in plain] == [f.sort_key() for f in suggested]
    assert [f.severity for f in plain] == [f.severity for f in suggested]


@pytest.mark.parametrize("document", ALL_FIXTURES)
def test_a_suggested_report_still_conforms_to_the_shipped_schema(document: str) -> None:
    findings = _findings(load_fixture(document), suggest=True)
    report = json.loads(render_findings_json(findings, tool_version))
    assert check(report, SCHEMA) == []


def test_an_empty_suggestions_array_is_refused_by_the_schema() -> None:
    """Absent and empty must not be two spellings of the same fact. Nothing
    writes an empty array; ``minItems`` is what makes that unwritable rather
    than merely unwritten."""
    findings = _findings(load_fixture("ctid_warnings.json"), suggest=True)
    report = json.loads(render_findings_json(findings, tool_version))
    report["findings"][0]["suggestions"] = []
    assert check(report, SCHEMA) != []


def test_a_suggestion_missing_its_difference_is_refused_by_the_schema() -> None:
    findings = _findings(load_fixture("ctid_warnings.json"), suggest=True)
    report = json.loads(render_findings_json(findings, tool_version))
    suggestions = report["findings"][0]["suggestions"]
    assert suggestions, "this fixture is meant to carry one"
    del suggestions[0]["difference"]
    assert check(report, SCHEMA) != []


# -- every rendering says the same thing ---------------------------------------


def test_the_text_report_prints_the_candidate_beneath_the_finding() -> None:
    text = render_findings_text(_findings(load_fixture("ctid_warnings.json"), suggest=True))
    expected = (
        "    suggested: ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4  (the same CTID in lower case)"
    )
    assert expected in text


def test_the_sarif_result_carries_the_candidate_in_its_property_bag() -> None:
    """SARIF's ``fixes`` wants a source region this tool does not have (#66),
    so the property bag carries it without claiming to be applicable."""
    document = fixture_path("ctid_warnings.json")
    log = json.loads(
        render_findings_sarif(
            _findings(load_fixture("ctid_warnings.json"), suggest=True), tool_version, document
        )
    )
    results = {r["ruleId"]: r for r in log["runs"][0]["results"]}
    assert results["CTID_UPPERCASE"]["properties"]["suggestions"] == [
        {
            "value": "ce-b55f88e3-dfd4-430b-ab47-3e5f9986e1e4",
            "difference": "the same CTID in lower case",
        }
    ]
    assert "suggestions" not in results["CTID_NOT_UUIDV4"]["properties"]


def test_the_default_sarif_log_is_byte_identical_with_the_flag_off() -> None:
    document = fixture_path("ctid_warnings.json")
    payload = load_fixture("ctid_warnings.json")
    plain = render_findings_sarif(_findings(payload), tool_version, document)
    assert "suggestions" not in plain
    assert plain != render_findings_sarif(_findings(payload, suggest=True), tool_version, document)


# -- what `diff` does with a report that carries them ---------------------------


def test_a_saved_suggested_report_reads_back_without_its_candidates() -> None:
    """`diff` compares runs, and a suggestion is not part of what changed.

    `findings_from_report` drops the key on purpose: one side of a diff is
    frequently a payload validated on the spot, which never carries a
    candidate, so reconstructing them would render as a change where there is
    none. The drop is stated in that function's docstring; this is the pin.
    """
    payload = load_fixture("ctid_warnings.json")
    report = json.loads(render_findings_json(_findings(payload, suggest=True), tool_version))
    assert any("suggestions" in f for f in report["findings"]), "the fixture must carry one"
    rebuilt = findings_from_report(report)
    assert [f.code for f in rebuilt] == [f.code for f in _findings(payload)]
    assert all(f.suggestions == () for f in rebuilt)


def test_diffing_a_suggested_report_against_its_own_payload_finds_nothing(
    tmp_path: Path,
) -> None:
    saved = tmp_path / "before.json"
    saved.write_text(
        render_findings_json(
            _findings(load_fixture("ctid_warnings.json"), suggest=True), tool_version
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ctdl_validate",
            "diff",
            str(saved),
            str(fixture_path("ctid_warnings.json")),
        ],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert b"added: present after, absent before (0)" in completed.stdout
    assert b"removed: present before, absent after (0)" in completed.stdout
    assert b"suggested:" not in completed.stdout


# -- through the CLI -----------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ctdl_validate", *args], capture_output=True, check=False
    )


def test_the_cli_prints_nothing_new_without_the_flag() -> None:
    path = str(fixture_path("ctid_warnings.json"))
    without = _run(path)
    with_flag = _run(path, "--suggest")
    assert without.returncode == with_flag.returncode == 0
    assert b"suggested:" not in without.stdout
    assert b"suggested:" in with_flag.stdout


def test_the_cli_json_report_carries_the_candidate_under_the_flag() -> None:
    completed = _run(str(fixture_path("ctid_warnings.json")), "--suggest", "--format", "json")
    assert completed.returncode == 0
    report = json.loads(completed.stdout)
    assert check(report, SCHEMA) == []
    suggested = [f for f in report["findings"] if "suggestions" in f]
    assert [f["code"] for f in suggested] == ["CTID_UPPERCASE"]
