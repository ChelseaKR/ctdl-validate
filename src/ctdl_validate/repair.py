"""``ctdl-validate repair --draft``: the re-spellings, written out as a patch.

``--suggest`` names the correction beside a finding. This applies the ones the
payload itself determines to a **copy**, re-validates the copy with the same
deterministic engine, and reports what moved. It is the other half of #64.

Three properties are the whole of it, and each is enforced rather than
promised:

**The input is never written.** ``repair`` reads a document and writes a
different path. It refuses an ``--out`` that is the input, or that is any
``--resolve`` path, before it opens anything.

**Nothing is invented.** Every operation's value comes from
:mod:`ctdl_validate.suggest`, which reads a re-spelling out of the run's own
input and refuses where more than one candidate exists. No CTID is minted, no
language is guessed, no literal becomes an IRI. This module adds one refusal
of its own -- see :func:`locate` -- and no candidates.

**The report is what the validator found, not what the patcher intended.** The
counts come from re-running the checks over the written copy and comparing the
two finding sets with :mod:`ctdl_validate.compare`, the same identity ``diff``
uses. A patch that resolves nothing says so, and a patch that introduces a
finding says that too, with the finding.

``replace`` only, which is the issue's own scope and is also the honest limit:
these four codes are re-spellings of a value that is already written, so there
is nothing to add and nothing to remove. An RFC 6902 patch of ``replace``
operations cannot change a document's shape.

**Why a finding can be skipped, and why each skip is data rather than an
omission.** A finding reaches an operation only when the run derived exactly
one candidate for it *and* this module can point at exactly one place in the
source where the reported value is written. The second condition is not
redundant. A finding names its entity by ``@id`` where it has one, and an
``@id`` may be declared by more than one object in a document -- that is a
defect this tool reports (``ID_DECLARED_MORE_THAN_ONCE``) rather than one it
refuses to read -- so "the value this finding is about" can be two positions.
Patching one of them would be a guess about which the finding meant, and
patching both would be a second guess that they are the same mistake. Neither
is a re-spelling the payload determines, so the finding is skipped and the
reason is printed with it.

Exit codes: 0 the draft was written; 2 the input could not be read, or an
output path was refused. **Not 1 for "the draft still has ERRORs"**: this verb
produces a draft for a person to read, and the exit code that gates a
publication is the validator's, run over whatever they decide to keep.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .compare import finding_key
from .findings import SEVERITY_ORDER, Finding, counts
from .graph import DocumentError
from .schema import SchemaIndex
from .session import Session
from .validator import build_session, validate

#: Why a finding this run could otherwise have corrected was left alone. Each
#: value is printed beside the finding, so a skipped correction is a sentence
#: rather than a silence.
NO_CANDIDATE = "no correction this payload determines"
SEVERAL_CANDIDATES = "more than one candidate, so which was meant is a guess"
NOT_IN_THE_SOURCE = (
    "the reported value is not written at that position in the source, so there is "
    "nothing to replace"
)
SEVERAL_POSITIONS = (
    "the value is written at {count} positions under this identifier, and which one "
    "the finding names is not decidable here"
)


def _escape(token: str) -> str:
    """One JSON Pointer reference token, RFC 6901 section 3."""
    return token.replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True)
class Located:
    """One place in the source document where a finding's value is written."""

    pointer: str
    #: The label the graph would give the object this value hangs off: its
    #: ``@id`` where it has one, otherwise its document path. Kept so the match
    #: can be made on the same identity the finding carries.
    label: str
    prop: str
    value: Any


