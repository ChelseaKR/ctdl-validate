"""SARIF 2.1.0 output: the same findings, in the format code-scanning viewers read.

The JSON report (``--format json``) is the canonical machine-readable form.
This module renders the same findings into SARIF without adding to them,
dropping any, or merging any. Four rules of the rendering are worth stating,
because each one is a place where a format conversion could quietly turn "not
checked" into "passed".

**Severity to result ``kind`` and ``level``.** SARIF separates what a result
*is* (``kind``) from how loudly to show it (``level``). The tool's four
severities map onto both:

===============  =================  =========
severity         kind               level
===============  =================  =========
ERROR            ``fail``           ``error``
WARNING          ``fail``           ``warning``
INFO             ``informational``  ``note``
UNVERIFIABLE     ``open``           ``note``
===============  =================  =========

``open`` is SARIF's own word for "the rule was evaluated and the result could
not be settled", which is exactly what UNVERIFIABLE means here. No result is
ever rendered with ``kind: pass``: this tool reports findings and only
findings, and an empty ``results`` array means the run produced none, never
that something was checked and passed.

One deliberate departure from the specification's prose: SARIF 2.1.0
section 3.27.10 says a result whose ``kind`` is not ``fail`` should carry
``level: none``. GitHub code scanning ignores ``kind`` and decides what to
display from ``level`` alone, documenting ``note``, ``warning`` and ``error``
as the levels it renders. A ``level: none`` UNVERIFIABLE finding would
therefore vanish from the one place this format is most often read, which is
the absence-as-pass this tool exists to refuse. So non-``fail`` results carry
``level: note``. The schema accepts it; a viewer that honours ``kind`` sees
the distinction; a viewer that does not still shows the finding. The tool's
own severity is carried verbatim in every result's ``properties.severity``.

**Rules.** Every finding code becomes one ``reportingDescriptor`` in
``tool.driver.rules``, with ``id`` equal to the code. A code is not always one
citation: ``RANGE_VIOLATION`` cites the CTDL encoding for a ``ceterms:`` term
and the CTDL-ASN encoding for a ``ceasn:`` one, and the CTID codes cite two
different sections of the same page. The per-finding citation, URL and
retrieval date therefore travel on each result, in ``properties.rule``,
exactly as the JSON report carries them. The rule descriptor carries
``helpUri`` when every finding under that code in this log cites one URL, and
lists every source with its retrieval date under ``properties.sources``
regardless.

**Locations.** A finding's location is the entity it is about -- an IRI, or a
blank-node identifier for an entity the payload never names. SARIF gets the
validated document as a ``physicalLocation`` (GitHub needs one to display
anything) and the entity as a ``logicalLocation``. No line or column is
reported, because the validator works on the parsed graph and does not track
one; a region would be an invented number. Documents supplied through
``--resolve`` are indexed and never validated, so every finding in a log is
about the one document named in the run's properties.

**Which bytes decided it.** ``tool.driver.properties`` carries the snapshot's
retrieval date and the SHA-256 of every vendored file the run read, computed
from the files themselves (:mod:`ctdl_validate.snapshot`). A code-scanning
alert outlives the checkout that produced it, and "ctdl-validate 0.2.1 said
so" is not enough to reproduce a verdict against a vocabulary that moves.

**Merging.** :func:`merge_logs` combines the logs of several documents into
one, because GitHub accepts at most twenty runs in an uploaded SARIF file and
a publication set is routinely more than twenty payloads. It is here, and not
in ``tools/action_runner.py``, for one reason: merging rules means re-deciding
``helpUri`` for a code now cited from two documents, and that is a rendering
decision. It is made once, in :func:`_rule_descriptor`, for both callers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .findings import Finding, Severity, counts
from .snapshot import identity

#: Where the tool is described. SARIF's ``informationUri`` for the driver.
INFORMATION_URI = "https://github.com/ChelseaKR/ctdl-validate"

#: The schema this file claims conformance with; a viewer can check it.
SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"

#: The SARIF version every log declares, and the only one this module reads.
SARIF_VERSION = "2.1.0"

#: Severity to SARIF ``(kind, level)``. See the module docstring.
KINDS: dict[Severity, tuple[str, str]] = {
    Severity.ERROR: ("fail", "error"),
    Severity.WARNING: ("fail", "warning"),
    Severity.INFO: ("informational", "note"),
    Severity.UNVERIFIABLE: ("open", "note"),
}

#: The name under which a result's stable identity is published. GitHub uses
#: ``partialFingerprints`` to match an alert across uploads; without one it
#: hashes the source line, and there is no line here.
FINGERPRINT = "ctdlValidate/finding/v1"

#: One line per finding code, describing what the code reports. These describe
#: this tool's own output; the rule each finding cites is Credential Engine's
#: and travels on the finding itself. ``tests/test_sarif.py`` fails if a code
#: the check modules can emit is missing from here.
DESCRIPTIONS: dict[str, str] = {
    "CTID_BARE_UUID": "A CTID is a bare UUID: the ce- prefix is missing.",
    "CTID_MALFORMED": "A CTID does not match the published ce- plus UUID v4 grammar.",
    "CTID_NOT_UUIDV4": "A CTID is well formed but its UUID is not version 4.",
    "CTID_UPPERCASE": "A CTID carries upper-case hexadecimal, which the grammar does not permit.",
    "CTID_URI_MISMATCH": "An entity's ceterms:ctid and the CTID in its own @id disagree.",
    "REGISTRY_URI_MALFORMED": "A Registry resource or graph URI does not end in a valid CTID.",
    "REF_BARE_UUID": "A property that must carry an identifier carries a bare UUID.",
    "REF_BARE_CTID": "A property that must carry an identifier carries a bare CTID, not a URI.",
    "REF_NOT_IRI": "A property that must carry an identifier carries something that is not one.",
    "REF_UNRESOLVED_BNODE": "A blank-node reference names a node the payload never defines.",
    "REF_RESOLVED_SUPPLIED": "A reference was resolved in a supplied document, not in the payload.",
    "REF_OUTSIDE_PAYLOAD": (
        "A reference could not be resolved from the payload or any supplied document."
    ),
    "DOMAIN_VIOLATION": "A property is used on a class its declared domain does not include.",
    "RANGE_VIOLATION": "A property's value is of a class its declared range does not include.",
    "ISPARTOF_FRAMEWORK_MISMATCH": (
        "A competency declares ceasn:isPartOf a framework other than the one it belongs to."
    ),
    "UNKNOWN_CLASS": "An @type names a class the vendored encodings do not declare.",
    "UNKNOWN_PROPERTY": "A property name is not declared by the vendored encodings.",
    "RANGE_DOCS_CONFLICT": (
        "A property's declared range and the documentation for it disagree, so it is not enforced."
    ),
    "CONCEPT_RANGE_CONFLICT": (
        "A property declares both a concept scheme and a range that is not a concept."
    ),
    "VERSION_RANGE_CONFLICT": (
        "A version-related property's declared range cannot be reconciled across the encodings."
    ),
    "INVERSE_MISMATCH": "Two properties the schema declares inverse do not agree.",
    "INVERSE_ONE_DIRECTION": "One direction of an inverse pair is present and the other is not.",
    "ID_DECLARED_MORE_THAN_ONCE": (
        "Several node objects share one @id and were read as a single entity."
    ),
    "CONCEPT_OUTSIDE_SCHEME": "A concept value belongs to a scheme other than the declared one.",
    "CONCEPT_OUTSIDE_SNAPSHOT": (
        "A concept value is not declared by the vendored snapshot, so it was not settled."
    ),
    "CONCEPT_NOT_IDENTIFIED": "A concept value carries no identifier this tool can check.",
    "LANGUAGE_MAP_EXPECTED": (
        "A property the context declares as a language map carries a bare literal."
    ),
    "TERM_UNSTABLE": "A term the encoding marks vs:unstable is used; it is disclosed, not judged.",
}


def _artifact_uri(path: Path) -> str:
    """A relative path as given, or a ``file:`` URI for an absolute one."""
    return path.as_uri() if path.is_absolute() else path.as_posix()


def _logical_location(entity: str) -> dict[str, str]:
    """The entity a finding is about, as a SARIF logical location.

    ``name`` is the short form a viewer shows in a list -- the CTID for a
    Registry URI, the identifier for a blank node -- and
    ``fullyQualifiedName`` is the entity exactly as the report carries it.
    """
    name = entity.rsplit("/", 1)[-1] if "/" in entity else entity
    return {"name": name, "fullyQualifiedName": entity}


def _fingerprint(finding: Finding) -> str:
    identity_of = "\x1f".join(
        (finding.code, finding.entity, finding.prop, finding.rule.url, finding.rule.citation)
    )
    return hashlib.sha256(identity_of.encode("utf-8")).hexdigest()


def _message(finding: Finding) -> str:
    return (
        f"{finding.prop} = {finding.value} on {finding.entity}. {finding.message}\n\n"
        f"Rule: {finding.rule.citation}\n"
        f"Source: {finding.rule.url} (retrieved {finding.rule.retrieved})"
    )


def _result(finding: Finding, rule_index: int, document: Path) -> dict[str, Any]:
    kind, level = KINDS[finding.severity]
    return {
        "ruleId": finding.code,
        "ruleIndex": rule_index,
        "kind": kind,
        "level": level,
        "message": {"text": _message(finding)},
        "locations": [
            {
                "physicalLocation": {"artifactLocation": {"uri": _artifact_uri(document)}},
                "logicalLocations": [_logical_location(finding.entity)],
            }
        ],
        "partialFingerprints": {FINGERPRINT: _fingerprint(finding)},
        "properties": {
            "severity": finding.severity.value,
            "entity": finding.entity,
            "property": finding.prop,
            "value": finding.value,
            "rule": {
                "citation": finding.rule.citation,
                "url": finding.rule.url,
                "retrieved": finding.rule.retrieved,
            },
        },
    }


def _rule_descriptor(code: str, cited: set[tuple[str, str]]) -> dict[str, Any]:
    """One ``reportingDescriptor`` for a code cited from ``(url, retrieved)`` pairs.

    The single place ``helpUri`` is decided, so that a code cited from two
    sources loses its single help URI identically whether the two citations
    came from one document or from two documents merged together.
    """
    ordered = sorted(cited)
    rule: dict[str, Any] = {"id": code, "name": code}
    description = DESCRIPTIONS.get(code)
    if description is not None:
        rule["shortDescription"] = {"text": description}
    urls = {url for url, _ in ordered}
    if len(urls) == 1 and next(iter(urls)).startswith(("http://", "https://")):
        rule["helpUri"] = next(iter(urls))
    rule["properties"] = {
        "sources": [{"url": url, "retrieved": retrieved} for url, retrieved in ordered]
    }
    return rule


def _rules(findings: list[Finding]) -> list[dict[str, Any]]:
    sources: dict[str, set[tuple[str, str]]] = {}
    for finding in findings:
        sources.setdefault(finding.code, set()).add((finding.rule.url, finding.rule.retrieved))
    return [_rule_descriptor(code, sources[code]) for code in sorted(sources)]


def driver(version: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    """The ``tool.driver`` every log carries, snapshot identity included."""
    return {
        "name": "ctdl-validate",
        "version": version,
        "semanticVersion": version,
        "informationUri": INFORMATION_URI,
        "properties": {"vendoredSnapshot": identity()},
        "rules": rules,
    }


def render_findings_sarif(findings: list[Finding], version: str, document: Path) -> str:
    """The SARIF 2.1.0 log for one validation run, as deterministic JSON."""
    rules = _rules(findings)
    index = {rule["id"]: position for position, rule in enumerate(rules)}
    log = {
        "$schema": SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": driver(version, rules)},
                "results": [_result(f, index[f.code], document) for f in findings],
                "properties": {
                    "document": {"path": _artifact_uri(document)},
                    "summary": counts(findings),
                },
            }
        ],
    }
    return json.dumps(log, indent=2, sort_keys=True, ensure_ascii=False)


def _one_run(log: Any, which: int) -> dict[str, Any]:
    """The single run of a log this module produced, or a stated refusal."""
    if not isinstance(log, dict) or log.get("version") != SARIF_VERSION:
        raise ValueError(f"log {which} does not declare SARIF {SARIF_VERSION}")
    runs = log.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(runs[0], dict):
        raise ValueError(f"log {which} does not carry exactly one run")
    run: dict[str, Any] = runs[0]
    return run


def merge_logs(logs: Sequence[Any]) -> str:
    """Several single-document logs as one log with one run.

    GitHub accepts at most twenty runs in an uploaded SARIF file, so one run
    per document stops working at the twenty-first -- and a publication set of
    twenty-one CTDL payloads is an ordinary set, not an edge case.

    Nothing is dropped, deduplicated or re-levelled: the results are
    concatenated in the order the documents were given, each result's
    ``ruleIndex`` is re-pointed at the merged rules array, and the run's
    ``summary`` is the sum of the summaries. Every driver must be identical,
    including its snapshot digests, because a log merged across two different
    vendored snapshots would attribute one snapshot's verdicts to the other.
    """
    if not logs:
        raise ValueError("no logs to merge")
    runs = [_one_run(log, which) for which, log in enumerate(logs)]

    drivers = [run["tool"]["driver"] for run in runs]
    versions = {json.dumps(d, sort_keys=True) for d in ({**d, "rules": []} for d in drivers)}
    if len(versions) != 1:
        raise ValueError("the logs were not produced by one tool and one vendored snapshot")

    sources: dict[str, set[tuple[str, str]]] = {}
    for run_driver in drivers:
        for rule in run_driver["rules"]:
            cited = sources.setdefault(rule["id"], set())
            for source in rule["properties"]["sources"]:
                cited.add((source["url"], source["retrieved"]))
    rules = [_rule_descriptor(code, sources[code]) for code in sorted(sources)]
    index = {rule["id"]: position for position, rule in enumerate(rules)}

    results: list[dict[str, Any]] = []
    summary = counts([])
    documents = []
    for which, run in enumerate(runs):
        for result in run["results"]:
            results.append({**result, "ruleIndex": index[result["ruleId"]]})
        totals = run["properties"]["summary"]
        if set(totals) != set(summary):
            raise ValueError(f"log {which} does not count the severities this tool reports")
        for severity, count in totals.items():
            summary[severity] += count
        documents.append(run["properties"]["document"])

    merged = {
        "$schema": SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": {**drivers[0], "rules": rules}},
                "results": results,
                "properties": {"documents": documents, "summary": summary},
            }
        ],
    }
    return json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False)
