"""The only place in this tool that opens a network connection.

The validator's promise is that it makes no network calls and no model calls,
and that the same input produces the same output byte for byte. Extraction
needs a page, so it needs the network, and the honest way to keep both is to
put every socket in one module with a stated posture and let the rest of the
extraction path stay a pure function of the bytes this module returns.

The posture, in full:

- **robots.txt is fetched first and obeyed.** A Disallow for this tool's
  product token is a hard stop with a nonzero exit code. There is no override
  flag, because a flag to ignore robots.txt is the whole of the harm.
- **An unreachable robots.txt is a stop, not a shrug** (RFC 9309 section
  2.3.1.4). A 4xx means no robots.txt exists and the fetch may proceed
  (section 2.3.1.3).
- **The User-Agent identifies the tool and links to its source** (section
  2.2.1). It can be extended with a contact, never replaced with a browser's.
- **Redirects are followed manually, at most five**, and robots.txt is checked
  again at every hop, so a redirect can never carry the fetch onto a host that
  disallows it.
- **One page per invocation**, http or https only, with a byte cap, a request
  timeout, and a minimum interval between requests to the same host that a
  site's own Crawl-delay can lengthen but not shorten.
- **Failures are loud.** Every stop raises :class:`FetchError` and exits 2.
  There is no partial page, and no empty extract standing in for a page that
  could not be fetched.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from .. import __version__

#: RFC 9309 section 2.2.1: a product token is letters, underscores, and hyphens.
PRODUCT_TOKEN = "ctdl-validate"
SOURCE_URL = "https://github.com/ChelseaKR/ctdl-validate"

DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MIN_INTERVAL = 1.0
#: RFC 9309 section 2.3.1.2: follow at least five consecutive redirects.
MAX_REDIRECTS = 5
#: RFC 9309 section 2.5: "The parsing limit MUST be at least 500 kibibytes."
ROBOTS_MAX_BYTES = 512 * 1024

ALLOWED_SCHEMES = ("http", "https")
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
REDIRECT_STATUSES = (301, 302, 303, 307, 308)

_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([a-zA-Z0-9_\-]+)""", re.IGNORECASE)
_HEAD_BYTES = 2048

Headers = dict[str, str]


def user_agent(contact: str | None = None) -> str:
    """The identification string, with the product token as a substring."""
    detail = f"+{SOURCE_URL}" + (f"; {contact}" if contact else "")
    return f"{PRODUCT_TOKEN}/{__version__} ({detail})"


DEFAULT_USER_AGENT = user_agent()


class FetchError(RuntimeError):
    """The page could not be fetched, for any reason, including robots.txt."""


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    encoding: str
    bytes_read: int
    redirects: tuple[str, ...]
    robots: str
    text: str = field(repr=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "status": self.status,
            "content_type": self.content_type,
            "encoding": self.encoding,
            "bytes": self.bytes_read,
            "redirects": list(self.redirects),
            "robots": self.robots,
        }


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Hand redirects back to the caller so robots.txt can be re-checked."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def origin_of(url: str) -> str:
    parts = urlparse(url)
    return urlunparse((parts.scheme, parts.netloc, "", "", "", ""))


def _headers(raw: object) -> Headers:
    """Header names lower-cased, so lookups do not depend on a server's casing."""
    items = raw.items() if hasattr(raw, "items") else []
    return {str(name).lower(): str(value) for name, value in items}


