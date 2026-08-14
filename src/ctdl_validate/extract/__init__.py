"""Deterministic extraction of CTDL-shaped JSON-LD from a page's own markup.

This package is the ``extract`` subcommand. It is separate from validation on
purpose, and the boundary is worth stating plainly:

- **Validation** (``ctdl-validate <file.json>``) makes no network calls and no
  model calls, and returns the same output for the same input, byte for byte.
  Adding this package does not change that. Nothing under
  :mod:`ctdl_validate.checks` imports anything here.
- **Extraction** (``ctdl-validate extract <url>``) fetches exactly one page,
  politely and under a stated posture (see :mod:`ctdl_validate.extract.fetch`),
  and is otherwise a pure function of the bytes it fetched: the same page text
  produces the same document and the same notes, byte for byte.

There are no model calls here either. Extraction reads the structured markup a
page already publishes (JSON-LD, microdata, RDFa Lite) and maps it onto CTDL
only where Credential Engine's published schema encoding declares an
equivalence. It cannot read a credential out of prose, and it will not try:
the price of never inventing a credential that was not on the page is that
pages without structured markup yield nothing at all.
"""

from __future__ import annotations

from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchError, FetchResult
from .markup import extract_from_html, read_page
from .report import Block, Extraction, Note

__all__ = [
    "DEFAULT_USER_AGENT",
    "Block",
    "Extraction",
    "FetchError",
    "FetchResult",
    "Fetcher",
    "Note",
    "extract_from_html",
    "read_page",
]
