"""ctdl-validate: deterministic structural validation for CTDL JSON-LD payloads."""

from __future__ import annotations

# Single source of version truth is pyproject.toml (REL-02). Reading it back
# from the installed distribution keeps `--version`, the JSON report stamp and
# the fetch User-Agent from drifting apart, which they did at v0.2.0.
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

try:
    __version__ = _dist_version("ctdl-validate")
except PackageNotFoundError:  # running from a source tree with no dist-info
    __version__ = "0.0.0+unknown"

from .findings import Finding, Rule, Severity
from .report import REPORT_SCHEMA_VERSION, read_report_schema
from .validator import validate_document

#: The public library surface. Everything here is documented in docs/API.md
#: with a stability promise; everything not here is internal and may move in
#: any release. ``tests/test_public_api.py`` pins these names and their
#: signatures, so widening or narrowing this list is a deliberate act.
__all__ = [
    "REPORT_SCHEMA_VERSION",
    "Finding",
    "Rule",
    "Severity",
    "__version__",
    "read_report_schema",
    "validate_document",
]
