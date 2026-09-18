"""The playground's rule list is derived, and this file is what keeps it derived.

`web/index.html` shows every rule this build can report. The obvious way to
build that page is to write the rules down in the HTML, and the obvious way is
wrong: a list of rules copied next to a tool is a list that goes stale in
exactly the direction nobody notices, because a rule that quietly stops firing
still has a paragraph describing it.

So the page states nothing about any rule. It ships one *document* per finding
code, runs the validator over each one in the browser, and prints what came
back: the severity, the wording and the citation are whatever this build
produced. Nothing on that page is a claim the page makes about the validator.

That leaves two things a test has to hold.

1. **The corpus has to stay complete and live.** Same four directions as
   ``tests/test_every_rule_fires.py``, applied to the page's documents: a code
   the source can emit with no document, a document filed under a code the
   source no longer emits, and -- the one that matters -- a document that no
   longer produces the code it is filed under. The third is why these are
   payloads and not strings: an entry can only stay green while the rule it
   names still does something.

2. **The page's own derivation has to work.** The catalog is built by Python
   embedded in the page, which enumerates finding codes out of the check
   modules by AST. If that scan silently under-reports, the page silently omits
   rules, which is the failure this repository spends its time hunting. So the
   test does not re-implement that code and compare notes with it. It executes
   the page's copy, and asserts against what the page would actually show.

The page's network posture is gated here too, because this is the first Python
test to read `web/index.html` and the posture is a property of that file: the
Content-Security-Policy is the control that keeps a payload in the browser, and
a control nothing checks is a comment.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document
from tests.test_every_rule_fires import rule_codes_in_source

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "index.html"

#: Where GitHub Pages serves this page, and the card published beside it.
#: Written out rather than parsed back out of the page, for the same reason the
#: allowed origins below are: an expectation read out of the thing under test
#: moves with the mistake and stays green.
PUBLISHED_AT = "https://chelseakr.github.io/ctdl-validate/"
CARD_FILENAME = "social-card.png"

#: The two network origins the validator is allowed to name, and the reason
#: each is there. Written out rather than parsed back out of the page, which is the
#: whole point: an expectation read out of the thing under test moves with the
#: mistake and stays green.
ALLOWED_ORIGINS = {
    "'self'": "the wheel, built from this commit by the Pages workflow",
    "https://cdn.jsdelivr.net": "the Pyodide runtime",
}

#: The Google origins the page's analytics may reach, and nothing else Google
#: serves (docs/adr/0007-playground-analytics.md). They belong to the page, not
#: to the validator, and are listed apart so that neither set can grow by
#: hiding in the other. www.google.com and doubleclick.net are absent on
#: purpose: with Google signals off, GA4 does not need them.
ANALYTICS_ORIGINS = {
    "https://www.googletagmanager.com": "the gtag.js loader",
    "https://*.google-analytics.com": "GA4's measurement endpoint",
    "https://*.analytics.google.com": "GA4's other measurement endpoint",
}

#: Ways a page sends something somewhere that a Content-Security-Policy
#: connect-src does not obviously cover at a glance, and that no part of this
#: page has any business using.
FORBIDDEN_APIS = (
    "sendBeacon",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "RTCPeerConnection",
    "navigator.geolocation",
    "<form",
)


def page_source() -> str:
    return PAGE.read_text(encoding="utf-8")


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Width and height out of a PNG's IHDR, so no image library is needed to read them.

    The signature is eight bytes, then a length and the chunk type ``IHDR``,
    then width and height as big-endian 32-bit integers.
    """
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    assert data[12:16] == b"IHDR", "the first chunk of a PNG is IHDR"
    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def script_block(element_id: str) -> str:
    """The raw text of one non-executing ``<script>`` block in the page.

    Both blocks this reaches for carry a type the browser does not execute:
    the corpus is ``application/json`` and the Python is ``text/plain``. They
    are data the page reads with ``textContent``, which is also why this can
    read the same bytes without an HTML parser.
    """
    match = re.search(
        rf'<script[^>]*\bid="{re.escape(element_id)}"[^>]*>(.*?)</script>',
        page_source(),
        re.DOTALL,
    )
    assert match is not None, (
        f"the page has no <script id={element_id!r}> block. The playground's rule "
        "catalog is built out of it, so it cannot have moved without this failing."
    )
    return match.group(1)


