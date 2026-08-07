"""Orchestration: run every check over a parsed document."""

from __future__ import annotations

from typing import Any

from .checks import ALL_CHECKS
from .findings import Finding, finalize
from .graph import parse_document
from .schema import load_schema


def validate_document(data: Any) -> list[Finding]:
    """Validate a decoded CTDL JSON-LD document.

    Accepts an object with @graph, a single entity object, or an array of
    entities. Returns findings in a deterministic order. Raises
    graph.DocumentError for shapes the tool does not read.
    """
    schema = load_schema()
    graph = parse_document(data, schema)
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(graph, schema))
    return finalize(findings)
