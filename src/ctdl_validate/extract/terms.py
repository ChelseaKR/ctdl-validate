"""Turning what a page wrote into a term this tool can look up.

Two small, boring problems, both solved the same way: read the published
files, do not guess.

1. schema.org publishes its vocabulary under both ``http://schema.org/`` and
   ``https://schema.org/``. Its own JSON-LD context declares ``{"@vocab":
   "http://schema.org/"}`` while the CTDL context declares the ``schema``
   prefix as ``https://schema.org/``. Both forms are normalized to the CTDL
   context's form so that the two published files agree with each other.
2. A term arrives either as a full IRI (microdata ``itemtype``, RDFa with a
   ``vocab``) or already compacted (``schema:name`` in hand-written JSON-LD).
   Both are compacted through the vendored contexts, so the rest of the code
   only ever sees ``prefix:local``.
"""

from __future__ import annotations

from ..schema import SchemaIndex

SCHEMA_ORG_HTTP = "http://schema.org/"
SCHEMA_ORG_HTTPS = "https://schema.org/"


def normalize_term(term: str, schema: SchemaIndex) -> str:
    """Compact a term IRI, folding schema.org's http form onto its https form."""
    if term.startswith(SCHEMA_ORG_HTTP):
        term = SCHEMA_ORG_HTTPS + term[len(SCHEMA_ORG_HTTP) :]
    return schema.compact_iri(term)


def is_absolute_iri(value: str) -> bool:
    """True for a value with a scheme, which is what makes it an identifier.

    Deliberately loose, matching the validator's own identifier-kind check:
    the question here is only whether the markup handed over something that
    can be used as an IRI, not whether it is a well-formed one.
    """
    scheme, separator, rest = value.partition(":")
    return bool(separator and rest and scheme.isascii() and scheme.isalnum())


def vocabulary_of(type_iri: str) -> str | None:
    """The namespace of a type IRI, or None when it has none.

    Used for microdata, where a bare ``itemprop`` name on a typed item belongs
    to the vocabulary that defines the item's type (HTML Living Standard,
    section 5.2.3).
    """
    if "://" not in type_iri:
        return None
    authority_start = type_iri.index("://") + 3
    cut = max(type_iri.rfind("#"), type_iri.rfind("/"))
    if cut < authority_start or cut == len(type_iri) - 1:
        return None
    return type_iri[: cut + 1]