def _walk_entity(
    obj: dict[str, Any], path: str, pointer: str, schema: SchemaIndex
) -> list[Located]:
    """Every property value under one entity object, with its JSON Pointer.

    Mirrors :meth:`ctdl_validate.graph._Builder.walk` step for step -- the
    ``@``-prefixed keys it skips, the ``compact_iri`` it applies to every other
    key, the way a bare value and a one-element list are the same thing to it,
    and the four shapes a dict value can take. It has to: the label and
    property this produces are compared against a finding's, and a walk that
    disagreed with the one that produced the finding would silently locate
    nothing and every correction would be skipped as "not in the source".
    """
    node_id = obj.get("@id") if isinstance(obj.get("@id"), str) else None
    label = node_id if node_id is not None else path
    located: list[Located] = []
    for key, raw in obj.items():
        if key.startswith("@"):
            continue
        prop = schema.compact_iri(key)
        prop_def = schema.properties.get(prop)
        listed = isinstance(raw, list)
        raw_values = raw if listed else [raw]
        for index, item in enumerate(raw_values):
            here = f"{pointer}/{_escape(key)}" + (f"/{index}" if listed else "")
            if isinstance(item, dict):
                if set(item.keys()) == {"@id"} and isinstance(item["@id"], str):
                    located.append(Located(f"{here}/@id", label, prop, item["@id"]))
                elif "@value" in item:
                    located.append(Located(f"{here}/@value", label, prop, item["@value"]))
                elif prop_def is not None and prop_def.language_map:
                    located.append(Located(here, label, prop, item))
                else:
                    located.extend(_walk_entity(item, f"{path}.{prop}[{index}]", here, schema))
            else:
                located.append(Located(here, label, prop, item))
    return located


def positions(document: Any, schema: SchemaIndex) -> list[Located]:
    """Every value in the document a finding could be about, with its pointer.

    The three document shapes are the three
    :func:`ctdl_validate.graph.parse_document` accepts, and the paths are built
    the same way, including the rule that a single entity under no ``@graph``
    is ``$`` rather than ``$[0]``.
    """
    if isinstance(document, dict) and "@graph" in document:
        entities = document["@graph"]
        prefix, base = "$.@graph", "/@graph"
    elif isinstance(document, dict):
        entities, prefix, base = [document], "$", ""
    elif isinstance(document, list):
        entities, prefix, base = document, "$", ""
    else:  # pragma: no cover - parse_document refuses this before we are called
        return []
    if not isinstance(entities, list):  # pragma: no cover - likewise
        return []

    located: list[Located] = []
    indexed = len(entities) > 1 or prefix.endswith("@graph")
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):  # pragma: no cover - likewise
            continue
        path = f"{prefix}[{index}]" if indexed else prefix
        pointer = f"{base}/{index}" if indexed else base
        located.extend(_walk_entity(entity, path, pointer, schema))

    # The `@graph` envelope's own `@id` is not a node and carries no property,
    # so the walk above never reaches it -- and it is exactly where
    # `CTID_URI_MISMATCH` lands on a graph URI. `graph.py` keeps it on the
    # Graph for the same reason; a finding names it with prop "@id".
    if isinstance(document, dict) and "@graph" in document:
        envelope = document.get("@id")
        if isinstance(envelope, str):
            located.append(Located("/@id", envelope, "@id", envelope))
    return located


def locate(finding: Finding, located: Sequence[Located]) -> list[str]:
    """Every pointer at which this finding's value is written, under its entity.

    Matched on the finding's own identity fields -- entity, property, value --
    so a document that writes the same string twice under different properties
    cannot be patched at the wrong one. The comparison against ``value`` is
    against the *raw* value rather than its rendering, and only a string can
    match: every code this module can act on reports a string, and comparing a
    rendered non-string against its source would be matching a `repr` to an
    object.
    """
    return [
        position.pointer
        for position in located
        if position.label == finding.entity
        and position.prop == finding.prop
        and isinstance(position.value, str)
        and position.value == finding.value
    ]


@dataclass(frozen=True)
class Operation:
    """One RFC 6902 ``replace``, and the finding it answers."""

    pointer: str
    value: str
    finding: Finding

    def as_patch(self) -> dict[str, str]:
        return {"op": "replace", "path": self.pointer, "value": self.value}


@dataclass(frozen=True)
class Skipped:
    """A finding this run did not act on, and why."""

    finding: Finding
    reason: str


