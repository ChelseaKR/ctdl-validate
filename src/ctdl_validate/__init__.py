"""ctdl-validate: deterministic structural validation for CTDL JSON-LD payloads."""

from __future__ import annotations

__version__ = "0.1.0"

from .findings import Finding, Rule, Severity
from .validator import validate_document

__all__ = ["Finding", "Rule", "Severity", "__version__", "validate_document"]
