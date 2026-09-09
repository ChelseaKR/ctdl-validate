"""``ctdl-validate diff``: what changed between two runs, and what it refuses to say.

The repository already computed this by hand every time a rule changed -- the
README's "36 of 120 documents failing became 0, as all 38 RANGE_VIOLATION
findings became CONCEPT_RANGE_CONFLICT" is a diff between two runs, produced
once and then typed. A verb makes it reproducible.

The half worth testing hardest is what the verb declines to claim. A finding
present before and absent after is *removed*, never *resolved*: a run over a
truncated payload, a run with a different `--resolve` set, and a real repair
all produce the same absence, and calling it a fix would be an absence
published as a measurement. A finding whose entity moved is *moved* only where
exactly one was removed and exactly one added under the same non-entity key;
where several were, the pairing is declined and said to be declined.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest

from ctdl_validate import __version__, validate_document
from ctdl_validate.compare import (
    Comparison,
    ReportError,
    compare,
    finding_key,
    findings_from_report,
    is_report,
)
from ctdl_validate.diff import (
    IDENTICAL_ACROSS_A_CHANGED_PAIR,
    UNRECORDED,
    comparable_fields,
    load_side,
    main,
    provenance_notes,
    render_json,
    render_text,
)
from ctdl_validate.findings import Finding, Rule, Severity, render_findings_json
from ctdl_validate.rules import RETRIEVED as VENDOR_RETRIEVED

from .conftest import FIXTURES, fixture_path, load_fixture

RESOLVE = FIXTURES / "resolve"

RULE = Rule(citation="a rule", url="https://example.invalid/", retrieved="2026-01-01")
OTHER = Rule(citation="another rule", url="https://example.invalid/b", retrieved="2026-01-01")


def _finding(  # noqa: PLR0913, PLR0917 - one keyword per Finding field, on purpose
    code: str = "CODE",
    *,
    severity: Severity = Severity.ERROR,
    entity: str = "urn:a",
    prop: str = "ceterms:name",
    value: str = "v",
    message: str = "m",
    rule: Rule = RULE,
) -> Finding:
    return Finding(code, severity, entity, prop, value, message, rule)


def _report(document: str, resolve: list[Path] | None = None) -> str:
    return render_findings_json(validate_document(load_fixture(document), resolve), __version__)


def _run(tmp_path: Path, *argv: str) -> tuple[int, str]:
    """The verb through the real CLI dispatch, capturing stdout."""
    completed = subprocess.run(
        [sys.executable, "-m", "ctdl_validate", "diff", *argv],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return completed.returncode, completed.stdout + completed.stderr


# -- the comparison ------------------------------------------------------------


def test_identical_inputs_yield_an_empty_diff() -> None:
    findings = validate_document(load_fixture("bug_class_252_wrong_framework_identifier.json"))
    assert findings, "this fixture should report something, or the test proves nothing"
    result = compare(findings, findings)
    assert result.empty
    assert result.unchanged == len(findings)
    assert result.before == result.after


def test_a_finding_present_only_after_is_added_and_only_before_is_removed() -> None:
    before = [_finding(entity="urn:a")]
    after = [_finding(entity="urn:b")]
    result = compare(before, after, pair_moves=False)
    assert [f.entity for f in result.added] == ["urn:b"]
    assert [f.entity for f in result.removed] == ["urn:a"]
    assert result.unchanged == 0


def test_a_finding_whose_value_moved_is_changed_not_removed_and_added() -> None:
    before = [_finding(value="one")]
    after = [_finding(value="two")]
    result = compare(before, after)
    assert not result.added and not result.removed
    assert [(b.value, a.value) for b, a in result.changed] == [("one", "two")]


def test_two_rules_failing_on_one_property_stay_distinct() -> None:
    """Identity carries the rule citation because it has to.

    Without it, two findings at one entity and property would collide and one
    would silently vanish from the comparison.
    """
    before = [_finding(rule=RULE), _finding(rule=OTHER)]
    assert len({finding_key(f) for f in before}) == 2
    result = compare(before, [_finding(rule=RULE)])
    assert [f.rule.citation for f in result.removed] == ["another rule"]


def test_a_displaced_finding_is_moved_rather_than_removed_and_added() -> None:
    result = compare([_finding(entity="urn:a")], [_finding(entity="urn:b")])
    assert not result.added and not result.removed
    assert [(b.entity, a.entity) for b, a in result.moved] == [("urn:a", "urn:b")]


def test_an_ambiguous_displacement_is_declined_and_said_to_be_declined() -> None:
    """Two removed and two added under one key: which went where is a guess."""
    before = [_finding(entity="urn:a"), _finding(entity="urn:b")]
    after = [_finding(entity="urn:c"), _finding(entity="urn:d")]
    result = compare(before, after)
    assert result.moved == []
    assert len(result.removed) == 2 and len(result.added) == 2
    assert result.ambiguous_moves == [("CODE", "ceterms:name", "v", "a rule")]


def test_pair_moves_off_leaves_every_displacement_in_removed_and_added() -> None:
    result = compare([_finding(entity="urn:a")], [_finding(entity="urn:b")], pair_moves=False)
    assert result.moved == []
    assert len(result.removed) == 1 and len(result.added) == 1


def test_a_moved_error_is_not_a_new_error() -> None:
    moved = compare([_finding(entity="urn:a")], [_finding(entity="urn:b")])
    assert moved.new_errors == []
    introduced = compare([], [_finding()])
    assert len(introduced.new_errors) == 1


def test_new_errors_counts_only_errors() -> None:
    result = compare([], [_finding(severity=Severity.WARNING), _finding(severity=Severity.ERROR)])
    assert [f.severity for f in result.new_errors] == [Severity.ERROR]


def test_the_comparison_never_uses_the_word_resolved() -> None:
    """The vocabulary is the contract: removed, added, changed, moved.

    A field named ``resolved`` would say, in the machine-readable output that
    other tools parse, that a finding's absence is evidence it was fixed. It
    is not, and the shape must not imply it.
    """
    assert [field.name for field in dataclasses.fields(Comparison)] == [
        "removed",
        "added",
        "changed",
        "moved",
        "unchanged",
        "before",
        "after",
        "ambiguous_moves",
    ]
    payload: dict[str, Any] = compare([_finding()], []).to_dict()
    assert set(payload) == {
        "removed",
        "added",
        "changed",
        "moved",
        "unchanged",
        "summary",
        "ambiguous_moves",
    }


# -- the issue's own acceptance cases ------------------------------------------


def test_the_seeded_framework_mismatch_is_reported_as_introduced() -> None:
    """`clean_framework.json` against its `bug_class_252` counterpart.

    Issue #61 expects "exactly the seeded `ISPARTOF_FRAMEWORK_MISMATCH`". That
    is not what the fixture pair produces, and the fixture is right: changing
    one competency's `ceasn:isPartOf` to an identifier no framework in the
    payload declares also makes that reference point outside the payload
    (`REF_OUTSIDE_PAYLOAD`, UNVERIFIABLE) and puts a second competency's
    `isPartOf` out of range (`RANGE_VIOLATION`). All three are introduced, and
    the seeded one is among them; asserting "exactly one" would have meant
    weakening the fixture to fit the sentence.
    """
    result = compare(
        validate_document(load_fixture("clean_framework.json")),
        validate_document(load_fixture("bug_class_252_wrong_framework_identifier.json")),
    )
    assert result.removed == []
    introduced = {f.code for f in result.added}
    assert "ISPARTOF_FRAMEWORK_MISMATCH" in introduced
    assert introduced == {"ISPARTOF_FRAMEWORK_MISMATCH", "REF_OUTSIDE_PAYLOAD", "RANGE_VIOLATION"}
    assert result.before["ERROR"] == 0 and result.after["ERROR"] == 1


def test_resolution_is_additive_a_resolved_run_introduces_no_error_the_other_lacked() -> None:
    """ADR-0004, checkable in one line.

    Supplying a document the payload refers to may settle an UNVERIFIABLE
    reference into an INFO or an ERROR. What it must never do is introduce an
    ERROR about something the unresolved run had no target for: every added
    ERROR here has to correspond to an UNVERIFIABLE finding that was removed
    on the same entity and property.
    """
    payload = load_fixture("external_reference.json")
    unresolved = validate_document(payload)
    resolved = validate_document(payload, [RESOLVE / "owner_organization.json"])
    result = compare(unresolved, resolved, pair_moves=False)

    unsettled = {(f.entity, f.prop) for f in unresolved if f.severity is Severity.UNVERIFIABLE}
    assert unsettled, "the unresolved run must have something unsettled, or this proves nothing"
    for finding in result.added:
        assert (finding.entity, finding.prop) in unsettled, finding
    assert all(f.severity is Severity.UNVERIFIABLE for f in result.removed)


def test_the_same_check_catches_a_resolution_that_is_not_additive() -> None:
    """The control for the test above: a fabricated non-additive run fails it.

    Without this, that assertion could be passing because `--resolve` happens
    to add nothing on this fixture rather than because it is additive.
    """
    unresolved = [_finding(severity=Severity.UNVERIFIABLE, entity="urn:a", prop="p")]
    not_additive = [_finding(severity=Severity.ERROR, entity="urn:z", prop="q")]
    result = compare(unresolved, not_additive, pair_moves=False)
    unsettled = {(f.entity, f.prop) for f in unresolved}
    assert any((f.entity, f.prop) not in unsettled for f in result.added)


# -- saved reports -------------------------------------------------------------


def test_a_saved_report_round_trips_to_the_findings_it_was_rendered_from() -> None:
    findings = validate_document(load_fixture("bug_class_252_wrong_framework_identifier.json"))
    rebuilt = findings_from_report(json.loads(render_findings_json(findings, __version__)))
    assert rebuilt == findings
    assert compare(findings, rebuilt).empty


def test_a_payload_is_not_mistaken_for_a_report_or_the_other_way_round() -> None:
    assert not is_report(load_fixture("clean_framework.json"))
    assert not is_report([{"@id": "urn:a"}])
    assert is_report(json.loads(_report("clean_framework.json")))


def test_a_truncated_report_raises_rather_than_diffing_what_it_could_read() -> None:
    """A partial read of evidence is the thing this comparison must not publish.

    A report whose findings were cut in half would otherwise diff as a payload
    whose second half had been repaired.
    """
    payload = json.loads(_report("bug_class_252_wrong_framework_identifier.json"))
    broken = copy.deepcopy(payload)
    del broken["findings"][0]["rule"]["citation"]
    with pytest.raises(ReportError):
        findings_from_report(broken)

    mutations: list[dict[str, Any]] = [{"findings": "not a list"}, {"tool": {}, "findings": None}]
    for mutation in mutations:
        with pytest.raises(ReportError):
            findings_from_report({**payload, **mutation})


def test_an_unknown_severity_in_a_report_is_refused_not_defaulted() -> None:
    payload = json.loads(_report("bug_class_252_wrong_framework_identifier.json"))
    payload["findings"][0]["severity"] = "CRITICAL"
    with pytest.raises(ReportError):
        findings_from_report(payload)


# -- provenance the diff cannot establish --------------------------------------


def test_a_report_side_says_its_vendored_snapshot_is_unknown(tmp_path: Path) -> None:
    saved = tmp_path / "before.json"
    saved.write_text(_report("clean_framework.json"), encoding="utf-8")
    side = load_side(saved, [])
    assert side.origin == "report"
    assert side.snapshot == UNRECORDED

    validated = load_side(fixture_path("clean_framework.json"), [])
    assert validated.origin == "payload"
    assert validated.snapshot != UNRECORDED

    notes = provenance_notes(side, validated)
    assert any("snapshot unknown" in note for note in notes), notes


def test_a_tool_version_mismatch_is_printed_and_does_not_stop_the_diff(tmp_path: Path) -> None:
    saved = json.loads(_report("clean_framework.json"))
    saved["tool"]["version"] = "0.0.1-ancient"
    path = tmp_path / "old.json"
    path.write_text(json.dumps(saved), encoding="utf-8")
    fresh = load_side(fixture_path("clean_framework.json"), [])
    notes = provenance_notes(load_side(path, []), fresh)
    assert any("tool version differs" in note for note in notes), notes
    assert main([str(path), str(fixture_path("clean_framework.json"))]) == 0


def test_two_validated_sides_agree_on_the_snapshot_and_say_nothing_about_it() -> None:
    left = load_side(fixture_path("clean_framework.json"), [])
    right = load_side(fixture_path("bug_class_252_wrong_framework_identifier.json"), [])
    assert provenance_notes(left, right) == []


def test_a_validated_side_is_always_stamped_with_the_running_snapshot() -> None:
    """Why there is no "the two snapshots differ" note, and when there must be.

    ``provenance_notes`` carried one and it could not fire: every side is
    stamped either :data:`UNRECORDED` (a saved report, which records no
    snapshot) or ``rules.RETRIEVED`` (validated here, in this process), so
    two *known* snapshots are one module constant read twice. An unreachable
    refusal reads as a guard and never is one, so it was removed.

    This test is the expiry date on that removal. The day a saved report
    carries its own snapshot -- ``ctdl_validate.snapshot.identity()`` is
    already emitted in SARIF and is what a ``--format json`` report would
    have to grow -- ``load_side`` stops returning one constant here, this
    fails, and the note has a real question to answer.
    """
    stamped = {
        load_side(fixture_path(name), []).snapshot
        for name in ("clean_framework.json", "ctid_warnings.json", "domain_violation.json")
    }
    assert stamped == {VENDOR_RETRIEVED}, (
        "a validated side no longer always carries the running snapshot, so two known "
        "snapshots can now disagree and provenance_notes has to say so again"
    )
    assert UNRECORDED != VENDOR_RETRIEVED, "the two stamps must stay distinguishable"


# -- what a changed pair differs on --------------------------------------------


def _rendered_change(before: Finding, after: Finding) -> str:
    """The text report for one changed pair, as a reader sees it."""
    side = load_side(fixture_path("clean_framework.json"), [])
    return render_text(side, side, compare([before], [after]))


def test_a_message_only_change_names_the_message_on_both_sides() -> None:
    """The defect this fixes.

    ``IDENTITY`` leaves value and message out, so a finding reworded between
    two tool versions is *changed* with an identical value and an identical
    severity -- and the text report's only line about a changed pair was
    ``was: <value> / <severity>``. It announced a change and then printed two
    identical strings, with the message shown nowhere on either side, while
    the README says in terms that a finding "whose value or message moved
    under that identity is *changed*".
    """
    old = _finding(message="the wording an older release used")
    new = _finding(message="the wording this release uses")
    assert finding_key(old) == finding_key(new), (
        "these must be the same finding, or nothing changed"
    )

    text = _rendered_change(old, new)
    assert "changed: same finding, different value or message (1)" in text
    assert "message now: the wording this release uses" in text
    assert "message was: the wording an older release used" in text
    # Only the field that moved is named: a report that listed every field
    # would put the reader back where they started.
    assert "value now:" not in text
    assert "severity now:" not in text


def test_a_value_change_names_the_value_and_leaves_the_message_alone() -> None:
    text = _rendered_change(_finding(value="ce-OLD"), _finding(value="ce-new"))
    assert "value now: ce-new" in text
    assert "value was: ce-OLD" in text
    assert "message now:" not in text


def test_a_severity_change_is_named_rather_than_left_to_be_spotted() -> None:
    text = _rendered_change(_finding(severity=Severity.ERROR), _finding(severity=Severity.WARNING))
    assert "severity now: WARNING" in text
    assert "severity was: ERROR" in text


def test_every_field_a_changed_pair_can_differ_on_is_named_by_the_report() -> None:
    """The floor under the two lists, so neither can stop covering ``Finding``.

    ``message`` was a field the report could not show; ``suggestions`` was
    added to ``Finding`` afterwards and would have been the next one. Deriving
    the comparable set from the dataclass is what stops that recurring, and
    this asserts the derivation still accounts for the whole record: a field
    added to ``Finding`` is either held equal by the identity key or named by
    the report, and there is no third place for it to go.
    """
    declared = {field.name for field in dataclasses.fields(Finding)}
    named = set(comparable_fields())
    identical = set(IDENTICAL_ACROSS_A_CHANGED_PAIR)
    assert identical <= declared, (
        f"identity names a field Finding does not have: {identical - declared}"
    )
    assert named, "a changed pair would have no field to differ on"
    unaccounted = declared - named - identical
    assert not unaccounted, (
        f"Finding has fields this report neither holds equal nor names: {unaccounted}"
    )
    assert not named & identical, "a field cannot be both held equal and reported as differing"
    assert "message" in named, "the field the report could not show must stay in the compared set"


def test_the_identity_fields_are_the_ones_the_comparison_actually_holds_equal() -> None:
    """``IDENTICAL_ACROSS_A_CHANGED_PAIR`` is a claim about ``compare``, so it
    is checked against ``compare`` rather than against a second list."""
    old = _finding()
    moved_one_field: tuple[tuple[str, Finding], ...] = (
        ("code", _finding("OTHER_CODE")),
        ("entity", _finding(entity="urn:elsewhere")),
        ("prop", _finding(prop="ceterms:description")),
        ("rule", _finding(rule=OTHER)),
    )
    assert {field for field, _ in moved_one_field} == set(IDENTICAL_ACROSS_A_CHANGED_PAIR)
    for field, new in moved_one_field:
        result = compare([old], [new], pair_moves=False)
        assert not result.changed, f"{field} moved and the pair was still called changed"
        assert result.removed and result.added


def test_resolve_is_refused_on_a_saved_report_rather_than_ignored(tmp_path: Path) -> None:
    """Silently ignoring the flag would report a difference that was in the
    invocation rather than in the payload."""
    saved = tmp_path / "before.json"
    saved.write_text(_report("clean_framework.json"), encoding="utf-8")
    code, output = _run(
        tmp_path,
        str(saved),
        str(fixture_path("clean_framework.json")),
        "--resolve-before",
        str(RESOLVE),
    )
    assert code == 2
    assert "saved report" in output


# -- the CLI -------------------------------------------------------------------


def test_the_verb_is_dispatched_and_exits_zero_when_something_changed(tmp_path: Path) -> None:
    code, output = _run(
        tmp_path,
        str(fixture_path("clean_framework.json")),
        str(fixture_path("bug_class_252_wrong_framework_identifier.json")),
    )
    assert code == 0, "a diff is data, not a verdict"
    assert "ISPARTOF_FRAMEWORK_MISMATCH" in output
    assert "it is not evidence that it was fixed" in output


def test_fail_on_new_gates_on_an_introduced_error_and_only_on_that() -> None:
    clean = str(fixture_path("clean_framework.json"))
    broken = str(fixture_path("bug_class_252_wrong_framework_identifier.json"))
    assert main([clean, broken, "--fail-on-new"]) == 1
    assert main([broken, clean, "--fail-on-new"]) == 0, "removing an ERROR is not a new one"
    assert main([clean, clean, "--fail-on-new"]) == 0


def test_an_unreadable_input_is_exit_two(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert main([str(missing), str(fixture_path("clean_framework.json"))]) == 2
    truncated = tmp_path / "truncated.json"
    truncated.write_text("{", encoding="utf-8")
    assert main([str(truncated), str(fixture_path("clean_framework.json"))]) == 2


def test_the_json_form_is_deterministic_and_carries_both_sides_provenance() -> None:
    left = load_side(fixture_path("clean_framework.json"), [])
    right = load_side(fixture_path("bug_class_252_wrong_framework_identifier.json"), [])
    result: Comparison = compare(left.findings, right.findings)
    rendered = render_json(left, right, result)
    assert rendered == render_json(left, right, compare(left.findings, right.findings))
    payload = json.loads(rendered)
    assert payload["tool"] == {"name": "ctdl-validate", "version": __version__}
    assert payload["before"]["origin"] == "payload"
    assert payload["after"]["ctdl_snapshot"] == left.snapshot
    assert payload["diff"]["summary"]["after"]["ERROR"] == 1


def test_diff_of_a_document_against_its_own_saved_report_is_empty(tmp_path: Path) -> None:
    """The two input kinds have to mean the same thing, or the verb is a lie."""
    saved = tmp_path / "saved.json"
    saved.write_text(_report("bug_class_252_wrong_framework_identifier.json"), encoding="utf-8")
    left = load_side(saved, [])
    right = load_side(fixture_path("bug_class_252_wrong_framework_identifier.json"), [])
    assert compare(left.findings, right.findings).empty


# -- the posture the default path has ------------------------------------------


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("this code path must not open a socket")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.mark.usefixtures("no_network")
def test_the_diff_verb_opens_no_socket() -> None:
    assert (
        main(
            [
                str(fixture_path("clean_framework.json")),
                str(fixture_path("bug_class_252_wrong_framework_identifier.json")),
            ]
        )
        == 0
    )


def test_running_diff_loads_no_fetching_code() -> None:
    """`extract` is the only command that may reach a network, and it must not
    be imported by a run that does not use it."""
    program = (
        "import sys; from ctdl_validate.cli import main; "
        f"main(['diff', {str(fixture_path('clean_framework.json'))!r}, "
        f"{str(fixture_path('clean_framework.json'))!r}]); "
        "loaded = [m for m in sys.modules if 'extract' in m]; "
        "print('LOADED:' + ','.join(sorted(loaded)))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    line = [ln for ln in completed.stdout.splitlines() if ln.startswith("LOADED:")]
    assert line == ["LOADED:"], line
