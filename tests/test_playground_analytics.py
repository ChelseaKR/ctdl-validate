"""The playground's analytics loads only where, and only as, ADR 0007 says.

`web/index.html` and `web/privacy.html` each carry one inline
``<script id="analytics">`` that may load Google Analytics 4. It must load
nothing at all -- no ``dataLayer``, no request, no cookie -- without a
measurement ID, off the published address, under Global Privacy Control or Do
Not Track, or after the visitor opts out. When it does load, the configuration
is the one the privacy page describes.

A string match over the script cannot tell a guard that runs from one that
does not, so the script is *executed* here, under Node, against a stub
window, navigator and document, once per case. Node is on every GitHub
runner; locally these tests skip without it, and in CI (``CI`` set) they fail
instead, so a runner that lost Node cannot turn them green by skipping.

The expected values are written out below rather than read back out of the
page, for the reason ``tests/test_playground_catalog.py`` gives: an
expectation parsed out of the thing under test moves with the mistake.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "index.html"
PRIVACY = ROOT / "web" / "privacy.html"
PAGES = (INDEX, PRIVACY)

#: GA4 property 554869909's web stream. Public: it is in every page served.
MEASUREMENT_ID = "G-QQV001MBJ7"
PUBLISHED = "https://chelseakr.github.io/ctdl-validate/"
GTAG_SRC = f"https://www.googletagmanager.com/gtag/js?id={MEASUREMENT_ID}"
OPT_OUT_KEY = "ctdl-validate:analytics-opt-out"

#: Where analytics_storage defaults to denied: the 27 EU member states, the
#: rest of the EEA, the UK and Switzerland. ISO 3166-1 alpha-2.
DENIED_REGIONS = [
    *("AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE"),
    *("IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"),
    *("IS", "LI", "NO"),
    *("GB", "CH"),
]

ADS_DENIED = {"ad_storage": "denied", "ad_user_data": "denied", "ad_personalization": "denied"}

#: Runs the page's script against stubs and prints what it did, as JSON.
HARNESS = r"""
const fs = require("fs");
const code = fs.readFileSync(process.argv[2], "utf8");
const scenario = JSON.parse(process.argv[3]);
const appended = [];
const listeners = {};
function control(text, hidden) {
  return {
    hidden, textContent: text, handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
  };
}
const elements = scenario.footer === false ? {} : {
  "analytics-choice": control("", true),
  "analytics-opt-out": control("Opt out of analytics", true),
  "analytics-status": control("", false),
};
const store = new Map(Object.entries(scenario.storage || {}));
const storage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => { store.set(key, String(value)); },
  removeItem: (key) => { store.delete(key); },
};
const url = new URL(scenario.url);
const window = {
  location: {
    href: url.href, protocol: url.protocol, hostname: url.hostname, origin: url.origin,
    pathname: url.pathname, search: url.search, hash: url.hash,
  },
};
if ("windowDnt" in scenario) window.doNotTrack = scenario.windowDnt;
Object.defineProperty(window, "localStorage", {
  get() {
    if (scenario.storageBlocked) throw new Error("SecurityError: storage is blocked");
    return storage;
  },
});
const navigator = {};
if ("gpc" in scenario) navigator.globalPrivacyControl = scenario.gpc;
if ("dnt" in scenario) navigator.doNotTrack = scenario.dnt;
if ("msDnt" in scenario) navigator.msDoNotTrack = scenario.msDnt;
const document = {
  head: { appendChild(el) { appended.push({ tag: el.tagName, src: el.src, async: el.async }); } },
  createElement(tag) { return { tagName: tag.toUpperCase() }; },
  getElementById(id) { return elements[id] || null; },
  addEventListener(type, handler) { listeners[type] = handler; },
};
new Function("window", "navigator", "document", code)(window, navigator, document);
if (listeners.DOMContentLoaded) listeners.DOMContentLoaded();
const button = elements["analytics-opt-out"];
for (let i = 0; i < (scenario.clicks || 0); i++) {
  if (button && button.handlers.click) button.handlers.click();
}
const view = (id) =>
  elements[id] ? { hidden: elements[id].hidden, text: elements[id].textContent } : null;
