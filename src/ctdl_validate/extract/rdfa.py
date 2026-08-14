"""Reader 3: RDFa Lite 1.1.

RDFa Lite is the profile W3C defines as "a minimal subset of RDFa": five
attributes, ``vocab``, ``typeof``, ``property``, ``resource``, and ``prefix``.
This reader implements exactly those five. Full RDFa 1.1 Core adds ``about``,
``rel``, ``rev``, ``datatype``, and ``inlist``, whose processing rules change
which subject a statement attaches to; implementing half of them would
silently produce a different graph than the page means, so none are
implemented and an element that mixes them with RDFa Lite attributes is
reported. Several of those names are also plain HTML, so an element carrying
one with no RDFa Lite attribute (``rel`` on a stylesheet link, say) is not
RDFa at all and is not reported. Pointing this reader at thirty real pages is
what established that: without the qualification the note fired on every page
in the sample, none of which used RDFa.

Two further limits, stated rather than papered over: a prefix the page does
not declare is passed through as written (RDFa's initial context is not
implemented), and an element carrying ``property`` without ``typeof``
contributes its own value and is not descended into.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import urljoin

from .. import rules
from ..findings import Severity
from ..schema import SchemaIndex
from .dom import Element
from .items import RDFA, RawItem, RawValue
from .microdata import collapse
from .report import Note
from .terms import normalize_term

#: The five attributes RDFa Lite 1.1 defines.
LITE = ("vocab", "typeof", "property", "resource", "prefix")

#: RDFa 1.1 Core attributes outside the Lite profile. Reported only where an
#: element mixes one of these with a Lite attribute, which is the case where
#: RDFa processing would produce a statement this reader does not. Several of
#: them are also ordinary HTML: `rel` on a `<link>` or an `<a>` has nothing to
#: do with RDFa, and reporting it would be noise on almost every page.
BEYOND_LITE = ("about", "rel", "rev", "datatype", "inlist")


@dataclass(frozen=True)
class _Env:
    """Attribute state inherited down the tree: vocab, prefixes, language."""

    vocab: str | None = None
    prefixes: tuple[tuple[str, str], ...] = ()
    language: str | None = None

    def extend(self, element: Element) -> _Env:
        attrs = element.attrs
        vocab = attrs.get("vocab", self.vocab) or None
        language = attrs.get("lang") or attrs.get("xml:lang") or self.language
        prefixes = self.prefixes + _parse_prefixes(attrs.get("prefix", ""))
        return replace(self, vocab=vocab, prefixes=prefixes, language=language)

    def namespace(self, prefix: str) -> str | None:
        for declared, namespace in reversed(self.prefixes):
            if declared == prefix:
                return namespace
        return None


def _parse_prefixes(declaration: str) -> tuple[tuple[str, str], ...]:
    """Parse ``prefix="foo: http://example.org/ bar: http://example.net/"``."""
    tokens = declaration.split()
    pairs: list[tuple[str, str]] = []
    for index in range(0, len(tokens) - 1, 2):
        name = tokens[index]
        if name.endswith(":"):
            pairs.append((name[:-1], tokens[index + 1]))
    return tuple(pairs)


class _RdfaReader:
    def __init__(self, schema: SchemaIndex, base_url: str) -> None:
        self.schema = schema
        self.base_url = base_url
        self.notes: list[Note] = []
        self._beyond_lite_reported = False

    def _resolve(self, token: str, env: _Env, path: str) -> str | None:
        prefix, separator, local = token.partition(":")
        if separator:
            namespace = env.namespace(prefix)
            # An undeclared prefix is passed through as written: RDFa's initial
            # context is not implemented, and rewriting the token would be a
            # guess about which vocabulary the author meant.
            expanded = namespace + local if namespace is not None else token
            return normalize_term(expanded, self.schema)
        if env.vocab is not None:
            return normalize_term(env.vocab + token, self.schema)
        self.notes.append(
            Note(
                code="RDFA_TERM_UNRESOLVED",
                severity=Severity.WARNING,
                subject=path,
                term=token,
                detail=(
                    "A bare RDFa term with no vocab in scope. RDFa Lite resolves bare "
                    "terms against the vocab attribute; with none declared there is "
                    "nothing to resolve it against, so it was left unread."
                ),
                rule=rules.RDFA_LITE_SUBSET,
            )
        )
        return None

    def _report_beyond_lite(self, element: Element, path: str) -> None:
        if self._beyond_lite_reported or not any(name in element.attrs for name in LITE):
            return
        present = [name for name in BEYOND_LITE if name in element.attrs]
        if not present:
            return
        self._beyond_lite_reported = True
        self.notes.append(
            Note(
                code="RDFA_BEYOND_LITE",
                severity=Severity.WARNING,
                subject=path,
                term=", ".join(present),
                detail=(
                    "This element carries RDFa 1.1 Core attributes alongside RDFa Lite "
                    "ones. The Core attributes are not interpreted here, so statements "
                    "that depend on them are missing from the extract. Core attributes "
                    "on elements with no RDFa Lite attribute are ordinary HTML and are "
                    "not counted."
                ),
                rule=rules.RDFA_LITE_SUBSET,
            )
        )

    def _literal_or_reference(self, element: Element, env: _Env) -> RawValue | None:
        attrs = element.attrs
        content = attrs.get("content")
        if content is not None:
            collapsed = collapse(content)
            return RawValue(text=collapsed, language=env.language) if collapsed else None
        for attribute in ("resource", "href", "src"):
            target = attrs.get(attribute)
            if target is not None and target.strip():
                return RawValue(iri=urljoin(self.base_url, target.strip()))
        text = collapse(element.text())
        return RawValue(text=text, language=env.language) if text else None

    def _property(
        self, element: Element, env: _Env, path: str, index: int
    ) -> list[tuple[str, RawValue]]:
        tokens = element.attrs.get("property", "").split()
        names = [name for name in (self._resolve(t, env, path) for t in tokens) if name is not None]
        if not names:
            return []
        if "typeof" in element.attrs:
            value: RawValue | None = RawValue(
                item=self.read_item(element, env, f"{path}.{names[0]}[{index}]")
            )
        else:
            value = self._literal_or_reference(element, env)
        return [] if value is None else [(name, value) for name in names]

    def _properties(self, element: Element, env: _Env, path: str) -> list[tuple[str, RawValue]]:
        props: list[tuple[str, RawValue]] = []
        for child in element.children:
            child_env = env.extend(child)
            self._report_beyond_lite(child, path)
            if "property" in child.attrs:
                props.extend(self._property(child, child_env, path, len(props)))
            elif "typeof" not in child.attrs:
                props.extend(self._properties(child, child_env, path))
        return props

    def read_item(self, element: Element, env: _Env, path: str) -> RawItem:
        tokens = element.attrs.get("typeof", "").split()
        types = tuple(t for t in (self._resolve(token, env, path) for token in tokens) if t)
        resource = element.attrs.get("resource")
        return RawItem(
            fmt=RDFA,
            path=path,
            types=types,
            item_id=urljoin(self.base_url, resource) if resource else None,
            props=tuple(self._properties(element, env, path)),
        )

    def scan(self, element: Element, env: _Env, counter: list[int]) -> list[RawItem]:
        items: list[RawItem] = []
        for child in element.children:
            child_env = env.extend(child)
            self._report_beyond_lite(child, "rdfa")
            if "typeof" in child.attrs and "property" not in child.attrs:
                items.append(self.read_item(child, child_env, f"rdfa[{counter[0]}]"))
                counter[0] += 1
            else:
                items.extend(self.scan(child, child_env, counter))
        return items


def read_rdfa(
    root: Element, base_url: str, schema: SchemaIndex
) -> tuple[list[RawItem], list[Note]]:
    reader = _RdfaReader(schema, base_url)
    items = reader.scan(root, _Env(), [0])
    return items, reader.notes
