"""The network posture, proven against a real server on localhost.

Every test here starts an HTTP server on 127.0.0.1, so the suite still makes
no calls to the internet. What is being proven is the part of the tool that
could do harm if it were wrong: that a Disallow stops the fetch, that an
unreachable robots.txt stops it, that redirects cannot smuggle the fetch onto
a host that has not been asked, and that the caps hold.
"""

from __future__ import annotations

import pytest

from ctdl_validate.extract.fetch import (
    DEFAULT_USER_AGENT,
    PRODUCT_TOKEN,
    Fetcher,
    FetchError,
    origin_of,
)

from .conftest import ALLOW_ALL, Route, robots, serve

PAGE = b"<!doctype html><html lang='en'><body><p>hello</p></body></html>"


def fetcher() -> Fetcher:
    return Fetcher(min_interval=0.0, timeout=5.0)


# -- the hard stop ----------------------------------------------------------


def test_a_disallow_for_this_tool_is_a_hard_stop() -> None:
    rules = f"User-agent: {PRODUCT_TOKEN}\nDisallow: /programs/\n"
    routes = {"/robots.txt": robots(rules), "/programs/x": Route(body=PAGE)}
    with serve(routes) as site:
        with pytest.raises(FetchError, match="disallowed by"):
            fetcher().fetch(f"{site.base}/programs/x")
        asked = [path for path, _ in site.requests]
    assert asked == ["/robots.txt"], "the page itself was never requested"


def test_a_wildcard_disallow_applies_to_this_tool_too() -> None:
    disallow_all = robots("User-agent: *\nDisallow: /\n")
    with serve({"/robots.txt": disallow_all}) as site, pytest.raises(FetchError, match="disallow"):
        fetcher().fetch(f"{site.base}/anything")


def test_an_unreachable_robots_txt_stops_the_fetch() -> None:
    # RFC 9309 2.3.1.4: a 5xx means the file is undefined and the crawler MUST
    # assume complete disallow.
    routes = {"/robots.txt": Route(status=503, body=b"down"), "/page": Route(body=PAGE)}
    with serve(routes) as site, pytest.raises(FetchError, match="2.3.1.4"):
        fetcher().fetch(f"{site.base}/page")


def test_a_missing_robots_txt_allows_the_fetch() -> None:
    # RFC 9309 2.3.1.3: 4xx means unavailable, and the crawler MAY proceed.
    with serve({"/page": Route(body=PAGE)}) as site:
        result = fetcher().fetch(f"{site.base}/page")
    assert result.status == 200
    assert "2.3.1.3" in result.robots


def test_robots_txt_is_fetched_once_per_origin() -> None:
    routes = {"/robots.txt": ALLOW_ALL, "/a": Route(body=PAGE), "/b": Route(body=PAGE)}
    with serve(routes) as site:
        client = fetcher()
        client.fetch(f"{site.base}/a")
        client.fetch(f"{site.base}/b")
        assert [path for path, _ in site.requests].count("/robots.txt") == 1


# -- redirects --------------------------------------------------------------


def test_a_redirect_is_followed_and_recorded() -> None:
    routes = {
        "/robots.txt": ALLOW_ALL,
        "/old": Route(status=301, location="/new"),
        "/new": Route(body=PAGE),
    }
    with serve(routes) as site:
        result = fetcher().fetch(f"{site.base}/old")
    assert result.final_url.endswith("/new")
    assert result.redirects == (f"{site.base}/new",)


def test_a_redirect_cannot_carry_the_fetch_onto_a_disallowing_host() -> None:
    blocked = {"/robots.txt": robots("User-agent: *\nDisallow: /\n"), "/page": Route(body=PAGE)}
    with serve(blocked) as second:
        hop = Route(status=302, location=f"{second.base}/page")
        routes = {"/robots.txt": ALLOW_ALL, "/go": hop}
        with serve(routes) as first, pytest.raises(FetchError, match="disallowed by"):
            fetcher().fetch(f"{first.base}/go")
        asked = [path for path, _ in second.requests]
    assert asked == ["/robots.txt"], "the other host's page was never requested"


def test_a_redirect_loop_stops_at_the_documented_limit() -> None:
    loop = {"/robots.txt": ALLOW_ALL, "/loop": Route(status=302, location="/loop")}
    with serve(loop) as site, pytest.raises(FetchError, match="more than 5 redirects"):
        fetcher().fetch(f"{site.base}/loop")


# -- caps and content -------------------------------------------------------


def test_a_response_over_the_byte_cap_is_refused() -> None:
    big = {"/robots.txt": ALLOW_ALL, "/big": Route(body=b"x" * 5000)}
    with serve(big) as site, pytest.raises(FetchError, match="byte cap"):
        Fetcher(min_interval=0.0, max_bytes=100).fetch(f"{site.base}/big")


def test_a_non_html_response_is_refused_rather_than_parsed() -> None:
    feed = Route(body=b"{}", content_type="application/json")
    routes = {"/robots.txt": ALLOW_ALL, "/data.json": feed}
    with serve(routes) as site, pytest.raises(FetchError, match="Content-Type"):
        fetcher().fetch(f"{site.base}/data.json")


def test_an_http_error_is_not_a_page() -> None:
    with serve({"/robots.txt": ALLOW_ALL}) as site, pytest.raises(FetchError, match="HTTP 404"):
        fetcher().fetch(f"{site.base}/missing")


def test_only_http_and_https_are_opened() -> None:
    for url in ("file:///etc/passwd", "data:text/html,<p>x", "ftp://example.org/x"):
        with pytest.raises(FetchError, match="only http and https"):
            fetcher().fetch(url)


# -- identification ---------------------------------------------------------


def test_the_user_agent_identifies_the_tool_and_carries_the_product_token() -> None:
    with serve({"/robots.txt": ALLOW_ALL, "/page": Route(body=PAGE)}) as site:
        fetcher().fetch(f"{site.base}/page")
        sent = {agent for _, agent in site.requests}
    assert sent == {DEFAULT_USER_AGENT}
    assert DEFAULT_USER_AGENT.startswith(f"{PRODUCT_TOKEN}/")
    assert "github.com/ChelseaKR/ctdl-validate" in DEFAULT_USER_AGENT


def test_a_contact_extends_the_user_agent_without_replacing_it() -> None:
    client = Fetcher(contact="someone@example.org", min_interval=0.0)
    assert client.user_agent.startswith(f"{PRODUCT_TOKEN}/")
    assert "someone@example.org" in client.user_agent


def test_a_declared_crawl_delay_can_only_slow_the_tool_down() -> None:
    rules = f"User-agent: {PRODUCT_TOKEN}\nCrawl-delay: 9\nDisallow:\n"
    with serve({"/robots.txt": robots(rules), "/page": Route(body=PAGE)}) as site:
        client = Fetcher(min_interval=0.0, timeout=5.0)
        client._check_robots(f"{site.base}/page")
        assert client._delays[origin_of(f"{site.base}/page")] == 9.0