process.stdout.write(JSON.stringify({
  dataLayer: window.dataLayer === undefined ? null : window.dataLayer.map((a) => Array.from(a)),
  appended,
  listeners: Object.keys(listeners),
  choice: view("analytics-choice"),
  button: view("analytics-opt-out"),
  status: view("analytics-status"),
  storage: Object.fromEntries(store),
  gaDisable: window["ga-disable-" + scenario.id] ?? null,
}));
"""


def analytics_script(page: Path) -> str:
    """The one analytics script in a page, and a check that it sits in the head."""
    source = page.read_text(encoding="utf-8")
    blocks = re.findall(r'<script id="analytics">(.*?)</script>', source, re.DOTALL)
    assert len(blocks) == 1, f"{page.name} carries {len(blocks)} analytics scripts, not 1"
    head_end = source.index("</head>")
    assert source.index('<script id="analytics">') < head_end, (
        f"{page.name}'s analytics script is not in the head"
    )
    return str(blocks[0])


def run(script: str, tmp_path: Path, **scenario: Any) -> dict[str, Any]:
    """Execute ``script`` under Node against stubs, and return what it did."""
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("node is not on PATH in CI, so the analytics script cannot be executed")
        pytest.skip("node is not installed; the analytics script is executed in CI")
    scenario.setdefault("url", PUBLISHED)
    scenario.setdefault("id", MEASUREMENT_ID)
    code = tmp_path / "analytics.js"
    code.write_text(script, encoding="utf-8")
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    completed = subprocess.run(
        [node, str(harness), str(code), json.dumps(scenario)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    result: dict[str, Any] = json.loads(completed.stdout)
    return result


def loaded_nothing(result: dict[str, Any]) -> bool:
    return result["dataLayer"] is None and result["appended"] == []


def sabotage(script: str, line: str, replacement: str = "") -> str:
    """Remove or replace one exact line of the script, and prove that it happened.

    A negative control whose edit silently matched nothing would leave the
    script intact and read as a pass, so the edit is asserted before any
    verdict is read.
    """
    assert script.count(line) == 1, f"the line to sabotage is not in the script once: {line!r}"
    changed = script.replace(line, replacement)
    assert changed != script
    assert line not in changed
    return changed


@pytest.fixture(scope="module")
def script() -> str:
    return analytics_script(INDEX)


# -- where the ID lives, and that both pages carry the same script -------------


def test_both_pages_carry_the_same_script_once_in_the_head() -> None:
    assert analytics_script(INDEX) == analytics_script(PRIVACY), (
        "privacy.html's analytics script is no longer a byte-for-byte copy of index.html's"
    )


def test_the_committed_id_is_this_sites_property(script: str) -> None:
    assert f'var GA4_ID = "{MEASUREMENT_ID}";' in script
    assert f'var OPT_OUT_KEY = "{OPT_OUT_KEY}";' in script


def test_no_page_loads_google_except_through_the_guarded_script() -> None:
    """A static <script src> would load before, and regardless of, every guard."""
    for page in PAGES:
        source = page.read_text(encoding="utf-8")
        outside = source.replace(analytics_script(page), "")
        assert not re.search(r"<script[^>]*\bsrc=[^>]*google", outside, re.IGNORECASE), page.name
        assert "gtag(" not in outside, f"{page.name} calls gtag outside the guarded script"
        assert not re.search(r"\bdataLayer\s*[.=\[]", outside), (
            f"{page.name} touches dataLayer outside the script"
        )


# -- the published page, with no signal: GA loads, configured as documented ---


@pytest.mark.parametrize(
    "url",
    [
        PUBLISHED,
        PUBLISHED + "index.html",
        PUBLISHED + "privacy.html",
        "https://chelseakr.github.io/ctdl-validate",
        PUBLISHED + "?from=somewhere#p=A-SHARE-LINK-PAYLOAD",
    ],
)
def test_on_the_published_page_ga_loads_with_the_documented_config(
    script: str, tmp_path: Path, url: str
) -> None:
    result = run(script, tmp_path, url=url)
    path = re.split(r"[#?]", url, maxsplit=1)[0].removeprefix("https://chelseakr.github.io")
    expected_location = f"https://chelseakr.github.io{path}"
    commands = result["dataLayer"]
    assert [c[0] for c in commands] == ["consent", "consent", "js", "config"]
    assert commands[0] == ["consent", "default", {**ADS_DENIED, "analytics_storage": "granted"}]
    assert commands[1] == [
        "consent",
        "default",
        {**ADS_DENIED, "analytics_storage": "denied", "region": DENIED_REGIONS},
    ]
    assert commands[3] == [
        "config",
        MEASUREMENT_ID,
        {
            "page_location": expected_location,
            "allow_google_signals": False,
            "allow_ad_personalization_signals": False,
        },
    ]
    assert result["appended"] == [{"tag": "SCRIPT", "src": GTAG_SRC, "async": True}]
    assert "A-SHARE-LINK-PAYLOAD" not in json.dumps(commands)
    assert "from=somewhere" not in json.dumps(commands)
    assert result["choice"]["hidden"] is False
    assert result["button"] == {"hidden": False, "text": "Opt out of analytics"}


def test_the_denied_regions_are_the_eea_the_uk_and_switzerland() -> None:
    assert len(DENIED_REGIONS) == len(set(DENIED_REGIONS)) == 32


# -- no ID, or not the published page: nothing loads, nothing is offered -------


@pytest.mark.parametrize("value", ["", "UA-12345-1", "g-qqv001mbj7", "G-QQV001MBJ7 "])
def test_without_a_usable_id_nothing_loads(script: str, tmp_path: Path, value: str) -> None:
    changed = sabotage(script, f'var GA4_ID = "{MEASUREMENT_ID}";', f'var GA4_ID = "{value}";')
    result = run(changed, tmp_path)
    assert loaded_nothing(result)
    assert result["listeners"] == []
    assert result["choice"]["hidden"] is True


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8931/index.html?a11y-static",
        "http://127.0.0.1:8932/index.html",
        "http://localhost:8899/",
        "http://chelseakr.github.io/ctdl-validate/",
        "https://chelseakr.github.io/",
        "https://chelseakr.github.io/tods-validate/",
        "https://chelseakr.github.io/ctdl-validate-fork/",
        "https://someone-else.github.io/ctdl-validate/",
        "https://chelseakr.github.io.example.com/ctdl-validate/",
    ],
)
def test_off_the_published_page_nothing_loads(script: str, tmp_path: Path, url: str) -> None:
    result = run(script, tmp_path, url=url)
    assert loaded_nothing(result)
    assert result["listeners"] == []
    assert result["choice"]["hidden"] is True


# -- GPC, DNT and the opt-out: nothing loads -----------------------------------


@pytest.mark.parametrize(
    "signal",
    [
        {"gpc": True},
        {"dnt": "1"},
        {"dnt": "yes"},
        {"windowDnt": "1"},
        {"msDnt": "1"},
        {"gpc": True, "dnt": "1"},
    ],
)
def test_gpc_or_dnt_loads_nothing(script: str, tmp_path: Path, signal: dict[str, Any]) -> None:
    result = run(script, tmp_path, **signal)
    assert loaded_nothing(result)
    assert result["choice"]["hidden"] is False
    assert result["button"]["hidden"] is True
    assert "Global Privacy Control or Do Not Track" in result["status"]["text"]


@pytest.mark.parametrize("signal", [{"gpc": False}, {"dnt": "0"}, {"dnt": "unspecified"}])
def test_a_signal_that_is_off_does_not_stop_ga(
    script: str, tmp_path: Path, signal: dict[str, Any]
) -> None:
    assert not loaded_nothing(run(script, tmp_path, **signal))


def test_the_opt_out_flag_loads_nothing(script: str, tmp_path: Path) -> None:
    result = run(script, tmp_path, storage={OPT_OUT_KEY: "1"})
    assert loaded_nothing(result)
    assert result["button"] == {"hidden": False, "text": "Opt back in"}
    assert result["status"]["text"] == "Analytics is off on this device."


@pytest.mark.parametrize(
    "storage",
    [
        {},
        {OPT_OUT_KEY: "0"},
        {"analytics-opt-out": "1"},
        {"trout-truck:analytics-opt-out": "1"},
        {"disclosed:analytics-opt-out": "1"},
    ],
)
def test_only_this_sites_key_opts_out(script: str, tmp_path: Path, storage: dict[str, str]) -> None:
    """chelseakr.github.io project sites share one origin, so one localStorage."""
    assert not loaded_nothing(run(script, tmp_path, storage=storage))


def test_a_click_is_remembered_and_a_second_click_undoes_it(script: str, tmp_path: Path) -> None:
    once = run(script, tmp_path, clicks=1)
    assert once["storage"] == {OPT_OUT_KEY: "1"}
    assert once["gaDisable"] is True
    assert once["button"]["text"] == "Opt back in"
    assert once["status"]["text"] == "Analytics is off on this device."

    next_page = run(script, tmp_path, storage=once["storage"])
    assert loaded_nothing(next_page)

    twice = run(script, tmp_path, clicks=2)
    assert twice["storage"] == {}
    assert twice["gaDisable"] is False
    assert twice["button"]["text"] == "Opt out of analytics"
    assert twice["status"]["text"] == "Analytics is back on from the next page you open."


def test_blocked_storage_still_honors_a_click_for_this_page(script: str, tmp_path: Path) -> None:
    result = run(script, tmp_path, storageBlocked=True, clicks=1)
    assert not loaded_nothing(result), "blocked storage is not an opt-out"
    assert result["gaDisable"] is True
    assert "lasts only until you leave this page" in result["status"]["text"]


def test_a_page_without_the_footer_control_still_loads(script: str, tmp_path: Path) -> None:
    assert not loaded_nothing(run(script, tmp_path, footer=False))


# -- negative controls: the harness sees a missing guard -----------------------


@pytest.mark.parametrize(
    ("guard", "scenario"),
    [
        ("if (n.globalPrivacyControl === true) return;", {"gpc": True}),
        ('if (dnt === "1" || dnt === "yes") return;', {"dnt": "1"}),
        ("if (optedOut) return;", {"storage": {OPT_OUT_KEY: "1"}}),
        (
            'if (l.protocol !== "https:" || l.hostname !== PUBLISHED_HOST) return;',
            {"url": "http://127.0.0.1:8931/ctdl-validate/"},
        ),
        (
            'if (l.pathname !== "/ctdl-validate" && l.pathname.indexOf(PUBLISHED_PATH) !== 0) '
            "return;",
            {"url": "https://chelseakr.github.io/tods-validate/"},
        ),
    ],
)
def test_removing_a_guard_is_caught(
    script: str, tmp_path: Path, guard: str, scenario: dict[str, Any]
) -> None:
    assert loaded_nothing(run(script, tmp_path, **scenario)), "the intact script must hold"
    broken = sabotage(script, guard)
    assert not loaded_nothing(run(broken, tmp_path, **scenario)), (
        f"with {guard!r} removed the harness still saw nothing load, so it cannot see that guard"
    )


def test_turning_google_signals_on_is_caught(script: str, tmp_path: Path) -> None:
    broken = sabotage(
        script,
        "allow_google_signals: false,",
        "allow_google_signals: true,",
    )
    config = run(broken, tmp_path)["dataLayer"][3][2]
    assert config["allow_google_signals"] is True


# -- the footer, the privacy page, and the claims around them -------------------


def test_each_page_has_one_hidden_opt_out_control() -> None:
    for page in PAGES:
        source = page.read_text(encoding="utf-8")
        assert source.count('<span id="analytics-choice" hidden>') == 1, page.name
        assert (
            source.count(
                '<button type="button" id="analytics-opt-out" class="link-button" hidden>'
                "Opt out of analytics</button>"
            )
            == 1
        ), page.name
        assert source.count('<span id="analytics-status" role="status"></span>') == 1, page.name


def test_the_playground_footer_links_the_privacy_page() -> None:
    source = INDEX.read_text(encoding="utf-8")
    footer = source[source.index("<footer>") : source.index("</footer>")]
    assert '<a href="privacy.html">Privacy</a>' in footer
    assert "Google Analytics" in footer


def test_the_privacy_page_describes_what_the_script_does() -> None:
    text = re.sub(r"\s+", " ", PRIVACY.read_text(encoding="utf-8"))
    for fact in (
        "Google Analytics 4",
        f"_ga_{MEASUREMENT_ID.removeprefix('G-')}",
        OPT_OUT_KEY,
        "Global Privacy Control or Do Not Track",
        "Google signals and ad personalization are off",
        "European Economic Area, the UK and Switzerland",
        "cookieless ping",
        "14 months",
        "never sent anywhere",
        "without anything after a <code>#</code> or <code>?</code>",
    ):
        assert fact in text, f"privacy.html no longer says {fact!r}"


#: Claims that were true before the page had analytics and are false with it.
#: "no telemetry" is not here: the README says it of the command-line tool,
#: which still has none, and ADR 0007 keeps analytics to the web page.
FALSE_NOW = (
    "no analytics",
    "no tracking",
    "no cookies",
    "nothing is collected",
    "playground needs exactly two network origins",
    "policy allows exactly two network origins",
    "policy down to two origins",
)


def test_no_visitor_facing_text_still_claims_there_is_no_analytics() -> None:
    for path in (
        INDEX,
        PRIVACY,
        ROOT / "README.md",
        ROOT / "web" / "README.md",
        ROOT / ".github" / "workflows" / "pages.yml",
    ):
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8")).lower()
        found = [claim for claim in FALSE_NOW if claim in text]
        assert found == [], f"{path.relative_to(ROOT)} still says {found}"


def test_the_false_claims_list_would_have_caught_the_old_wording() -> None:
    """A negative control for the list above: each claim matches the text it replaced."""
    old = (
        "content-security-policy: the playground needs exactly two network origins; "
        "the page's content-security-policy allows exactly two network origins; "
        "no analytics, no tracking, no cookies; nothing is collected; "
        "it also keeps the page's content-security-policy down to two origins"
    ).lower()
    assert [claim for claim in FALSE_NOW if claim not in old] == []