def corpus() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = json.loads(script_block("rule-corpus"))
    return loaded


def page_python() -> dict[str, Any]:
    """Run the page's own Python, and hand back what it defined.

    The rule this suppresses asks whether the executed content can come from
    outside the program. It cannot: the argument is a fixed block of this
    repository's own source, read from a path this file computes, in a test
    process, with no input reaching it. Executing it is the entire purpose --
    the alternative is a second copy of the page's derivation logic here,
    compared against the first, which is exactly the drift this file exists to
    prevent. Suppressed on this line rather than repo-wide, so the rule still
    fires on the next exec that is not this one.
    """
    namespace: dict[str, Any] = {}
    source = compile(script_block("py-bootstrap"), "web/index.html#py-bootstrap", "exec")
    # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    exec(source, namespace)
    return namespace


# -- the corpus stays complete and live ---------------------------------------


def test_every_code_the_source_emits_has_a_document_on_the_page() -> None:
    """A rule the playground cannot demonstrate is a rule its visitors cannot find."""
    missing = sorted(rule_codes_in_source() - set(corpus()))
    assert missing == [], (
        "the check modules emit these and web/index.html ships no document that reaches "
        f"them, so the playground's rule list would be missing them: {missing}"
    )


def test_no_document_on_the_page_outlives_the_rule_it_was_written_for() -> None:
    stale = sorted(set(corpus()) - rule_codes_in_source())
    assert stale == [], (
        "web/index.html files documents under these codes and no check module emits them "
        f"any more: {stale}. Remove the entry, or the rule was deleted by accident."
    )


@pytest.mark.parametrize("code", sorted(corpus()))
def test_the_page_document_still_produces_the_code_it_is_filed_under(
    code: str, tmp_path: Path
) -> None:
    """The behavioral half: each document is validated, not just named."""
    entry = corpus()[code]
    resolve = None
    if entry.get("resolve") is not None:
        neighbor = tmp_path / "neighbor.json"
        neighbor.write_text(json.dumps(entry["resolve"]), encoding="utf-8")
        resolve = [neighbor]
    findings = validate_document(entry["document"], resolve)
    hits = [f for f in findings if f.code == code]
    assert hits, (
        f"the playground's document for {code} no longer produces it, so that entry in the "
        f"rule list would say the rule has no example. What it did produce: "
        f"{sorted({f.code for f in findings})}"
    )
    for finding in hits:
        assert finding.rule.citation.strip(), f"{code} would be listed on the page citing nothing"
        assert finding.rule.url.strip(), f"{code} would be listed on the page with no source URL"
        assert finding.rule.retrieved.strip(), f"{code} would be listed with no retrieval date"


# -- the page's own derivation works ------------------------------------------


def test_the_pages_code_scan_finds_exactly_the_codes_the_source_emits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The page enumerates rules by AST, and this runs that scan, not a copy of it."""
    monkeypatch.chdir(tmp_path)
    codes, unreadable = page_python()["codes_in_source"]()
    assert unreadable == 0, (
        f"{unreadable} finding code in the check modules is built at run time rather than "
        "written as a string literal, so the page cannot list it"
    )
    assert codes == rule_codes_in_source(), (
        "the scan embedded in web/index.html and the one in test_every_rule_fires.py "
        f"disagree: only on the page {sorted(codes - rule_codes_in_source())}, only in the test "
        f"{sorted(rule_codes_in_source() - codes)}"
    )


def test_the_page_would_render_a_derived_row_for_every_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End to end: the rows the visitor sees, produced by the code that produces them."""
    monkeypatch.chdir(tmp_path)
    derived = json.loads(page_python()["catalog"](json.dumps(corpus())))
    rows = derived["rows"]
    assert derived["unreadable"] == 0
    assert {row["code"] for row in rows} == rule_codes_in_source()
    without_example = sorted(row["code"] for row in rows if not row["example"])
    assert without_example == [], (
        "the playground would show these rules with no derived example, which is honest "
        f"and is still a gap a visitor would meet: {without_example}"
    )
    severities = {s.value for s in Severity}
    for row in rows:
        assert row["severity"] in severities, f"{row['code']} carries {row['severity']!r}"
        assert row["message"].strip(), f"{row['code']} would render an empty message"
        assert row["rule"]["citation"].strip(), f"{row['code']} would render citing nothing"


