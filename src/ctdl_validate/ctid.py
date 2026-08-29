"""CTID grammar, from the published definition.

Source ("About the CTID", https://credreg.net/ctdl/ctid, retrieved
2026-08-06): "Each CTID is made up of a standard UUID v4 prefixed with ce-",
"in the form 8-4-4-4-12", and, with the prefix, "there are a total of 34
hexadecimal characters and 5 hyphens for a total of 39 characters".
Example: ce-e8a41a52-6ff6-48f0-9872-889c87b093b7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX_GROUPS = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

#: The published grammar, strictly: lower case, ce- prefix, 8-4-4-4-12.
CTID_RE = re.compile(rf"^ce-{_HEX_GROUPS}$")
#: Same shape, any case (used to separate case problems from shape problems).
CTID_ANY_CASE_RE = re.compile(rf"^ce-{_HEX_GROUPS}$", re.IGNORECASE)
#: A UUID with no ce- prefix: the "bare UUID where a CTID belongs" bug class.
BARE_UUID_ANY_CASE_RE = re.compile(rf"^{_HEX_GROUPS}$", re.IGNORECASE)

EXPECTED_GRAMMAR = (
    "ce- followed by a UUID v4 in 8-4-4-4-12 form, 39 characters, lower case "
    "hexadecimal, e.g. ce-e8a41a52-6ff6-48f0-9872-889c87b093b7"
)

REGISTRY_RESOURCE_PREFIX = "https://credentialengineregistry.org/resources/"
REGISTRY_GRAPH_PREFIX = "https://credentialengineregistry.org/graph/"

#: Character offsets within a shape-valid CTID ("ce-" + UUID): the UUID
#: version nibble and variant nibble per RFC 4122 section 4.1.1/4.1.3.
_VERSION_OFFSET = 17
_VARIANT_OFFSET = 22


@dataclass(frozen=True)
class CtidShape:
    matches_shape: bool
    lowercase: bool
    uuid_v4: bool
    bare_uuid: bool


def classify_ctid(value: str) -> CtidShape:
    if CTID_ANY_CASE_RE.match(value):
        lowered = value.lower()
        version_ok = lowered[_VERSION_OFFSET] == "4"
        variant_ok = lowered[_VARIANT_OFFSET] in "89ab"
        return CtidShape(
            matches_shape=True,
            lowercase=value == lowered,
            uuid_v4=version_ok and variant_ok,
            bare_uuid=False,
        )
    return CtidShape(
        matches_shape=False,
        lowercase=value == value.lower(),
        uuid_v4=False,
        bare_uuid=bool(BARE_UUID_ANY_CASE_RE.match(value)),
    )


def registry_uri_tail(value: str) -> str | None:
    """The CTID portion of a Registry resource/graph URI, or None."""
    for prefix in (REGISTRY_RESOURCE_PREFIX, REGISTRY_GRAPH_PREFIX):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return None