def _require_fetchable(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise FetchError(
            f"{url}: only http and https URLs are fetched (got "
            f"{parts.scheme or 'no scheme'}). Nothing else is opened, including "
            "file: and data: URLs."
        )
    if not parts.netloc:
        raise FetchError(f"{url}: no host in the URL")


def _charset(content_type: str, body: bytes) -> str:
    for parameter in content_type.split(";")[1:]:
        name, _, value = parameter.partition("=")
        if name.strip().lower() == "charset" and value.strip():
            return value.strip().strip('"')
    declared = _META_CHARSET.search(body[:_HEAD_BYTES])
    return declared.group(1).decode("ascii") if declared else "utf-8"


def _decode(body: bytes, content_type: str) -> tuple[str, str]:
    """Decode using the encoding the response or the markup declares."""
    encoding = _charset(content_type, body)
    try:
        return body.decode(encoding), encoding
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace"), f"{encoding} (undecodable, replaced)"


class Fetcher:
    """A polite, single-page HTTP client. One per run; it holds the rate limit.

    The posture -- robots.txt first and obeyed, an identifying User-Agent,
    manual redirects re-checked at every hop, a byte cap, a timeout, and a
    per-host interval -- is the class's whole reason to exist and is not
    configurable. What media type a caller is willing to read is not part of
    that posture, so it is the one knob: ``accepted_content_types``. The
    ``extract`` command reads HTML. ``tools/registry_survey.py`` subclasses
    this to read the Registry API's JSON through the identical posture rather
    than writing a second, less careful HTTP client.
    """

    #: Response media types this fetcher will read. Anything else is an error,
    #: never a silent empty result.
    accepted_content_types: tuple[str, ...] = HTML_CONTENT_TYPES

    def __init__(
        self,
        contact: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ) -> None:
        self.user_agent = user_agent(contact)
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.min_interval = min_interval
        self._opener = urllib.request.build_opener(_NoRedirects)
        self._robots: dict[str, tuple[RobotFileParser | None, str]] = {}
        self._delays: dict[str, float] = {}
        self._last_request: dict[str, float] = {}

    # -- transport --------------------------------------------------------

    def _request(self, url: str, limit: int) -> tuple[int, Headers, bytes]:
        # The URL is the operator's own argument, restricted to http and https
        # by _require_fetchable before this is reached. No response body is
        # executed or interpreted here, and the only URL this method is ever
        # handed that did not come from the operator is a Location header,
        # which fetch() re-checks against robots.txt before following.
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": ", ".join(self.accepted_content_types),
            },
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return int(response.status), _headers(response.headers), response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            body = exc.read(limit + 1)
            headers = _headers(exc.headers)
            exc.close()
            return int(exc.code), headers, body
        except (urllib.error.URLError, OSError) as exc:
            raise FetchError(f"{url}: request failed ({exc})") from exc

    def _wait(self, origin: str) -> None:
        delay = self._delays.get(origin, self.min_interval)
        previous = self._last_request.get(origin)
        if previous is not None:
            remaining = delay - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[origin] = time.monotonic()

    # -- robots.txt -------------------------------------------------------

    def _robots_for(self, origin: str) -> tuple[RobotFileParser | None, str]:
        cached = self._robots.get(origin)
        if cached is not None:
            return cached
        self._wait(origin)
        result = self._read_robots(f"{origin}/robots.txt")
        self._robots[origin] = result
        return result

    def _read_robots(self, robots_url: str) -> tuple[RobotFileParser | None, str]:
        current = robots_url
        for _ in range(MAX_REDIRECTS + 1):
            status, headers, body = self._request(current, ROBOTS_MAX_BYTES)
            location = headers.get("location")
            if status in REDIRECT_STATUSES and location:
                current = urljoin(current, location)
                continue
            return self._robots_from_response(status, body, current)
        raise FetchError(f"{robots_url}: more than {MAX_REDIRECTS} redirects fetching robots.txt")

    def _robots_from_response(
        self, status: int, body: bytes, url: str
    ) -> tuple[RobotFileParser | None, str]:
        if 200 <= status < 300:
            parser = RobotFileParser()
            parser.parse(_decode(body[:ROBOTS_MAX_BYTES], "text/plain")[0].splitlines())
            return parser, f"read from {url} (HTTP {status})"
        if 400 <= status < 500:
            # RFC 9309 2.3.1.3: unavailable, so any resource may be accessed.
            return None, f"none published at {url} (HTTP {status}); RFC 9309 2.3.1.3 allows it"
        # RFC 9309 2.3.1.4: unreachable means complete disallow.
        raise FetchError(
            f"{url}: HTTP {status}. RFC 9309 section 2.3.1.4 requires a crawler to "
            "assume complete disallow when robots.txt is unreachable, so nothing was "
            "fetched from this host."
        )

    def _check_robots(self, url: str) -> str:
        origin = origin_of(url)
        parser, description = self._robots_for(origin)
        if parser is None:
            return description
        if not parser.can_fetch(self.user_agent, url):
            raise FetchError(
                f"{url}: disallowed by {origin}/robots.txt for the product token "
                f"{PRODUCT_TOKEN}. This is a hard stop; there is no flag to override it."
            )
        delay = parser.crawl_delay(self.user_agent)
        if delay is not None:
            self._delays[origin] = max(self.min_interval, float(delay))
        return f"{description}, fetch allowed"

    # -- the fetch --------------------------------------------------------

    def fetch(self, url: str) -> FetchResult:
        """Fetch one page politely, or raise FetchError saying exactly why not."""
        current = url
        redirects: list[str] = []
        for _ in range(MAX_REDIRECTS + 1):
            _require_fetchable(current)
            robots = self._check_robots(current)
            self._wait(origin_of(current))
            status, headers, body = self._request(current, self.max_bytes)
            location = headers.get("location")
            if status in REDIRECT_STATUSES and location:
                current = urljoin(current, location)
                redirects.append(current)
                continue
            content_type, text, encoding = self._read_page(current, status, headers, body)
            return FetchResult(
                requested_url=url,
                final_url=current,
                status=status,
                content_type=content_type,
                encoding=encoding,
                bytes_read=len(body),
                redirects=tuple(redirects),
                robots=robots,
                text=text,
            )
        raise FetchError(
            f"{url}: more than {MAX_REDIRECTS} redirects. RFC 9309 section 2.3.1.2 "
            "sets five as the limit a crawler must follow; beyond it this tool stops."
        )

    def _read_page(
        self, url: str, status: int, headers: Headers, body: bytes
    ) -> tuple[str, str, str]:
        if not 200 <= status < 300:
            raise FetchError(f"{url}: HTTP {status}")
        if len(body) > self.max_bytes:
            raise FetchError(
                f"{url}: response exceeds the {self.max_bytes} byte cap and was not "
                "read further. Raise --max-bytes deliberately if the page really is "
                "that large."
            )
        content_type = headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() not in self.accepted_content_types:
            raise FetchError(
                f"{url}: Content-Type is {content_type or 'absent'}; this reads "
                f"{' and '.join(self.accepted_content_types)} only. A JSON-LD file "
                "that is already CTDL should be validated directly, not extracted."
            )
        text, encoding = _decode(body, content_type)
        return content_type, text, encoding