def test_the_static_accessibility_fixture_names_rules_the_page_can_load() -> None:
    """?a11y-static renders example buttons; a dead one is a broken control in the gate."""
    fixture = re.search(r"const A11Y_SAMPLE = \[(.*?)\n      \];", page_source(), re.DOTALL)
    assert fixture is not None, "the static accessibility fixture has moved"
    codes = set(re.findall(r'code:\s*"([A-Z0-9_]+)"', fixture.group(1)))
    assert codes, "the static accessibility fixture names no finding codes"
    unloadable = sorted(codes - set(corpus()))
    assert unloadable == [], (
        "the static accessibility fixture renders a catalog row with a 'load the payload' "
        f"button for these, and the page ships no payload for them: {unloadable}"
    )


# -- the page keeps the payload in the browser --------------------------------


def content_security_policy() -> dict[str, list[str]]:
    match = re.search(
        r'http-equiv="Content-Security-Policy"\s*\n?\s*content="([^"]*)"', page_source()
    )
    assert match is not None, "web/index.html declares no Content-Security-Policy"
    directives: dict[str, list[str]] = {}
    for directive in match.group(1).split(";"):
        parts = directive.split()
        if parts:
            directives[parts[0]] = parts[1:]
    return directives


def test_the_policy_names_its_origins_and_no_others() -> None:
    """The playground's promise is that no payload leaves the tab. This is the control.

    The validator's two origins, plus the analytics origins and nothing more.
    The analytics script is guarded and reads nothing from the payload, but a
    script origin is still a party who can change what runs on this page, so
    each one is named here and a third cannot arrive unnoticed.
    """
    policy = content_security_policy()
    assert policy["default-src"] == ["'none'"], (
        "default-src is what closes every fetch directive this policy does not name; "
        f"it reads {policy['default-src']}"
    )
    assert set(policy["connect-src"]) == set(ALLOWED_ORIGINS) | set(ANALYTICS_ORIGINS), (
        f"connect-src is {policy['connect-src']}. Exactly these origins belong there: "
        + ", ".join(
            f"{origin} ({why})"
            for origin, why in sorted({**ALLOWED_ORIGINS, **ANALYTICS_ORIGINS}.items())
        )
    )
    hosts = [token for token in policy["script-src"] if "://" in token]
    assert hosts == ["https://cdn.jsdelivr.net", "https://www.googletagmanager.com"], (
        f"script-src names {hosts}. The Pyodide runtime and the gtag.js loader are the "
        "only scripts from elsewhere; another script origin is another party who can "
        "change what runs beside a payload the visitor has not published."
    )
    img_hosts = {token for token in policy["img-src"] if "://" in token}
    assert img_hosts <= set(ANALYTICS_ORIGINS), (
        f"img-src names {sorted(img_hosts)}; only the analytics origins may appear there"
    )
    assert "'unsafe-eval'" not in policy["script-src"], (
        "'unsafe-eval' is not needed: the worker is built from bytes the page fetched and "
        "hashed itself, not from a string handed to eval"
    )


def test_the_page_uses_no_api_that_would_send_a_payload_anywhere() -> None:
    html = page_source()
    found = sorted(api for api in FORBIDDEN_APIS if api in html)
    assert found == [], (
        f"web/index.html mentions {found}. Nothing on this page has a reason to open a "
        "second channel out of the tab, and a form would post the payload on submit."
    )


