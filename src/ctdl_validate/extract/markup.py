"""Reading one page's structured markup, then mapping it onto CTDL.

Three readers run over the same document: JSON-LD script blocks, microdata,
and RDFa Lite. Each reads only what its own specification defines, and each
reports what it could not read. Their output is the same vocabulary-neutral
item model, which :mod:`ctdl_validate.extract.build` then maps onto CTDL using
the crosswalk Credential Engine publishes in its schema encodings.

Nothing in this path touches the network: it takes decoded page text and a
source URL, and returns a document and a list of notes. Given the same page
text it returns the same bytes, which is what makes the extract worth
validating.
"""

from __future__ import annotations

from urllib.parse import urljoin

from .. import rules
from ..findings import Severity
from ..schema import SchemaIndex, load_schema
from .build import build_document
from .crosswalk import load_crosswalk
from .dom import Element, parse_html
from .items import JSON_LD, MICRODATA, RDFA, RawItem, declared_types, walk_items
from .jsonld import read_block
from .microdata import read_microdata
from .rdfa import read_rdfa
from .report import Block, Extraction, Note

JSON_LD_TYPE = "application/ld+json"


def _script_blocks(root: Element) -> list[str]:
    """The source text of every ``application/ld+json`` script, in page order."""
    blocks: list[str] = []
    for element in root.walk():
        if element.tag != "script":
            continue
        declared = element.attrs.get("type", "").split(";")[0].strip().lower()
        if declared == JSON_LD_TYPE:
            blocks.append("".join(node for node in element.nodes if isinstance(node, str)))
    return blocks


def _base_url(root: Element, source_url: str) -> str:
    """The document base: a ``<base href>`` if the page declares one."""
    for element in root.walk():
        if element.tag == "base" and element.attrs.get("href"):
            return urljoin(source_url, element.attrs["href"])
    return source_url


def _count(items: list[RawItem]) -> int:
    """Items including nested ones: what the block really contains."""
    return sum(1 for _ in walk_items(items))


def _no_markup_note(source: str) -> Note:
    return Note(
        code="NO_STRUCTURED_DATA",
        severity=Severity.WARNING,
        subject=source,
        term="(page)",
        detail=(
            "The page publishes no JSON-LD, microdata, or RDFa. There is nothing to "
            "extract deterministically. Reading the credential off the prose would "
            "mean inventing structure the publisher never asserted."
        ),
        rule=rules.EXTRACTION_POLICY,
    )


def read_page(
    page: str, source_url: str, schema: SchemaIndex
) -> tuple[list[RawItem], list[Block], list[Note]]:
    root = parse_html(page)
    base = _base_url(root, source_url)

    items: list[RawItem] = []
    blocks: list[Block] = []
    notes: list[Note] = []

    for index, source in enumerate(_script_blocks(root)):
        path = f"{JSON_LD}[{index}]"
        block_items, block_notes = read_block(source, path, schema)
        items.extend(block_items)
        notes.extend(block_notes)
        blocks.append(
            Block(
                fmt=JSON_LD,
                path=path,
                items=_count(block_items),
                types=declared_types(block_items),
            )
        )

    for fmt, reader in ((MICRODATA, read_microdata), (RDFA, read_rdfa)):
        found, found_notes = reader(root, base, schema)
        items.extend(found)
        notes.extend(found_notes)
        if found:
            blocks.append(
                Block(fmt=fmt, path=fmt, items=_count(found), types=declared_types(found))
            )

    if not blocks:
        notes.append(_no_markup_note(source_url))
    return items, blocks, notes


def extract_from_html(page: str, source_url: str) -> Extraction:
    """Read a page's structured markup and map it onto CTDL. No network."""
    schema = load_schema()
    items, blocks, notes = read_page(page, source_url, schema)
    document, mapping_notes = build_document(items, source_url, schema, load_crosswalk())
    return Extraction(
        source=source_url,
        document=document,
        blocks=tuple(blocks),
        notes=tuple(notes + mapping_notes),
    )
