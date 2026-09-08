"""Orchestration: run every check over a parsed document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .checks import ALL_CHECKS
from .findings import Finding, finalize
from .graph import parse_document
from .schema import load_schema
from .session import Session, Supplied, build_supplied
from .suggest import with_suggestions


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


def validate(session: Session, *, suggest: bool = False) -> list[Finding]:
    """Run every check over an assembled session.

    ``suggest`` attaches determined re-spellings to the findings that have
    one (:mod:`ctdl_validate.suggest`). It runs *after* ``finalize``, so it
    cannot change which findings there are, their order, or their identity;
    with it off, nothing in this module's output moves.
    """
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(session))
    final = finalize(findings)
    return with_suggestions(session, final) if suggest else final


def validate_document(
    data: Any, resolve: list[Path] | None = None, *, suggest: bool = False
) -> list[Finding]:
    """Validate a decoded CTDL JSON-LD document.

    Accepts an object with @graph, a single entity object, or an array of
    entities. Returns findings in a deterministic order. Raises
    graph.DocumentError for shapes the tool does not read.

    ``resolve`` is optional and additive: see :mod:`ctdl_validate.session`.
    ``suggest`` is optional and additive too: it adds candidate re-spellings
    to findings that have a determined one and changes nothing else.
    """
    return validate(build_session(data, resolve), suggest=suggest)