def test_the_runtime_is_pinned_to_a_hash_the_page_checks_itself() -> None:
    """SRI is not defined on a worker's script, so the page has to do the checking."""
    html = page_source()
    assert re.search(r'PYODIDE_SRI\s*=\s*\n?\s*"sha384-[A-Za-z0-9+/=]{60,}"', html), (
        "the pinned Pyodide hash is gone or is not a sha384 digest"
    )
    assert 'crypto.subtle.digest("SHA-384"' in html, (
        "nothing in the page hashes the runtime it fetched. The worker is built out of "
        "those bytes, and a worker's top-level script cannot carry an integrity attribute, "
        "so this check is the only thing standing between the CDN and the payload."
    )
    assert "tag.integrity = PYODIDE_SRI" in html, (
        "the fallback path loads the runtime with a <script> tag and has to pin it with "
        "the integrity attribute"
    )


# -- the head names a card that is actually published --------------------------


def head_meta(name: str) -> str | None:
    """The ``content`` of one meta tag in the page's head, by property or name."""
    match = re.search(
        rf'(?:property|name)="{re.escape(name)}"\s*\n?\s*content="([^"]*)"', page_source()
    )
    if match is None:
        # The attribute order is not fixed by anything, so try the other one.
        match = re.search(
            rf'content="([^"]*)"\s*\n?\s*(?:property|name)="{re.escape(name)}"', page_source()
        )
    return match.group(1) if match else None


def test_the_head_declares_a_card_and_the_card_is_in_the_repository() -> None:
    """og:image naming a file nothing publishes is a blank rectangle wherever this is shared.

    ``web/a11y/audit.mjs`` checks the same tags in a browser and
    ``.github/workflows/pages.yml`` checks the file is in the artifact it
    uploads, but both need a runner. This is the one that runs in ``make
    verify``, so a card deleted in an editor fails before it is pushed.
    """
    for tag in ("og:image", "twitter:image"):
        value = head_meta(tag)
        assert value == f"{PUBLISHED_AT}{CARD_FILENAME}", (
            f"{tag} is {value!r}. It has to be the absolute address of the card this "
            f"repository publishes: a crawler reads this head from an origin that is not "
            f"this one, so a relative path resolves against the wrong site or nothing."
        )
    assert (ROOT / "web" / CARD_FILENAME).is_file(), (
        f"the head names web/{CARD_FILENAME} and the file is not there"
    )


def test_the_card_is_the_size_the_head_says_it_is() -> None:
    """Declared dimensions let a crawler lay the preview out before it fetches the image."""
    width, height = png_dimensions((ROOT / "web" / CARD_FILENAME).read_bytes())
    assert (width, height) == (1200, 630), (
        f"web/{CARD_FILENAME} is {width}x{height}. 1200x630 is the size the head declares "
        f"and the size every preview crops to."
    )
    assert head_meta("og:image:width") == str(width), "og:image:width disagrees with the file"
    assert head_meta("og:image:height") == str(height), "og:image:height disagrees with the file"


def test_the_card_is_described_for_a_reader_who_cannot_see_it() -> None:
    alt = head_meta("og:image:alt")
    assert alt and alt.strip(), (
        "og:image:alt is absent. In a preview the card carries the page's only words, and "
        "a reader who cannot see it gets none of them."
    )
    assert head_meta("twitter:card") == "summary_large_image", (
        "the card is 1200x630, which is the large-image layout; declaring 'summary' crops "
        "it to a square thumbnail"
    )


# -- the page says what it is, as well as what it validates --------------------
#
# The page carries two kinds of JSON-LD for two different audiences, and the
# whole difficulty is that a sweep cannot tell them apart by counting.
#
#   `#rule-corpus`, above: CTDL example payloads in ceterms: and ceasn:. They
#   are the subject matter -- the documents the playground validates.
#
#   `#page-schema`, in the head: one schema.org node whose subject is this
#   page. Before it, nothing on the site stated what a visitor had arrived at;
#   a machine reader got a rich description of several example credentials and
#   no statement at all about the tool. The page still scored as "has
#   structured data" to anything that counts JSON-LD, which is the trap.
#
# So these tests sweep for both, assert each sweep is non-empty before
# comparing anything, and derive the expected examples from the check modules
# rather than from a second list kept beside them.

