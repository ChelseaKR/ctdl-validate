"""The check registry, in the order the README documents them."""

from __future__ import annotations

from collections.abc import Callable

from ..findings import Finding
from ..session import Session
from . import (
    concept_scheme,
    ctid_format,
    domain_range,
    identifier_kind,
    identity,
    inverses,
    language_map,
    references,
)

Check = Callable[[Session], list[Finding]]

ALL_CHECKS: tuple[Check, ...] = (
    ctid_format.check,
    identifier_kind.check,
    references.check,
    domain_range.check,
    inverses.check,
    identity.check,
    concept_scheme.check,
    language_map.check,
)

__all__ = ["ALL_CHECKS", "Check"]
