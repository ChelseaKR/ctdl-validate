"""The three markup readers: what they read, and what they refuse to read."""

from __future__ import annotations

from ctdl_validate.extract.dom import parse_html
from ctdl_validate.extract.items import declared_types, walk_items
from ctdl_validate.extract.jsonld import read_block, read_context
from ctdl_validate.extract.markup import read_page
from ctdl_validate.extract.microdata import read_microdata
from ctdl_validate.extract.rdfa import read_rdfa
from ctdl_validate.extract.terms import is_absolute_iri, normalize_term, vocabulary_of
from ctdl_validate.schema import load_schema

from .conftest import load_page

SOURCE = "https://example.edu/page"


def codes(notes: object) -> set[str]:
    return {note.code for note in notes}  # type: ignore[attr-defined]


# -- the tree builder -------------------------------------------------------


def test_text_is_document_order_and_excludes_script() -> None:
    root = parse_html("<div>My name is <span>Elizabeth</span>.<script>var x = 1;</script></div>")
    assert root.children[0].text() == "My name is Elizabeth."


def test_implied_end_tags_do_not_swallow_following_items() -> None:
    root = parse_html("<ul><li itemscope itemtype='https://schema.org/Organization'><li>next</ul>")
    items = [element for element in root.walk() if element.tag == "li"]
    assert len(items) == 2, "an unclosed <li> must not contain the next one"


def test_stray_end_tag_is_ignored_rather_than_unwinding_the_tree() -> None:
    root = parse_html("<div><p>one</p></section><p>two</p></div>")
    div = root.children[0]
    assert [child.tag for child in div.children] == ["p", "p"]


# -- terms ------------------------------------------------------------------


def test_schema_org_http_and_https_normalize_to_one_term() -> None:
    schema = load_schema()
    assert normalize_term("http://schema.org/name", schema) == "schema:name"
    assert normalize_term("https://schema.org/name", schema) == "schema:name"
    assert normalize_term("ceterms:name", schema) == "ceterms:name"


def test_vocabulary_of_needs_a_local_name() -> None:
    assert vocabulary_of("https://schema.org/Course") == "https://schema.org/"
    assert vocabulary_of("http://purl.org/ctdl/terms/Course") == "http://purl.org/ctdl/terms/"
    assert vocabulary_of("https://schema.org") is None
    assert vocabulary_of("Course") is None


def test_absolute_iri_recognition_is_about_the_scheme() -> None:
    assert is_absolute_iri("https://example.edu/x")
    assert not is_absolute_iri("Example Community College")
    assert not is_absolute_iri("/about")


# -- JSON-LD ----------------------------------------------------------------


def test_schema_org_context_resolves_bare_terms() -> None:
    context = read_context("https://schema.org")
    assert context.resolved
    assert context.expand("name") == "https://schema.org/name"


def test_unknown_context_leaves_bare_terms_unread() -> None:
    context = read_context("https://example.org/private.jsonld")
    assert not context.resolved
    assert context.expand("name") is None
    assert context.expand("schema:name") == "schema:name"


def test_inline_context_supplies_vocab_prefixes_and_language() -> None:
    context = read_context(
        [{"@vocab": "https://schema.org/", "sdo": "https://schema.org/", "@language": "es"}]
    )
    assert context.expand("name") == "https://schema.org/name"
    assert context.expand("sdo:name") == "https://schema.org/name"
    assert context.language == "es"


def test_jsonld_reads_graph_nesting_and_language_objects() -> None:
    schema = load_schema()
    source = """
    {"@context": "https://schema.org", "@graph": [
      {"@type": "Course", "name": {"@value": "Soldadura", "@language": "es"},
       "provider": {"@type": "Organization", "name": "Example"},
       "sameAs": {"@id": "https://example.edu/x"}, "free": true, "seats": 12}
    ]}
    """
    items, notes = read_block(source, "json-ld[0]", schema)
    assert notes == []
    everything = list(walk_items(items))
    assert declared_types(items) == ("schema:Course", "schema:Organization")
    values = dict(everything[0].props)
    assert values["schema:name"].text == "Soldadura"
    assert values["schema:name"].language == "es"
    assert values["schema:sameAs"].iri == "https://example.edu/x"
    assert values["schema:free"].text == "true"
    assert values["schema:seats"].text == "12"
    assert values["schema:provider"].item is everything[1]


def test_malformed_block_is_reported_not_repaired() -> None:
    items, notes = read_block('{"@type": "Course", "name": }', "json-ld[0]", load_schema())
    assert items == []
    assert codes(notes) == {"JSONLD_PARSE_ERROR"}