#: The schema.org node's element id, its `@id`, and the type it declares.
#: Written out rather than read back out of the page, for the same reason
#: PUBLISHED_AT is: an expectation parsed out of the thing under test moves
#: with the mistake and stays green.
SCHEMA_ELEMENT_ID = "page-schema"
SCHEMA_NODE_ID = f"{PUBLISHED_AT}#playground"
SCHEMA_CONTEXT = "https://schema.org"
SCHEMA_TYPE = "WebApplication"
SCHEMA_CATEGORY = "DeveloperApplication"

#: SPDX identifier -> the license text it denotes. One entry, because the
#: project declares one license. Relicensing to something this map does not
#: know about fails here, rather than quietly leaving the old URL on the page.
LICENSE_URLS = {"Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0"}

#: Fields that would have to be a hand-kept copy of a number, a date or a
#: judgment that nothing derives for this page. The running version is read
#: off the wheel at boot, because `main` is routinely ahead of the last tag;
#: the rest do not exist at all. Any of them appearing in the node is this
#: portfolio's dominant defect -- a figure served long after the value moved,
#: with nothing able to notice -- installed in the one place on the page a
#: human reader never sees.
UNDERIVED_FIELDS = frozenset(
    {
        "aggregateRating",
        "dateCreated",
        "dateModified",
        "datePublished",
        "downloadUrl",
        "fileSize",
        "featureList",
        "interactionCount",
        "interactionStatistic",
        "ratingCount",
        "ratingValue",
        "review",
        "reviewCount",
        "softwareVersion",
        "version",
    }
)


def ld_json_blocks() -> list[str]:
    """Every ``application/ld+json`` block in the page, in document order."""
    return re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        page_source(),
        re.DOTALL,
    )


def page_schema() -> dict[str, Any]:
    """The one schema.org node, parsed.

    Parsed rather than pattern-matched, because "well formed" is the claim: a
    node a crawler cannot load says exactly as much as no node at all, and a
    regex over it would pass on JSON that does not parse.
    """
    blocks = ld_json_blocks()
    assert len(blocks) == 1, (
        f"web/index.html carries {len(blocks)} application/ld+json blocks; exactly one "
        "belongs there. A second would be a second statement about what this page is, "
        "and the CTDL examples are not written in that type for exactly this reason."
    )
    loaded: Any = json.loads(blocks[0])
    assert isinstance(loaded, dict), (
        f"the schema.org block is a {type(loaded).__name__}, not an object"
    )
    return loaded


def project_metadata() -> dict[str, Any]:
    manifest: dict[str, Any] = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project: dict[str, Any] = manifest["project"]
    return project


def keys_anywhere(value: Any) -> set[str]:
    """Every key in a nested structure, so a banned field cannot hide in `offers`."""
    if isinstance(value, dict):
        found = set(value)
        for nested in value.values():
            found |= keys_anywhere(nested)
        return found
    if isinstance(value, list):
        found = set()
        for item in value:
            found |= keys_anywhere(item)
        return found
    return set()


def test_the_page_carries_both_kinds_of_json_ld_and_neither_sweep_is_empty() -> None:
    """The gate for this page's structured data, both halves in one place.

    Both sweeps are asserted non-empty *before* anything is compared. The
    failure worth guarding against is a sweep that finds nothing and reports
    agreement: an empty set equals an empty set, so a page that had lost every
    example would sail through a test that only checked the two matched.
    """
    described = ld_json_blocks()
    assert described, (
        "web/index.html carries no application/ld+json block, so nothing on this page "
        "states what the page is. The CTDL documents below it describe example "
        "credentials; they say nothing about this tool, and a reader that counts JSON-LD "
        "will score the page as self-describing anyway."
    )

    examples = set(corpus())
    assert examples, (
        "web/index.html ships no CTDL example documents. The playground validates the "
        "documents in its own corpus to build its rule list, so an empty corpus is an "
        "empty page."
    )

    expected = rule_codes_in_source()
    assert expected, (
        "the check modules emit no finding codes, so the comparison below is two empty "
        "sets agreeing and proves nothing about either"
    )
    assert examples == expected, (
        f"the page's CTDL examples and the codes the source emits disagree: only on the "
        f"page {sorted(examples - expected)}, only in the source {sorted(expected - examples)}"
    )

    node = page_schema()
    assert node.get("@type") == SCHEMA_TYPE, (
        f"the schema.org node declares @type {node.get('@type')!r}, expected "
        f"{SCHEMA_TYPE!r}. This page is a tool, and the node is what says so."
    )
    serialized = json.dumps(node)
    assert "ceterms:" not in serialized and "ceasn:" not in serialized, (
        "the schema.org node names a CTDL vocabulary. The two kinds of JSON-LD on this "
        "page have been confused for each other: this one describes the page, the corpus "
        "describes credentials."
    )


