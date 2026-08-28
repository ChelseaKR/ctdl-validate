"""Check 6: one identifier, one entity.

A CTDL payload may write the same ``@id`` on more than one node object. The
idiom is ordinary: an entity is declared at the top of the ``@graph`` and then
embedded again, inline and partially, where another entity refers to it.

The parser now reads those as one entity (see :func:`ctdl_validate.graph`),
which is what a JSON-LD processor does and what the alternative -- keeping
whichever declaration was walked first -- could not do without making the
verdict a function of array order. That merge is invisible in the output
unless something says it happened, and a merge nobody was told about is a
worse failure than the one it replaced: the reader sees a finding against an
entity whose type list no single line of their document contains.

So this check exists to say it out loud. It reports no defect. Repeating an
``@id`` is not an error, and this check never returns one.
"""

from __future__ import annotations

from ..findings import Finding, Severity
from ..rules import REPEATED_ID_POLICY
from ..session import Session


def check(session: Session) -> list[Finding]:
    findings: list[Finding] = []
    for node_id, paths in sorted(session.graph.repeated_ids().items()):
        node = session.graph.by_id[node_id]
        types = ", ".join(node.types) if node.types else "no @type"
        # Walk order, deliberately not sorted. These are locations in the
        # reader's file, and walk order is the order they appear in it.
        # Sorting them lexically was tried and removed: it cannot be right
        # (`$.@graph[10]` sorts before `$.@graph[9]`, so it reverses document
        # order from ten entities up) and no test could tell the difference,
        # which is two reasons not to keep it. The merged @type tuple *is*
        # sorted, for a reason that does not apply here: type names are a set
        # the document states twice, while these paths are positions.
        findings.append(
            Finding(
                code="ID_DECLARED_MORE_THAN_ONCE",
                severity=Severity.INFO,
                entity=node_id,
                prop="@id",
                value=node_id,
                message=(
                    f"{len(paths)} node objects declare this @id "
                    f"({', '.join(paths)}). They were read as one entity, typed "
                    f"[{types}], and every check below judged that merged entity. "
                    "If they were meant to be different resources, they need "
                    "different identifiers."
                ),
                rule=REPEATED_ID_POLICY,
            )
        )
    return findings
