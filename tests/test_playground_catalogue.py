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

2. **The page's own derivation has to work.** The catalogue is built by Python
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
from pathlib import Path
from typing import Any

import pytest

from ctdl_validate import Severity, validate_document
from tests.test_every_rule_fires import codes_in_source

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "index.html"

#: Where GitHub Pages serves this page, and the card published beside it.
#: Written out rather than parsed back out of the page, for the same reason the
#: allowed origins below are: an expectation read out of the thing under test
#: moves with the mistake and stays green.
PUBLISHED_AT = "https://chelseakr.github.io/ctdl-validate/"
CARD_FILENAME = "social-card.png"

#: The two network origins the page is allowed to name, and the reason each is
#: there. Written out rather than parsed back out of the page, which is the
#: whole point: an expectation read out of the thing under test moves with the
#: mistake and stays green.
ALLOWED_ORIGINS = {
    "'self'": "the wheel, built from this commit by the Pages workflow",
    "https://cdn.jsdelivr.net": "the Pyodide runtime",
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
        "catalogue is built out of it, so it cannot have moved without this failing."
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
    missing = sorted(codes_in_source() - set(corpus()))
    assert missing == [], (
        "the check modules emit these and web/index.html ships no document that reaches "
        f"them, so the playground's rule list would be missing them: {missing}"
    )


def test_no_document_on_the_page_outlives_the_rule_it_was_written_for() -> None:
    stale = sorted(set(corpus()) - codes_in_source())
    assert stale == [], (
        "web/index.html files documents under these codes and no check module emits them "
        f"any more: {stale}. Remove the entry, or the rule was deleted by accident."
    )


@pytest.mark.parametrize("code", sorted(corpus()))
def test_the_page_document_still_produces_the_code_it_is_filed_under(
    code: str, tmp_path: Path
) -> None:
    """The behavioural half: each document is validated, not just named."""
    entry = corpus()[code]
    resolve = None
    if entry.get("resolve") is not None:
        neighbour = tmp_path / "neighbour.json"
        neighbour.write_text(json.dumps(entry["resolve"]), encoding="utf-8")
        resolve = [neighbour]
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
    assert codes == codes_in_source(), (
        "the scan embedded in web/index.html and the one in test_every_rule_fires.py "
        f"disagree: only on the page {sorted(codes - codes_in_source())}, only in the test "
        f"{sorted(codes_in_source() - codes)}"
    )


def test_the_page_would_render_a_derived_row_for_every_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End to end: the rows the visitor sees, produced by the code that produces them."""
    monkeypatch.chdir(tmp_path)
    derived = json.loads(page_python()["catalogue"](json.dumps(corpus())))
    rows = derived["rows"]
    assert derived["unreadable"] == 0
    assert {row["code"] for row in rows} == codes_in_source()
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
        "the static accessibility fixture renders a catalogue row with a 'load the payload' "
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


def test_the_policy_names_two_origins_and_no_others() -> None:
    """The playground's promise is that no payload leaves the tab. This is the control."""
    policy = content_security_policy()
    assert policy["default-src"] == ["'none'"], (
        "default-src is what closes every fetch directive this policy does not name; "
        f"it reads {policy['default-src']}"
    )
    assert set(policy["connect-src"]) == set(ALLOWED_ORIGINS), (
        f"connect-src is {policy['connect-src']}. Exactly two origins belong there: "
        + ", ".join(f"{origin} ({why})" for origin, why in sorted(ALLOWED_ORIGINS.items()))
    )
    hosts = [token for token in policy["script-src"] if "://" in token]
    assert hosts == ["https://cdn.jsdelivr.net"], (
        f"script-src names {hosts}. A second script origin is a second party who can "
        "change what runs against a payload the visitor has not published."
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