def test_the_schema_org_node_is_addressable_and_sits_ahead_of_the_examples() -> None:
    """Three things keep a reader from mistaking the node for a third CTDL example."""
    html = page_source()
    node = page_schema()

    assert node.get("@context") == SCHEMA_CONTEXT, (
        f"the node's @context is {node.get('@context')!r}. Without schema.org's context "
        "its terms resolve to nothing and a crawler reads an untyped blob."
    )
    assert node.get("@id") == SCHEMA_NODE_ID, (
        f"the node's @id is {node.get('@id')!r}, expected {SCHEMA_NODE_ID!r}. A node with "
        "no stable identifier cannot be referred to, merged or superseded."
    )
    assert f'id="{SCHEMA_ELEMENT_ID}"' in html, (
        f"the node's script element has no id={SCHEMA_ELEMENT_ID!r}, which is how the "
        "next person tells it from the corpus without reading the JSON"
    )
    assert html.index(f'id="{SCHEMA_ELEMENT_ID}"') < html.index('id="rule-corpus"'), (
        "the schema.org node is below the CTDL corpus. It belongs in the head, with the "
        "rest of what this page says about itself, and the ordering is half of what makes "
        "the difference legible in the source."
    )


def test_the_page_finds_its_examples_by_id_and_never_by_element_type() -> None:
    """What makes it safe to put a second kind of JSON-LD on this page at all.

    The corpus is addressed by element id. Were the page ever to reach for its
    examples by selecting on a script element's type instead, the head's
    description of the tool would be loaded as a CTDL payload and handed to
    the validator as a document to check.
    """
    html = page_source()
    assert 'document.getElementById("rule-corpus")' in html, (
        "the page no longer reads its example corpus by element id. Whatever replaced it "
        "has to be checked against the schema.org node in the head before this passes."
    )
    selectors = re.findall(r'querySelectorAll?\(\s*"([^"]*script[^"]*)"', html)
    assert selectors == [], (
        f"the page selects script elements by CSS: {selectors}. That is how the "
        "application/ld+json node in the head gets swept up as a CTDL example."
    )
    assert "getElementsByTagName" not in html, (
        "the page collects elements by tag name, which is the other way the head's "
        "schema.org node ends up in the corpus"
    )


