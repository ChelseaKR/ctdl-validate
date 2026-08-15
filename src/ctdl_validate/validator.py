"""Orchestration: run every check over a parsed document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .checks import ALL_CHECKS
from .findings import Finding, finalize
from .graph import parse_document
from .schema import load_schema
from .session import Session, Supplied, build_supplied


def build_session(data: Any, resolve: list[Path] | None = None) -> Session:
    """Assemble the primary payload, the schema, and any supplied documents.

    ``resolve`` names further CTDL documents, or directories of them, whose
    entities become resolvable for this run. Nothing is fetched: they are read
    from the local filesystem. They are never validated themselves.
    """
    schema = load_schema()
    return Session(
        graph=parse_document(data, schema),
        schema=schema,
        supplied=build_supplied(resolve, schema) if resolve else Supplied(),
    )


def validate(session: Session) -> list[Finding]:
    """Run every check over an assembled session."""
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(session))
    return finalize(findings)


def validate_document(data: Any, resolve: list[Path] | None = None) -> list[Finding]:
    """Validate a decoded CTDL JSON-LD document.

    Accepts an object with @graph, a single entity object, or an array of
    entities. Returns findings in a deterministic order. Raises
    graph.DocumentError for shapes the tool does not read.

    ``resolve`` is optional and additive: see :mod:`ctdl_validate.session`.
    """
    return validate(build_session(data, resolve))
