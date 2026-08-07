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

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    UNVERIFIABLE = "UNVERIFIABLE"


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

    def sort_key(self) -> tuple[str, str, str, str, str, str]:
        return (self.entity, self.prop, self.code, self.value, self.severity.value, self.message)

    def to_dict(self) -> dict[str, object]:
        return {
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

    def render_text(self) -> str:
        return (
            f"{self.severity.value:12} {self.code}  entity={self.entity}\n"
            f"    {self.prop} = {self.value}\n"
            f"    {self.message}\n"
            f"    rule: {self.rule.citation}\n"
            f"    source: {self.rule.url} (retrieved {self.rule.retrieved})"
        )


def finalize(findings: list[Finding]) -> list[Finding]:
    """Deduplicate and order findings deterministically."""
    return sorted(set(findings), key=Finding.sort_key)