def test_the_schema_org_node_repeats_only_what_the_head_already_says() -> None:
    """Every claim traced back to the committed thing that already makes it.

    A head tag is served long after anyone reads it, so the only safe claim in
    one is a claim something else in the repository is responsible for. These
    are the six, and each is pinned to its source rather than to a copy.
    """
    node = page_schema()
    html = page_source()

    title_match = re.search(r"<title>([^<]*)</title>", html)
    assert title_match is not None, "the page has no <title>"
    expected_name = title_match.group(1).split(":")[0].strip()
    assert node.get("name") == expected_name, (
        f"the node names this page {node.get('name')!r}; the title calls it "
        f"{expected_name!r}. One page, one name."
    )

    assert node.get("description") == head_meta("description"), (
        "the node's description and the meta description disagree. They are two "
        "statements of the same sentence to two readers, and web/a11y/audit.mjs holds "
        "the meta description to what the page can actually claim -- a second copy "
        "drifting out from under that is how a claim nobody vetted gets published."
    )

    assert node.get("url") == PUBLISHED_AT, (
        f"the node's url is {node.get('url')!r}, expected {PUBLISHED_AT!r}. Five sibling "
        "projects publish under this origin and the bare origin is a 404, so an address "
        "without /ctdl-validate/ names another project or nothing."
    )

    lang_match = re.search(r'<html lang="([^"]*)"', html)
    assert lang_match is not None, "the document declares no language"
    assert node.get("inLanguage") == lang_match.group(1), (
        f"the node says inLanguage {node.get('inLanguage')!r} and the document declares "
        f"lang {lang_match.group(1)!r}"
    )

    repository = project_metadata()["urls"]["Repository"]
    assert node.get("sameAs") == repository, (
        f"the node's sameAs is {node.get('sameAs')!r}; pyproject.toml declares the "
        f"repository as {repository!r}"
    )
    assert f'href="{repository}"' in html, (
        "the page's footer no longer links the repository the node points at, so the two "
        "routes to the source have come apart"
    )

    assert node.get("applicationCategory") == SCHEMA_CATEGORY, (
        f"the node's applicationCategory is {node.get('applicationCategory')!r}, expected "
        f"{SCHEMA_CATEGORY!r}"
    )
    requirements = node.get("browserRequirements")
    assert isinstance(requirements, str) and "WebAssembly" in requirements, (
        f"the node states browserRequirements {requirements!r}. The page compiles a "
        "WebAssembly Python runtime and cannot run without one, which is the requirement "
        "worth stating."
    )
    assert "WebAssembly" in (head_meta("description") or ""), (
        "the description no longer says the tool runs on WebAssembly, so the node's "
        "browserRequirements is now a claim the page does not otherwise make"
    )


def test_the_schema_org_node_states_the_license_pyproject_declares() -> None:
    """The license is the one claim here that is not already in the head."""
    declared = project_metadata()["license"]["text"]
    assert declared in LICENSE_URLS, (
        f"pyproject.toml declares the license {declared!r} and this test knows no URL for "
        "it. Add it to LICENSE_URLS deliberately; a relicensed project quietly serving "
        "the old license to every machine reader is the failure this guards."
    )
    assert page_schema().get("license") == LICENSE_URLS[declared], (
        f"the node's license is {page_schema().get('license')!r}; pyproject.toml declares "
        f"{declared!r}, which is {LICENSE_URLS[declared]!r}"
    )
    assert (ROOT / "LICENSE").is_file(), "the repository ships no LICENSE file"


def test_the_node_says_free_in_both_places_or_in_neither() -> None:
    """schema.org states a price two ways, and a reader may believe either one."""
    node = page_schema()
    offers = node.get("offers")
    assert isinstance(offers, dict), f"the node's offers is {offers!r}, expected an object"
    assert offers.get("@type") == "Offer", f"offers declares @type {offers.get('@type')!r}"
    assert offers.get("price") == "0", (
        f"the node offers this page at {offers.get('price')!r}. It runs entirely in the "
        "reader's browser off a static page; there is nothing to charge for."
    )
    assert offers.get("priceCurrency"), (
        "a price with no currency is not a price schema.org will read"
    )
    assert node.get("isAccessibleForFree") is True, (
        f"isAccessibleForFree is {node.get('isAccessibleForFree')!r} beside a price of "
        f"{offers.get('price')!r}. The two say the same thing to different readers and "
        "cannot be allowed to disagree."
    )


def test_the_schema_org_node_states_no_figure_nothing_derives() -> None:
    """The fields left out, held out.

    Not a style preference. A rating, a review count, a download count, a
    release date or a version number written here would be served for as long
    as nobody happened to look, and no gate in this repository could tell. The
    version in particular is genuinely knowable -- and is read off the wheel at
    boot, in the footer, which is why it is not typed here.
    """
    present = sorted(keys_anywhere(page_schema()) & UNDERIVED_FIELDS)
    assert present == [], (
        f"the schema.org node states {present}. Nothing in this repository derives those "
        "for this page, so each one is a value typed once and served until someone "
        "notices -- in the one part of the page no visitor ever reads. The running "
        "version is shown in the footer, from the wheel the page actually loaded."
    )
