"""The identity of the vendored CTDL snapshot, taken from the bytes it reads.

Every finding this tool emits is a claim about what Credential Engine
publishes, and the whole of what it knows is four vendored files: the CTDL and
CTDL-ASN schema encodings and their JSON-LD contexts.
``vendor/SOURCES.md`` records where each one came from and its SHA-256, and
``tests/test_vendor_integrity.py`` fails if a vendored file stops matching the
hash recorded for it.

That gate protects the repository. It does not travel with a report. A SARIF
log read six months later in someone else's code-scanning dashboard says
"ctdl-validate 0.2.1 found this", and the reader has no way to tell which
bytes decided it -- so a re-vendoring that changes a verdict is invisible at
exactly the place the verdict is read. CTDL moves: this tool already reports
``TERM_UNSTABLE`` and ``CONCEPT_OUTSIDE_SNAPSHOT`` precisely because the
vocabulary is not fixed, which makes "which snapshot" a live question rather
than a formality.

Two properties of the digests are deliberate:

**Computed, not recorded.** They are not read out of ``SOURCES.md`` or copied
from the integrity test's table. A recorded hash answers "what did we write
down"; a computed one answers "what did this run read", which is the question
a reader of an old report is actually asking. The two agreeing is
``tests/test_sarif.py::test_the_driver_digests_are_the_hashes_the_integrity_gate_records``;
if they ever disagree, the recorded one is the one that is wrong.

**Complete, or it is not an identity.** :data:`VENDORED_FILES` must name every
file under ``vendor/`` that the validator reads, and a test asserts that
against the directory itself. A snapshot identity that silently omits a file
looks like a full fingerprint while a changed encoding passes under it
unnoticed -- an absence published as a measurement, which is the class of
defect this tool exists to report.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib import resources

from .rules import RETRIEVED

#: The hash algorithm the digests are taken with, named in the output so a
#: reader never has to infer it from a hex string's length.
ALGORITHM = "sha256"

#: Every vendored file the validator reads, as a path relative to ``vendor/``.
#: ``SOURCES.md`` is the provenance record and is not itself an input.
#: ``tests/test_sarif.py`` asserts this is the whole of ``vendor/``.
VENDORED_FILES: tuple[str, ...] = (
    "ctdl/context.json",
    "ctdl/schema.json",
    "ctdlasn/context.json",
    "ctdlasn/schema.json",
)


def _read(relpath: str) -> bytes:
    path = resources.files("ctdl_validate").joinpath("vendor").joinpath(relpath)
    with path.open("rb") as handle:
        data: bytes = handle.read()
    return data


@lru_cache(maxsize=1)
def digests() -> dict[str, str]:
    """``{relative path: hex digest}`` for every vendored file, computed now.

    Cached, because the files cannot change under a running process; the cache
    is on the whole mapping, so there is no partial state to read.
    """
    return {relpath: hashlib.sha256(_read(relpath)).hexdigest() for relpath in VENDORED_FILES}


def identity() -> dict[str, object]:
    """The snapshot's identity, as a SARIF property bag.

    ``retrieved`` is the date the encodings and contexts were downloaded,
    which is what a human reads and what every rule citation already carries;
    ``files`` is what a machine checks it against.
    """
    return {
        "retrieved": RETRIEVED,
        "algorithm": ALGORITHM,
        "files": dict(sorted(digests().items())),
    }
