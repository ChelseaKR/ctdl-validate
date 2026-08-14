from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = FIXTURES / "pages"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_path(name: str) -> Path:
    return FIXTURES / name


def page_path(name: str) -> Path:
    return PAGES / name


def load_page(name: str) -> str:
    """A synthetic HTML fixture. Nothing here is copied from a real site."""
    return (PAGES / name).read_text(encoding="utf-8")


# -- a server on localhost, so no test ever reaches the internet -------------


@dataclass
class Route:
    status: int = 200
    body: bytes = b""
    content_type: str = "text/html; charset=utf-8"
    location: str | None = None


@dataclass
class Site:
    base: str = ""
    requests: list[tuple[str, str]] = field(default_factory=list)


def _handler(routes: dict[str, Route], site: Site) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self) -> None:  # noqa: N802 - the name the stdlib dispatches on
            site.requests.append((self.path, self.headers.get("User-Agent", "")))
            route = routes.get(self.path)
            if route is None:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"not found")
                return
            self.send_response(route.status)
            if route.location is not None:
                self.send_header("Location", route.location)
            self.send_header("Content-Type", route.content_type)
            self.send_header("Content-Length", str(len(route.body)))
            self.end_headers()
            self.wfile.write(route.body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


@contextmanager
def serve(routes: dict[str, Route]) -> Iterator[Site]:
    site = Site()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(routes, site))
    site.base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield site
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def robots(body: str) -> Route:
    return Route(body=body.encode(), content_type="text/plain")


ALLOW_ALL = robots("User-agent: *\nDisallow:\n")
