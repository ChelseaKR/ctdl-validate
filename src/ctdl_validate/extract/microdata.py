"""Reader 2: HTML microdata (``itemscope``, ``itemtype``, ``itemprop``).

Value extraction follows the HTML Living Standard, section 5.2.4 Values, case
for case. Property names follow section 5.2.3: an absolute URL is a name in
its own right, and a bare name on a *typed* item belongs to the vocabulary
that defines the item's type. On an *untyped* item the standard says a bare
name is proprietary, defined by no public specification, so this reader has
nothing to resolve it against and says so instead of assuming schema.org.

One normalization is applied to text values: runs of white space are
collapsed to single spaces and the result is trimmed, because HTML collapses
white space when it renders and the indentation in the source is not part of
the value an author published. Nothing else about a value is altered.
"""

from __future__ import annotations

from urllib.parse import urljoin

from .. import rules
from ..findings import Severity
from ..schema import SchemaIndex
from .dom import Element
from .items import MICRODATA, RawItem, RawValue
from .report import Note
from .terms import is_absolute_iri, normalize_term, vocabulary_of

#: HTML Living Standard 5.2.4: elements whose value is their ``src`` URL.
SRC_ELEMENTS = frozenset({"audio", "embed", "iframe", "img", "source", "track", "video"})
#: ... their ``href`` URL.
HREF_ELEMENTS = frozenset({"a", "area", "link"})


def collapse(text: str) -> str:
    return " ".join(text.split())


class _MicrodataReader:
    def __init__(self, schema: SchemaIndex, base_url: str) -> None:
        self.schema = schema
        self.base_url = base_url
        self.notes: list[Note] = []
        self._itemref_reported = False

    def _value(self, element: Element, path: str, language: str | None) -> RawValue | None:
        """The property value of an element, per HTML Living Standard 5.2.4."""
        attrs = element.attrs
        if element.tag == "meta":
            return self._literal(attrs.get("content", ""), path, language)
        if element.tag in SRC_ELEMENTS:
            return self._reference(attrs.get("src", ""), path)
        if element.tag in HREF_ELEMENTS:
            return self._reference(attrs.get("href", ""), path)
        if element.tag == "object":
            return self._reference(attrs.get("data", ""), path)
        if element.tag in ("data", "meter"):
            return self._literal(attrs.get("value", ""), path, language)
        if element.tag == "time":
            return self._literal(attrs.get("datetime", element.text()), path, language)
        return self._literal(element.text(), path, language)

    def _literal(self, text: str, path: str, language: str | None) -> RawValue | None:
        collapsed = collapse(text)
        if not collapsed:
            self._empty(path)
            return None
        return RawValue(text=collapsed, language=language)

    def _reference(self, url: str, path: str) -> RawValue | None:
        if not url.strip():
            self._empty(path)
            return None
        return RawValue(iri=urljoin(self.base_url, url.strip()))

    def _empty(self, path: str) -> None:
        self.notes.append(
            Note(
                code="EMPTY_VALUE",
                severity=Severity.INFO,
                subject=path,
                term="(value)",
                detail=(
                    "The element carries an itemprop but publishes no value for it. "
                    "An empty value asserts nothing, so nothing was emitted."
                ),
                rule=rules.MICRODATA_VALUES,
            )
        )

    def _names(self, element: Element, vocab: str | None, path: str) -> list[str]:
        names: list[str] = []
        for token in element.attrs.get("itemprop", "").split():
            if is_absolute_iri(token):
                names.append(normalize_term(token, self.schema))
            elif vocab is not None:
                names.append(normalize_term(vocab + token, self.schema))
            else:
                self.notes.append(
                    Note(
                        code="MICRODATA_NAME_UNRESOLVED",
                        severity=Severity.WARNING,
                        subject=path,
                        term=token,
                        detail=(
                            "A bare itemprop name on an item with no itemtype. The "
                            "standard makes such a name proprietary to the author, so "
                            "there is no vocabulary to resolve it against and it was "
                            "left unread."
                        ),
                        rule=rules.MICRODATA_NAMES,
                    )
                )
        return names

    def _check_itemref(self, element: Element, path: str) -> None:
        if "itemref" not in element.attrs or self._itemref_reported:
            return
        self._itemref_reported = True
        self.notes.append(
            Note(
                code="MICRODATA_ITEMREF",
                severity=Severity.WARNING,
                subject=path,
                term=element.attrs["itemref"],
                detail=(
                    "This page associates properties with items through itemref. This "
                    "reader does not follow itemref, so any property reached only that "
                    "way is missing from the extract."
                ),
                rule=rules.MICRODATA_ITEMREF,
            )
        )

    def _properties(
        self, element: Element, path: str, vocab: str | None, language: str | None
    ) -> list[tuple[str, RawValue]]:
        """Properties contributed by an element's subtree, not descending into items."""
        props: list[tuple[str, RawValue]] = []
        for child in element.children:
            child_language = child.attrs.get("lang") or child.attrs.get("xml:lang") or language
            self._check_itemref(child, path)
            if "itemprop" in child.attrs:
                props.extend(self._property(child, path, vocab, child_language, len(props)))
            elif "itemscope" not in child.attrs:
                props.extend(self._properties(child, path, vocab, child_language))
        return props

    def _property(
        self, element: Element, path: str, vocab: str | None, language: str | None, index: int
    ) -> list[tuple[str, RawValue]]:
        names = self._names(element, vocab, f"{path}.itemprop[{index}]")
        if not names:
            return []
        value_path = f"{path}.{names[0]}[{index}]"
        if "itemscope" in element.attrs:
            value = RawValue(item=self.read_item(element, value_path, language))
        else:
            found = self._value(element, value_path, language)
            if found is None:
                return []
            value = found
        return [(name, value) for name in names]

    def read_item(self, element: Element, path: str, language: str | None) -> RawItem:
        raw_types = element.attrs.get("itemtype", "").split()
        vocab = vocabulary_of(raw_types[0]) if raw_types else None
        item_id = element.attrs.get("itemid")
        self._check_itemref(element, path)
        return RawItem(
            fmt=MICRODATA,
            path=path,
            types=tuple(normalize_term(t, self.schema) for t in raw_types),
            item_id=urljoin(self.base_url, item_id) if item_id else None,
            props=tuple(self._properties(element, path, vocab, language)),
        )


def _top_level_elements(element: Element, language: str | None) -> list[tuple[Element, str | None]]:
    """Item elements that are not themselves property values, in document order."""
    found: list[tuple[Element, str | None]] = []
    for child in element.children:
        child_language = child.attrs.get("lang") or child.attrs.get("xml:lang") or language
        if "itemscope" in child.attrs and "itemprop" not in child.attrs:
            found.append((child, child_language))
        else:
            found.extend(_top_level_elements(child, child_language))
    return found


def read_microdata(
    root: Element, base_url: str, schema: SchemaIndex
) -> tuple[list[RawItem], list[Note]]:
    reader = _MicrodataReader(schema, base_url)
    items = [
        reader.read_item(element, f"microdata[{index}]", language)
        for index, (element, language) in enumerate(_top_level_elements(root, None))
    ]
    return items, reader.notes
