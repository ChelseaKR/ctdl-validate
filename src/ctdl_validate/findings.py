"""Finding model: severities, rule citations, deterministic ordering.

The severity semantics here are the contract of the whole tool:

- ERROR: the payload violates a cited structural rule.
- WARNING: a cited signal that something is very likely wrong, where the rule
  is not absolute or Registry enforcement of it is not documented.
- INFO: worth a human look; not a defect on its own.
- UNVERIFIABLE: the answer cannot be determined from the payload alone and the
  tool refuses to guess. Never counted as a pass or a fail.

Only ERROR findings make the CLI exit nonzero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from .report import REPORT_SCHEMA_VERSION, DocumentScope


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class Suggestion:
    """A re-spelling this run can determine from what it was given.

    ``difference`` says what a reader would have to change, in the tool's own
    vocabulary. Neither field asserts that ``value`` is what was meant: it
    asserts only that ``value`` is written somewhere in this run's input and
    that the finding names a defect whose correction that value supplies. See
    :mod:`ctdl_validate.suggest` for which codes can produce one and, more
    importantly, which are refused.
    """

    value: str
    difference: str

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "difference": self.difference}

    def render_text(self) -> str:
        return f"    suggested: {self.value}  ({self.difference})"


@dataclass(frozen=True)
class Rule:
    """Where a rule comes from. Every finding carries one.

    ``retrieved`` is the date the cited source was downloaded, or ``"-"`` when
    the citation is tool policy rather than an external document.
    """

    citation: str
    url: str
    retrieved: str


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    entity: str
    prop: str
    value: str
    message: str
    rule: Rule
    #: Determined re-spellings, and the only field here with a default. It is
    #: not written by a check: every check constructs a finding without it, and
    #: `suggest.with_suggestions` attaches them afterwards, under `--suggest`
    #: only. So it is derived rather than reported, an empty tuple is the
    #: honest value for a finding nothing was derived for, and it takes no part
    #: in `sort_key` or in the deduplication `finalize` does -- a suggestion is
    #: not part of a finding's identity.
    #:
    #: `tests/test_public_api.py` names this as the single exemption from "no
    #: field of a Finding is optional", so a second one cannot appear quietly.
    suggestions: tuple[Suggestion, ...] = ()

    def sort_key(self) -> tuple[str, str, str, str, str, str]:
        return (self.entity, self.prop, self.code, self.value, self.severity.value, self.message)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity.value,
            "entity": self.entity,
            "property": self.prop,
            "value": self.value,
            "message": self.message,
            "rule": {
                "citation": self.rule.citation,
                "url": self.rule.url,
                "retrieved": self.rule.retrieved,
            },
        }
        if self.suggestions:
            payload["suggestions"] = [s.to_dict() for s in self.suggestions]
        return payload

    def render_text(self) -> str:
        return (
            f"{self.severity.value:12} {self.code}  entity={self.entity}\n"
            f"    {self.prop} = {self.value}\n"
            f"    {self.message}\n"
            f"    rule: {self.rule.citation}\n"
            f"    source: {self.rule.url} (retrieved {self.rule.retrieved})"
            + "".join("\n" + s.render_text() for s in self.suggestions)
        )


def finalize(findings: list[Finding]) -> list[Finding]:
    """Deduplicate and order findings deterministically."""
    return sorted(set(findings), key=Finding.sort_key)


#: The order severities are counted and printed in, everywhere.
SEVERITY_ORDER = (Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.UNVERIFIABLE)


def counts(findings: list[Finding]) -> dict[str, int]:
    return {
        severity.value: sum(1 for f in findings if f.severity is severity)
        for severity in SEVERITY_ORDER
    }


def render_findings_json(
    findings: list[Finding], version: str, *, scope: DocumentScope | None = None
) -> str:
    """The canonical machine-readable report.

    ``report_schema_version`` names the published shape this conforms to, so a
    consumer can check what it is reading instead of inferring it from the
    tool version. See :mod:`ctdl_validate.report`.

    ``scope`` says how much of the document the run had jurisdiction over; see
    :class:`ctdl_validate.graph.DocumentScope`. ``None`` is a real third state
    and is rendered as ``null``, not as zero: a caller rendering findings it
    assembled by hand has no document to measure, and inventing a count for it
    would be the same defect this field exists to remove, pointing the other
    way.
    """
    payload = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "ctdl-validate", "version": version},
        "document": {
            "entities": None if scope is None else scope.entities,
            "checked_entities": None if scope is None else scope.checked_entities,
        },
        "findings": [f.to_dict() for f in findings],
        "summary": counts(findings),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def render_findings_text(findings: list[Finding], *, scope: DocumentScope | None = None) -> str:
    lines = [f.render_text() + "\n" for f in findings]
    summary = ", ".join(f"{counts(findings)[s.value]} {s.value}" for s in SEVERITY_ORDER)
    lines.append(f"{len(findings)} finding(s): {summary}")
    if scope is not None and scope.checked_entities == 0:
        # Said in words, not left to be inferred from a zero. Without this line
        # a run over a file that is not CTDL at all is byte-identical to a run
        # over a clean CTDL payload, which is what makes a wide pre-commit
        # `files:` pattern a gate that cannot fail (#63).
        lines.append(
            f"Nothing here was checked: {scope.entities} entit"
            f"{'y' if scope.entities == 1 else 'ies'} read, none declaring a ceterms: or "
            f"ceasn: term. This is not a clean CTDL payload; it is a document this tool has "
            f"nothing to say about."
        )
    return "\n".join(lines)