# -- microdata --------------------------------------------------------------


def test_microdata_value_rules_follow_the_standard() -> None:
    schema = load_schema()
    root = parse_html(load_page("organization_microdata.html"))
    items, notes = read_microdata(root, SOURCE, schema)

    assert len(items) == 2, "the untyped item is still an item"
    values = dict(items[0].props)
    assert values["schema:name"].text == "Example Community College"
    assert values["schema:foundingDate"].text == "1965-09-01", "meta uses @content"
    assert values["schema:subjectWebpage"].iri == "https://example.edu/about", "href resolved"
    assert values["schema:email"].text == "admissions@example.edu", "white space collapsed"
    assert "schema:legalName" not in values, "an empty value asserts nothing"
    assert values["schema:address"].item is not None

    nested = dict(values["schema:address"].item.props)
    assert nested["schema:addressLocality"].language == "es", "nearest lang attribute wins"
    assert codes(notes) == {"EMPTY_VALUE", "MICRODATA_NAME_UNRESOLVED"}


def test_microdata_reads_every_element_specific_value_rule() -> None:
    page = """
    <div itemscope itemtype="https://schema.org/Organization">
      <img itemprop="image" src="/logo.png">
      <link itemprop="sameAs" href="https://example.org/wiki">
      <object itemprop="video" data="/tour.mp4"></object>
      <data itemprop="numberOfEmployees" value="120">a hundred and twenty</data>
      <meter itemprop="rating" value="4.5">four and a half</meter>
      <time itemprop="foundingDate" datetime="1965-09-01">September 1965</time>
      <time itemprop="dissolutionDate">2020</time>
      <a itemprop="url" href="">empty</a>
    </div>
    """
    items, notes = read_microdata(parse_html(page), SOURCE, load_schema())
    values = dict(items[0].props)
    assert values["schema:image"].iri == "https://example.edu/logo.png"
    assert values["schema:sameAs"].iri == "https://example.org/wiki"
    assert values["schema:video"].iri == "https://example.edu/tour.mp4"
    assert values["schema:numberOfEmployees"].text == "120", "the value attribute, not the text"
    assert values["schema:rating"].text == "4.5"
    assert values["schema:foundingDate"].text == "1965-09-01", "the datetime attribute"
    assert values["schema:dissolutionDate"].text == "2020", "no datetime: the text"
    assert "schema:url" not in values, "an empty href is not a reference"
    assert "EMPTY_VALUE" in codes(notes)


def test_microdata_itemref_is_reported_because_it_is_not_followed() -> None:
    root = parse_html(load_page("mixed_problems.html"))
    _, notes = read_microdata(root, SOURCE, load_schema())
    assert "MICRODATA_ITEMREF" in codes(notes)


# -- RDFa -------------------------------------------------------------------


def test_rdfa_lite_reads_vocab_prefix_resource_and_language() -> None:
    root = parse_html(load_page("program_rdfa.html"))
    items, notes = read_rdfa(root, SOURCE, load_schema())

    assert [item.item_id for item in items[:2]] == [
        "https://example.edu/page#college",
        "https://example.edu/page#second",
    ]
    first = dict(items[0].props)
    assert first["schema:name"].text == "Example Community College"
    assert first["schema:description"].language == "fr"
    assert first["schema:subjectWebpage"].iri == "https://example.edu/about"
    assert dict(items[1].props)["schema:name"].text == "Example Extension Campus"
    assert "RDFA_BEYOND_LITE" in codes(notes)


def test_rdfa_bare_term_without_vocab_is_left_unread() -> None:
    root = parse_html('<div typeof="Organization"><span property="name">X</span></div>')
    items, notes = read_rdfa(root, SOURCE, load_schema())
    assert [(item.types, item.props) for item in items] == [((), ())]
    assert codes(notes) == {"RDFA_TERM_UNRESOLVED"}


# -- the page ---------------------------------------------------------------


def test_a_page_with_no_structured_data_says_so() -> None:
    items, blocks, notes = read_page(load_page("no_markup.html"), SOURCE, load_schema())
    assert (items, blocks) == ([], [])
    assert codes(notes) == {"NO_STRUCTURED_DATA"}


def test_every_format_on_one_page_is_inventoried() -> None:
    items, blocks, _ = read_page(load_page("mixed_problems.html"), SOURCE, load_schema())
    assert [block.fmt for block in blocks] == ["json-ld", "json-ld", "json-ld", "microdata"]
    assert blocks[2].items == 2, "the nested course counts too"
    assert items
