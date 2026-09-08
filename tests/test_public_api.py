"""``ctdl_validate``'s public surface, pinned so that changing it is deliberate.

The playground imports ``validate_document`` through Pyodide, the Action runs
the CLI, and ``ctdl-validate-jvm`` compares its own JSON reporter against this
one. Issue #65 makes that a promise rather than an accident. The pins below
are not busywork: a signature here is what another runtime writes its call
against, and the failure mode of an unpinned surface is a caller that breaks
on an upgrade with nothing in the CHANGELOG to explain it.

Changing one of these turns this file red on purpose: edit it in the same
commit that changes the API, and say so in the CHANGELOG under ``Changed`` --
``docs/API.md`` states which changes require a major release.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path

import pytest

import ctdl_validate
from ctdl_validate import Finding, Rule, Severity

ROOT = Path(__file__).resolve().parent.parent
API_DOC = ROOT / "docs" / "API.md"
CHANGELOG = ROOT / "CHANGELOG.md"

#: Every public name, and the exact signature it is promised to keep. A
#: callable's signature is compared as ``str(inspect.signature(...))``; a
#: non-callable's entry is None and only its presence is pinned.
PUBLIC: dict[str, str | None] = {
    "REPORT_SCHEMA_VERSION": None,
    "Finding": None,
    "Rule": None,
    "Severity": None,
    "__version__": None,
    "read_report_schema": "() -> 'str'",
    "validate_document": (
        "(data: 'Any', resolve: 'list[Path] | None' = None, *, "
        "suggest: 'bool' = False) -> 'list[Finding]'"
    ),
}

#: The fields of ``Finding``, in order, with their declared types. A field
#: removed or renamed breaks every consumer; a field added without a default
#: breaks every constructor call.
FINDING_FIELDS = [
    ("code", "str"),
    ("severity", "Severity"),
    ("entity", "str"),
    ("prop", "str"),
    ("value", "str"),
    ("message", "str"),
    ("rule", "Rule"),
    ("suggestions", "tuple[Suggestion, ...]"),
]

#: The one field of ``Finding`` allowed to carry a default, and why.
#:
#: The rule below — no field of a Finding is optional — exists so that a check
#: cannot construct a finding short of its ``value`` or ``message`` and have
#: the gap read as an empty string. ``suggestions`` is not written by a check
#: at all: every check builds a finding without it and
#: ``suggest.with_suggestions`` attaches candidates afterwards, under
#: ``--suggest`` only. An empty tuple is the honest value for a finding nobody
#: derived anything for, and the JSON report omits the key rather than writing
#: an empty array.
#:
#: This is a set of one on purpose. A second entry here is a second field whose
#: absence means something, and adding one has to be as deliberate as this was.
FIELDS_WITH_A_DEFAULT = {"suggestions"}

RULE_FIELDS = [("citation", "str"), ("url", "str"), ("retrieved", "str")]


def test_all_is_exactly_the_documented_surface() -> None:
    assert sorted(ctdl_validate.__all__) == sorted(PUBLIC)


def test_every_public_name_is_importable() -> None:
    for name in PUBLIC:
        assert hasattr(ctdl_validate, name), name


def test_every_public_signature_is_the_one_that_was_promised() -> None:
    for name, expected in PUBLIC.items():
        if expected is None:
            continue
        actual = str(inspect.signature(getattr(ctdl_validate, name)))
        assert actual == expected, f"{name}{actual} is not the promised {name}{expected}"


def test_finding_and_rule_keep_their_fields() -> None:
    assert [(f.name, f.type) for f in dataclasses.fields(Finding)] == FINDING_FIELDS
    assert [(f.name, f.type) for f in dataclasses.fields(Rule)] == RULE_FIELDS


def test_no_field_of_a_finding_is_optional_but_the_one_named_exemption() -> None:
    """A Finding cannot be built short of a *reported* field and have the gap
    read as an empty string. See ``FIELDS_WITH_A_DEFAULT`` for the single
    derived field that is exempt and why."""
    optional = {
        field.name
        for field in dataclasses.fields(Finding)
        if field.default is not dataclasses.MISSING
        or field.default_factory is not dataclasses.MISSING
    }
    assert optional == FIELDS_WITH_A_DEFAULT


def test_finding_and_rule_are_frozen() -> None:
    """A consumer holding a Finding must not be able to change it under the
    code that produced it."""
    rule = Rule(citation="c", url="https://example.invalid/", retrieved="2026-01-01")
    finding = Finding("CODE", Severity.ERROR, "urn:ctid:x", "prop", "value", "message", rule)
    for instance, field_name in ((rule, "citation"), (finding, "severity")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(instance, field_name, "changed")


def test_severity_members_are_the_four_the_report_declares() -> None:
    assert [s.value for s in Severity] == ["ERROR", "WARNING", "INFO", "UNVERIFIABLE"]


def test_the_api_document_names_every_public_symbol() -> None:
    """A promise nobody can read is not a promise."""
    documented = API_DOC.read_text(encoding="utf-8")
    for name in PUBLIC:
        assert f"`{name}`" in documented, f"docs/API.md does not mention {name}"


def test_the_api_document_states_the_stability_rule() -> None:
    documented = API_DOC.read_text(encoding="utf-8")
    assert "Semantic Versioning" in documented
    assert "report_schema_version" in documented


def test_the_changelog_records_this_surface_being_named() -> None:
    """The pin above is only half of it: the surface has to be announced.

    This is the mechanical half of "no signature change without a CHANGELOG
    entry" -- it checks the entry that named the API exists at all, so the
    document and the promise cannot land without one."""
    assert "docs/API.md" in CHANGELOG.read_text(encoding="utf-8")
