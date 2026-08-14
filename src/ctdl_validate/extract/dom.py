"""A small, tolerant HTML tree, built on the standard library's html.parser.

This is deliberately not a conforming HTML5 tree constructor, in the same
spirit as :mod:`ctdl_validate.graph` being deliberately not a general JSON-LD
processor: microdata and RDFa need element nesting, attributes, and text, and
nothing else. A handful of well-known implied end tags are handled (``p``,
``li``, table cells, ``dt``/``dd``, ``option``); beyond those, a page that
relies on implied end tags can nest items differently here than a browser
would, which is recorded in the extraction limits section of the README.

No network, no encoding guesswork: the caller decodes bytes to text and hands
the text in.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser

#: Deepest element nesting this reader will build. Real pages sit well under
#: it; past it a document is either pathological or hostile, and every walk
#: over the tree below is recursive, so the limit is refused rather than
#: absorbed. See SECURITY.md.
MAX_DEPTH = 200


class MarkupError(ValueError):
    """The page is not something this reader will build a tree from."""


#: Elements with no end tag (HTML Living Standard, "void elements").
VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

#: Start tags that implicitly close still-open elements, and what they close.
_IMPLIED_END = {
    "li": frozenset({"li"}),
    "p": frozenset({"p"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "tr": frozenset({"tr", "td", "th"}),
    "td": frozenset({"td", "th"}),
    "th": frozenset({"td", "th"}),
    "option": frozenset({"option"}),
}


@dataclass
class Element:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    #: Children in document order; a ``str`` child is a run of text.
    nodes: list[Element | str] = field(default_factory=list)

    @property
    def children(self) -> list[Element]:
        return [n for n in self.nodes if isinstance(n, Element)]

    def text(self) -> str:
        """Descendant text content, in document order.

        ``script`` and ``style`` subtrees are excluded: their contents are
        program text, not prose, and including them would corrupt any value
        read from an enclosing element.
        """
        parts: list[str] = []
        for node in self.nodes:
            if isinstance(node, str):
                parts.append(node)
            elif node.tag not in ("script", "style"):
                parts.append(node.text())
        return "".join(parts)

    def walk(self) -> Iterator[Element]:
        """This element, then every descendant element, in document order."""
        yield self
        for child in self.children:
            yield from child.walk()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element(tag="#document")
        self._stack: list[Element] = [self.root]

    def _close_implied(self, tag: str) -> None:
        closes = _IMPLIED_END.get(tag)
        if closes is None:
            return
        while len(self._stack) > 1 and self._stack[-1].tag in closes:
            self._stack.pop()

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> Element:
        self._close_implied(tag)
        element = Element(tag=tag, attrs={name: value or "" for name, value in attrs})
        self._stack[-1].nodes.append(element)
        return element

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = self._open(tag, attrs)
        if tag in VOID_ELEMENTS:
            return
        if len(self._stack) > MAX_DEPTH:
            raise MarkupError(
                f"element nesting deeper than {MAX_DEPTH}; this page is not read rather "
                "than read partially"
            )
        self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self._stack) - 1, 0, -1):
            if self._stack[depth].tag == tag:
                del self._stack[depth:]
                return
        # An end tag with no matching open element: ignore it rather than
        # unwinding the tree on the strength of a guess.

    def handle_data(self, data: str) -> None:
        self._stack[-1].nodes.append(data)


def parse_html(source: str) -> Element:
    """Parse an HTML document into a tree rooted at a ``#document`` element."""
    builder = _TreeBuilder()
    builder.feed(source)
    builder.close()
    return builder.root
