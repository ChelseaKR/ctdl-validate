"""A repeated @id is one entity, and the answer does not turn on array order.

Issue #33: ``by_id`` kept whichever node object declared an identifier first
and dropped the rest, so a reference to that identifier was judged against a
declaration chosen by ``@graph`` position. Both directions were reachable --
a stub out of range manufactured an ERROR, a stub in range hid one -- and the
determinism tests could not see either, because a stable wrong answer is
byte-identical to itself.

Every payload here is synthetic. See ADR-0005.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from ctdl_validate import Severity, validate_document
from ctdl_validate.findings import render_findings_text
from ctdl_validate.graph import parse_document
from ctdl_validate.schema import load_schema

RESOURCE = "https://credentialengineregistry.org/resources/"
ORG = f"{RESOURCE}ce-11111111-1111-4111-8111-111111111111"
PLACE = f"{RESOURCE}ce-22222222-2222-4222-8222-222222222222"
OTHER = f"{RESOURCE}ce-33333333-3333-4333-8333-333333333333"


def _issue_33_payload(embedded_type: str) -> dict[str, Any]:
    """The issue's document: a Place also embedded as a typed stub.

    ``embedded_type`` is the incidental class the stub carries. The issue
    reports both directions from this one shape.
    """
    return {
        "@context": "https://credreg.net/ctdl/schema/context/json",
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Organization",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:name": {"en-US": "Org X"},
                "ceterms:parentOrganization": {
                    "@id": PLACE,
                    "@type": embedded_type,
                    "ceterms:name": {"en-US": "stub, embedded with an incidental @type"},
                },
            },
            {
                "@id": PLACE,
                "@type": "ceterms:Place",
                "ceterms:name": {"en-US": "the real entity: a Place"},
            },
            {
                "@id": OTHER,
                "@type": "ceterms:Organization",
                "ceterms:ctid": "ce-33333333-3333-4333-8333-333333333333",
                "ceterms:name": {"en-US": "Org Y"},
                "ceterms:address": PLACE,
            },
        ],
    }


def _reordered(payload: dict[str, Any]) -> dict[str, Any]:
    """The same document with the real declaration walked first."""
    moved = copy.deepcopy(payload)
    entities = moved["@graph"]
    moved["@graph"] = [entities[1], entities[0], entities[2]]
    return moved


def test_the_issue_33_false_positive_is_gone() -> None:
    findings = validate_document(_issue_33_payload("ceterms:Organization"))
    assert not [f for f in findings if f.code == "RANGE_VIOLATION"], (
        "ceterms:address points at an entity the document declares a ceterms:Place"
    )


def _judgements(document: dict[str, Any]) -> list[Any]:
    """Every finding that judges the document.

    The merge disclosure is excluded on purpose. Its message names the paths
    the declarations sit at, and rearranging the ``@graph`` moves them, so it
    is the one finding whose text is *supposed* to follow array order. What
    must not follow array order is anything that says the document is wrong.
    """
    return [
        f.to_dict() for f in validate_document(document) if f.code != "ID_DECLARED_MORE_THAN_ONCE"
    ]


def test_the_verdict_does_not_depend_on_graph_array_order() -> None:
    payload = _issue_33_payload("ceterms:Organization")
    assert _judgements(payload) == _judgements(_reordered(payload))


def test_the_merge_disclosure_says_the_same_thing_from_either_order() -> None:
    """Its paths move with the document; its subject and its merge do not."""
    payload = _issue_33_payload("ceterms:Organization")
    both = []
    for document in (payload, _reordered(payload)):
        merged = [f for f in validate_document(document) if f.code == "ID_DECLARED_MORE_THAN_ONCE"]
        assert len(merged) == 1
        both.append((merged[0].entity, merged[0].severity, "ceterms:Organization, ceterms:Place"))
        assert "ceterms:Organization, ceterms:Place" in merged[0].message
    assert both[0] == both[1]


def test_the_rendered_report_is_stable_apart_from_those_paths() -> None:
    payload = _issue_33_payload("ceterms:Organization")
    without_paths = [
        render_findings_text(
            [f for f in validate_document(d) if f.code != "ID_DECLARED_MORE_THAN_ONCE"]
        )
        for d in (payload, _reordered(payload))
    ]
    assert without_paths[0] == without_paths[1]


def test_a_violation_survives_the_merge_when_no_declaration_is_in_range() -> None:
    """The merge must not become a new way to lose a real finding.

    ``ceterms:address`` ranges on ``ceterms:Place``. Neither declaration of
    the referenced entity is one, so the union is not one either, and the
    ERROR is reported from both array orders.
    """
    payload = _issue_33_payload("ceterms:Organization")
    payload["@graph"][1]["@type"] = "ceterms:CredentialOrganization"
    for document in (payload, _reordered(payload)):
        findings = validate_document(document)
        assert any(f.code == "RANGE_VIOLATION" and f.severity is Severity.ERROR for f in findings)


def test_one_declaration_in_range_settles_it_from_either_order() -> None:
    """The false-negative direction issue #33 names, read honestly.

    The issue expects a suppressed violation when the first-walked stub is in
    range and the authoritative declaration is not. Merging does not restore
    a violation there, and should not: the document asserts the resource is
    both classes, and ``ceterms:address`` admits one of them. What the fix
    owes is that the answer is the same either way round, which under
    first-wins it was not.
    """
    payload = _issue_33_payload("ceterms:Place")
    payload["@graph"][1]["@type"] = "ceterms:Organization"
    for document in (payload, _reordered(payload)):
        findings = validate_document(document)
        assert not [f for f in findings if f.code == "RANGE_VIOLATION"]
        assert any(f.code == "ID_DECLARED_MORE_THAN_ONCE" for f in findings)


def test_the_merge_is_reported_with_every_declaration_site() -> None:
    findings = validate_document(_issue_33_payload("ceterms:Organization"))
    merged = [f for f in findings if f.code == "ID_DECLARED_MORE_THAN_ONCE"]
    assert len(merged) == 1
    finding = merged[0]
    assert finding.severity is Severity.INFO
    assert finding.entity == PLACE
    assert "$.@graph[1]" in finding.message
    assert "ceterms:Organization, ceterms:Place" in finding.message


def test_a_document_without_repeats_reports_nothing_from_check_6() -> None:
    payload = _issue_33_payload("ceterms:Organization")
    del payload["@graph"][0]["ceterms:parentOrganization"]
    findings = validate_document(payload)
    assert not [f for f in findings if f.code == "ID_DECLARED_MORE_THAN_ONCE"]


def test_merging_unions_types_and_properties() -> None:
    payload = _issue_33_payload("ceterms:Organization")
    graph = parse_document(payload, load_schema())
    node = graph.by_id[PLACE]
    assert node.types == ("ceterms:Organization", "ceterms:Place")
    assert graph.repeated_ids() == {
        PLACE: ("$.@graph[0].ceterms:parentOrganization[0]", "$.@graph[1]")
    }
    assert len(node.props["ceterms:name"]) == 2, "both declarations' names survive the merge"


def test_a_single_declaration_keeps_its_own_type_order() -> None:
    """Sorting is what the merge does, not what the parser does to everyone."""
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": ["ceterms:QualityAssuranceCredential", "ceterms:Credential"],
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
            }
        ]
    }
    graph = parse_document(payload, load_schema())
    assert graph.by_id[ORG].types == (
        "ceterms:QualityAssuranceCredential",
        "ceterms:Credential",
    )


def test_repeats_inside_one_property_array_are_untouched() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Organization",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:keyword": ["nursing", "nursing"],
            }
        ]
    }
    graph = parse_document(payload, load_schema())
    assert graph.by_id[ORG].props["ceterms:keyword"] == ("nursing", "nursing")


def test_a_repeated_blank_node_is_one_node_and_is_reported() -> None:
    payload = {
        "@graph": [
            {
                "@id": ORG,
                "@type": "ceterms:Organization",
                "ceterms:ctid": "ce-11111111-1111-4111-8111-111111111111",
                "ceterms:address": {"@id": "_:place", "@type": "ceterms:Place"},
                "ceterms:offers": {"@id": "_:place", "ceterms:name": {"en-US": "again"}},
            }
        ]
    }
    findings = validate_document(payload)
    assert any(f.code == "ID_DECLARED_MORE_THAN_ONCE" and f.entity == "_:place" for f in findings)
    assert not [f for f in findings if f.code == "REF_UNRESOLVED_BNODE"]


def test_the_json_rendering_of_the_judgements_is_stable_too() -> None:
    """The JSON rendering is the machine-readable contract; hold it as well."""
    payload = _issue_33_payload("ceterms:Organization")
    first = json.dumps(_judgements(payload), sort_keys=True)
    second = json.dumps(_judgements(_reordered(payload)), sort_keys=True)
    assert first == second


def test_declaration_paths_are_listed_in_document_order_past_index_nine() -> None:
    """Ten entities, so lexical order and document order disagree.

    An earlier draft sorted these paths. Nothing in the suite could tell,
    because with fewer than ten entities walk order already is lexical order.
    It is also wrong: `$.@graph[10]` sorts before `$.@graph[9]`. This is the
    case that separates the two, so re-adding the sort fails here.
    """
    graph: list[dict[str, Any]] = [
        {
            "@id": f"{RESOURCE}ce-{index:08d}-1111-4111-8111-111111111111",
            "@type": "ceterms:Organization",
            "ceterms:ctid": f"ce-{index:08d}-1111-4111-8111-111111111111",
        }
        for index in range(10)
    ]
    graph.append({"@id": graph[9]["@id"], "ceterms:name": {"en-US": "declared again"}})
    findings = [
        f for f in validate_document({"@graph": graph}) if f.code == "ID_DECLARED_MORE_THAN_ONCE"
    ]
    assert len(findings) == 1
    assert "($.@graph[9], $.@graph[10])" in findings[0].message