@dataclass(frozen=True)
class Draft:
    """What a repair run produced: the operations, the skips, and the counts."""

    operations: tuple[Operation, ...]
    skipped: tuple[Skipped, ...]
    before: tuple[Finding, ...]
    after: tuple[Finding, ...]

    @property
    def resolved(self) -> tuple[Finding, ...]:
        """Findings the draft no longer reports. Not "fixed": see the note below."""
        after_keys = {finding_key(f) for f in self.after}
        return tuple(f for f in self.before if finding_key(f) not in after_keys)

    @property
    def introduced(self) -> tuple[Finding, ...]:
        before_keys = {finding_key(f) for f in self.before}
        return tuple(f for f in self.after if finding_key(f) not in before_keys)

    @property
    def untouched(self) -> tuple[Finding, ...]:
        after_keys = {finding_key(f) for f in self.after}
        return tuple(f for f in self.before if finding_key(f) in after_keys)

    def as_dict(self) -> dict[str, Any]:
        return {
            "patch": [operation.as_patch() for operation in self.operations],
            "skipped": [
                {"finding": skip.finding.to_dict(), "reason": skip.reason} for skip in self.skipped
            ],
            "resolved": [f.to_dict() for f in self.resolved],
            "introduced": [f.to_dict() for f in self.introduced],
            "counts": {
                "operations": len(self.operations),
                "skipped": len(self.skipped),
                "resolved": len(self.resolved),
                "untouched": len(self.untouched),
                "introduced": len(self.introduced),
            },
            "summary": {"before": counts(list(self.before)), "after": counts(list(self.after))},
            "tool": {"name": "ctdl-validate", "version": __version__},
        }


def operations_for(
    session: Session, document: Any, findings: Sequence[Finding]
) -> tuple[tuple[Operation, ...], tuple[Skipped, ...]]:
    """One ``replace`` per finding whose correction is determined and locatable."""
    located = positions(document, session.schema)
    operations: list[Operation] = []
    skipped: list[Skipped] = []
    for finding in findings:
        if not finding.suggestions:
            skipped.append(Skipped(finding, NO_CANDIDATE))
            continue
        if len(finding.suggestions) > 1:
            # `suggest._sole` refuses to offer two today, so this is a guard
            # against a future suggester rather than a branch the shipped
            # suggesters reach. It is here because the alternative -- taking
            # `suggestions[0]` -- would silently pick one.
            skipped.append(Skipped(finding, SEVERAL_CANDIDATES))
            continue
        pointers = locate(finding, located)
        if not pointers:
            skipped.append(Skipped(finding, NOT_IN_THE_SOURCE))
            continue
        if len(pointers) > 1:
            skipped.append(Skipped(finding, SEVERAL_POSITIONS.format(count=len(pointers))))
            continue
        operations.append(Operation(pointers[0], finding.suggestions[0].value, finding))
    return tuple(operations), tuple(skipped)


def apply_patch(document: Any, operations: Sequence[Operation]) -> Any:
    """A deep copy of the document with every operation applied.

    The copy is what makes "the original is never written" true of this module
    and not only of the CLI around it.
    """
    patched = copy.deepcopy(document)
    for operation in operations:
        tokens = [
            token.replace("~1", "/").replace("~0", "~")
            for token in operation.pointer.split("/")[1:]
        ]
        target: Any = patched
        for token in tokens[:-1]:
            target = target[int(token)] if isinstance(target, list) else target[token]
        last = tokens[-1]
        if isinstance(target, list):
            target[int(last)] = operation.value
        else:
            target[last] = operation.value
    return patched


def draft(document: Any, resolve: list[Path] | None = None) -> tuple[Draft, Any]:
    """Build the draft and the patched document, without writing anything."""
    session = build_session(document, resolve)
    before = validate(session, suggest=True)
    operations, skipped = operations_for(session, document, before)
    patched = apply_patch(document, operations)
    after = validate(build_session(patched, resolve))
    return (
        Draft(operations, skipped, tuple(before), tuple(after)),
        patched,
    )


def _line(finding: Finding) -> str:
    return (
        f"  {finding.severity.value:12} {finding.code}  entity={finding.entity}\n"
        f"      {finding.prop} = {finding.value}"
    )


