"""What extraction reports, and how it renders.

Extraction produces two things: a CTDL-shaped document containing only what
the page literally published, and a list of notes saying what was read, what
was dropped, and why. The notes carry the same obligation as validation
findings: each one cites the published rule behind it, with a source URL and a
retrieval date, and the ``Note`` model makes a note without a citation
impossible to construct.

Severities keep the meanings :mod:`ctdl_validate.findings` gives them, read in
the extraction context:

- **WARNING**: the page published something that did not survive the mapping.
  Nothing is wrong with the page; the extract is simply narrower than the
  page, and the operator needs to know exactly where.
- **INFO**: worth a human look, not a loss. A related-but-not-equivalent
  class, an untagged language map, the absence of a CTID.
- **UNVERIFIABLE**: reserved for validation. Extraction reports what it read;
  whether the result is publishable is the validator's question.

ERROR is deliberately unused here. Extraction either completes and reports, or
fails outright with a :class:`~ctdl_validate.extract.fetch.FetchError` and a
nonzero exit code; there is no partial success dressed up as an error line.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..findings import Rule, Severity

_SEVERITY_ORDER = (Severity.WARNING, Severity.INFO)


@dataclass(frozen=True)
class Note:
    code: str
    severity: Severity
    subject: str
    term: str
    detail: str
    rule: Rule

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "subject": self.subject,
            "term": self.term,
            "detail": self.detail,
            "rule": {
                "citation": self.rule.citation,
                "url": self.rule.url,
                "retrieved": self.rule.retrieved,
            },
        }

    def render_text(self) -> str:
        return (
            f"{self.severity.value:12} {self.code}  at={self.subject}\n"
            f"    term = {self.term}\n"
            f"    {self.detail}\n"
            f"    rule: {self.rule.citation}\n"
            f"    source: {self.rule.url} (retrieved {self.rule.retrieved})"
        )


@dataclass(frozen=True)
class Block:
    """One structured-data block found in the page."""

    fmt: str
    path: str
    items: int
    types: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.fmt,
            "path": self.path,
            "items": self.items,
            "types": list(self.types),
        }


@dataclass(frozen=True)
class Extraction:
    """The result of reading one page's structured markup."""

    source: str
    document: dict[str, Any]
    blocks: tuple[Block, ...]
    notes: tuple[Note, ...]

    @property
    def entities(self) -> int:
        graph = self.document.get("@graph")
        return len(graph) if isinstance(graph, list) else 0

    def note_counts(self) -> dict[str, int]:
        return {
            severity.value: sum(1 for note in self.notes if note.severity is severity)
            for severity in _SEVERITY_ORDER
        }


def render_document(extraction: Extraction) -> str:
    """The extracted CTDL JSON-LD document alone, ready to pipe into validation."""
    return json.dumps(extraction.document, indent=2, sort_keys=True, ensure_ascii=False)


def render_json(extraction: Extraction, tool_version: str, fetch: dict[str, object]) -> str:
    payload = {
        "tool": {"name": "ctdl-validate", "version": tool_version, "command": "extract"},
        "source": extraction.source,
        "fetch": fetch,
        "blocks": [block.to_dict() for block in extraction.blocks],
        "document": extraction.document,
        "notes": [note.to_dict() for note in extraction.notes],
        "summary": {"entities": extraction.entities, **extraction.note_counts()},
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _block_lines(extraction: Extraction) -> list[str]:
    if not extraction.blocks:
        return ["structured data: none found (no JSON-LD, microdata, or RDFa)"]
    lines = ["structured data found:"]
    for block in extraction.blocks:
        types = ", ".join(block.types) if block.types else "no types declared"
        lines.append(f"    {block.fmt:10} {block.path}  {block.items} item(s): {types}")
    return lines


def render_text(extraction: Extraction) -> str:
    counts = extraction.note_counts()
    summary = ", ".join(f"{counts[s.value]} {s.value}" for s in _SEVERITY_ORDER)
    lines = [f"source: {extraction.source}", *_block_lines(extraction), ""]
    lines.extend(note.render_text() + "\n" for note in extraction.notes)
    lines.append(
        f"{extraction.entities} CTDL entity(ies) extracted; "
        f"{len(extraction.notes)} note(s): {summary}"
    )
    return "\n".join(lines)
