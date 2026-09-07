"""The published shape of ``--format json``, and the version of that shape.

``--format json`` is not a debugging convenience. The GitHub Action reads its
``summary`` counts to apply ``fail-on``, the playground renders the same
report through Pyodide and offers it as a download, and the Registry survey
harness reads its ``findings``. Until now the shape was defined only by the
function that writes it, which means a renamed key would have been a silent
change to every consumer -- and for a consumer that reads a count out of
``summary``, a silently missing key reads as zero, which is a clean gate. That
is the defect this tool exists to catch, in the tool's own output.

So the shape is published, as ``report.schema.json`` beside this module, and
every report says which version of it the report conforms to.

``REPORT_SCHEMA_VERSION`` moves independently of the tool's version:

- the **major** part changes when a consumer that reads the current shape
  would break -- a key removed or renamed, a type changed, a value that used
  to be present becoming optional;
- the **minor** part changes when a key is added that a consumer may ignore;
- the **patch** part changes when only the schema's own prose changes.

The schema sets ``additionalProperties: false`` throughout, so a consumer that
validates its input learns about a new key rather than passing over it. That
makes a minor bump visible to anyone who checks, which is the point: the
alternative is a consumer silently reading a report it does not understand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The version of ``report.schema.json``, stamped into every JSON report.
#: See the module docstring for what each part means.
REPORT_SCHEMA_VERSION = "1.1.0"

#: The schema itself, shipped as package data so an installed copy -- and the
#: playground's Pyodide wheel -- can print it. ``pyproject.toml`` lists it
#: under ``package-data``; ``tests/test_report_schema.py`` fails if that entry
#: is dropped.
REPORT_SCHEMA_PATH = Path(__file__).resolve().parent / "report.schema.json"


def read_report_schema() -> str:
    """The schema as published, byte for byte."""
    return REPORT_SCHEMA_PATH.read_text(encoding="utf-8")


@dataclass(frozen=True)
class DocumentScope:
    """How much of a parsed document this tool has jurisdiction over.

    ``ctdl-validate`` checks terms in the ``ceterms:`` and ``ceasn:``
    namespaces (:func:`ctdl_validate.schema.is_checked_term`). A document that
    declares none of them trips no rule -- correctly, because there is nothing
    in it this tool has anything to say about. What is *not* correct is that
    the report of such a run has been indistinguishable from the report of a
    clean CTDL payload: both read ``0 finding(s): 0 ERROR, ...`` and exit 0.

    Measured on 2026-09-07: ``package.json``, ``tsconfig.json``, ``{}``,
    ``[]``, this repository's own ``report.schema.json`` and the vendored
    ``vendor/ctdl/context.json`` each produce exactly that report. The sibling
    tool refuses the same input -- ``oscal-validate`` exits 2 with "no OSCAL
    model root found" -- and the difference matters most in a pre-commit hook,
    where ``types: [json]`` hands the validator every JSON file in a
    repository and a wall of clean reports over files that are not CTDL reads
    as a passing gate (#63).

    So the count is published beside the findings. ``checked_entities`` is
    zero exactly when the run had nothing to check, and a reader who sees zero
    findings can tell the two conditions apart. Nothing here changes a
    severity, a finding, or an exit code: the exit contract in ``docs/API.md``
    is unchanged, because a document that parses is not a document that could
    not be read.
    """

    #: Entities the walk registered, including nested ones.
    entities: int
    #: Of those, how many declare at least one term this tool checks -- as a
    #: ``@type`` or as a property key. Both are counted because a node can
    #: carry ``ceterms:`` properties under a class the snapshot does not name,
    #: and such a node is squarely this tool's business.
    checked_entities: int