def render_text(result: Draft, out: Path) -> str:
    lines = [f"draft written to {out}", ""]
    lines.append(f"applied ({len(result.operations)})")
    for operation in result.operations:
        lines.append(_line(operation.finding))
        lines.append(f"      -> {operation.value}   at {operation.pointer}")
    if not result.operations:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"not applied ({len(result.skipped)})")
    for skip in result.skipped:
        lines.append(_line(skip.finding))
        lines.append(f"      left alone: {skip.reason}")
    if not result.skipped:
        lines.append("  (none)")
    lines.append("")
    for name, findings in (
        ("resolved", result.resolved),
        ("introduced", result.introduced),
    ):
        lines.append(f"{name} ({len(findings)})")
        lines += [_line(finding) for finding in findings] or ["  (none)"]
        lines.append("")
    lines.append(f"untouched: {len(result.untouched)}")
    for name, findings in (("before", result.before), ("after", result.after)):
        counted = ", ".join(f"{counts(list(findings))[s.value]} {s.value}" for s in SEVERITY_ORDER)
        lines.append(f"{name}: {len(findings)} finding(s): {counted}")
    lines.append(
        "A resolved finding is one the draft no longer reports. It is not evidence that "
        "the entity it was about is now correct: only that this document no longer says "
        "what the finding said about it."
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctdl-validate repair",
        description=(
            "Write a copy of a CTDL document with the re-spellings this payload "
            "determines applied, re-validate the copy, and report what moved. The "
            "input is never written. Offline, no model calls."
        ),
    )
    parser.add_argument("file", help="path to a CTDL JSON-LD document")
    parser.add_argument(
        "--draft",
        action="store_true",
        required=True,
        help=(
            "required, and the only mode. The word is the contract: what this writes "
            "is a draft for a person to read, not a repaired document. Requiring it "
            "means no future mode can become the default by omission"
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help="where to write the patched copy. Refused if it is the input or a --resolve path",
    )
    parser.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "a further CTDL document, or a directory of them, this run can resolve "
            "references against. Repeatable, read-only, never written and never patched"
        ),
    )
    parser.add_argument(
        "--patch-out",
        metavar="PATH",
        help="also write the RFC 6902 patch itself, as a JSON array of replace operations",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="report format (default: text)"
    )
    return parser


def _refuse_output(out: Path, source: Path, resolve: list[Path]) -> str | None:
    """Why this ``--out`` may not be written, or ``None``.

    Compared by resolved path rather than by string, so ``./x.json`` and
    ``x.json`` are one file here as they are on disk. A relative path that does
    not exist yet still resolves, which is the ordinary case for an output.

    A ``--resolve`` argument may be a **directory**, which
    :func:`ctdl_validate.session.expand` opens into the ``.json`` files one
    level inside it. Comparing the target only with the arguments therefore
    missed every one of those members: ``--resolve supplied/ --out
    supplied/other.json`` wrote the draft over a supplied document, silently
    and with exit 0. So a directory argument protects everything under it,
    which is the claim the README already makes ("an ``--out`` that is ... any
    ``--resolve`` path, is refused before anything is opened").
    """
    target = out.resolve()
    if target == source.resolve():
        return (
            "--out is the input. This verb writes a draft beside the document rather "
            "than over it: the original is the thing a reader checks the draft against."
        )
    for path in resolve:
        supplied = path.resolve()
        if target == supplied:
            return (
                f"--out is {path}, which was supplied with --resolve. A supplied document "
                "is never validated and never patched by this run."
            )
        if supplied.is_dir() and target.is_relative_to(supplied):
            return (
                f"--out is inside {path}, a directory supplied with --resolve, so it is "
                "one of the supplied documents. A supplied document is never validated "
                "and never patched by this run."
            )
    return None


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(list(argv))
    source = Path(args.file)
    out = Path(args.out)
    resolve = [Path(p) for p in args.resolve]

    refusal = _refuse_output(out, source, resolve)
    if refusal is not None:
        print(f"ctdl-validate repair: {refusal}", file=sys.stderr)
        return 2

    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ctdl-validate repair: cannot read {source}: {exc}", file=sys.stderr)
        return 2
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ctdl-validate repair: {source} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    try:
        result, patched = draft(document, resolve or None)
    except DocumentError as exc:
        print(f"ctdl-validate repair: {source}: {exc}", file=sys.stderr)
        return 2

    try:
        with out.open("w", encoding="utf-8") as handle:
            json.dump(patched, handle, indent=2, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
        if args.patch_out:
            with Path(args.patch_out).open("w", encoding="utf-8") as handle:
                json.dump(
                    [operation.as_patch() for operation in result.operations],
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
    except OSError as exc:
        print(f"ctdl-validate repair: cannot write: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_text(result, out))
    return 0


__all__ = [
    "Draft",
    "Located",
    "Operation",
    "Skipped",
    "apply_patch",
    "draft",
    "locate",
    "main",
    "operations_for",
    "positions",
]
