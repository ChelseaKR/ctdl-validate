"""The boundary between the two commands, enforced rather than asserted.

The README promises no network calls at validation time. Adding a command that
fetches pages makes that promise worth proving instead of repeating, so these
tests take the socket away and run the validator anyway.
"""

from __future__ import annotations

import socket
from typing import Any, NoReturn

import pytest

from ctdl_validate.cli import main

from .conftest import fixture_path, page_path

FIXTURES = (
    "clean_framework.json",
    "bug_class_250_bare_uuid_for_ctid.json",
    "bug_class_252_wrong_framework_identifier.json",
    "external_reference.json",
)


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("this code path must not open a socket")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.mark.usefixtures("no_network")
def test_validation_opens_no_socket(capsys: pytest.CaptureFixture[str]) -> None:
    for name in FIXTURES:
        main([str(fixture_path(name))])
    assert "finding(s)" in capsys.readouterr().out


@pytest.mark.usefixtures("no_network")
def test_extracting_from_a_saved_page_opens_no_socket() -> None:
    args = ["extract", "https://example.edu/x", "--from-file", str(page_path("course_jsonld.html"))]
    assert main(args) == 0


@pytest.mark.usefixtures("no_network")
def test_resolving_a_reference_opens_no_socket(capsys: pytest.CaptureFixture[str]) -> None:
    # --resolve widens what a run can see using files the operator already has.
    # It is emphatically not "fetch the thing the reference points at".
    args = [
        str(fixture_path("external_reference.json")),
        "--resolve",
        str(fixture_path("resolve/owner_organization.json")),
    ]
    assert main(args) == 0
    assert "REF_RESOLVED_SUPPLIED" in capsys.readouterr().out


@pytest.mark.usefixtures("no_network")
def test_the_unverifiable_severity_is_still_never_a_fetch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A reference outside the payload is reported UNVERIFIABLE precisely
    # because resolving it would need the network the validator does not have.
    assert main([str(fixture_path("external_reference.json"))]) == 0
    assert "UNVERIFIABLE" in capsys.readouterr().out
