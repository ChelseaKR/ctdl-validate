"""The repository's description of its own release must be the release.

From 2026-08-16 to 2026-08-21 the README's status line and the GitHub
repository description both read "0.1.0" while 0.2.1 was the release on PyPI,
and the README's `uses:` examples pointed at `@main` with a comment saying no
release carried the action, one release after one did. A validator whose front
page misreports its own version has the defect it exists to catch.

The version has one source of truth, `pyproject.toml`
(`tests/test_version_single_source.py` keeps the package from growing a second
one). These tests pin every place the repository *describes* that version to
it, and pin the release date to the CHANGELOG heading for it, so a release
commit has to move them together or fail the build. The GitHub repository
description cannot be read offline and is handled structurally instead: it no
longer carries a version at all.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CITATION = ROOT / "CITATION.cff"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
WEB_README = ROOT / "web" / "README.md"

RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def _version() -> str:
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version: str = manifest["project"]["version"]
    return version


def _releases() -> dict[str, str]:
    """version -> date, from the CHANGELOG's dated headings, newest first."""
    return dict(RELEASE_HEADING.findall(CHANGELOG.read_text(encoding="utf-8")))


def test_the_released_version_has_a_dated_changelog_section() -> None:
    releases = _releases()
    assert _version() in releases, f"CHANGELOG.md has no dated heading for {_version()}"
    for version, released in releases.items():
        date.fromisoformat(released)  # a heading date that does not parse is a typo
        assert version.count(".") == 2


def test_the_readme_status_line_names_the_release() -> None:
    text = README.read_text(encoding="utf-8")
    version, released = _version(), _releases()[_version()]
    assert f"**Status:** Beta. Version `{version}`, released {released}" in text
    other = [v for v in re.findall(r"Version `(\d+\.\d+\.\d+)`", text) if v != version]
    assert other == [], f"the README names a version that is not the release: {other}"


def test_the_action_examples_pin_the_released_tag() -> None:
    uses = re.findall(r"uses: ChelseaKR/ctdl-validate@(\S+)", README.read_text(encoding="utf-8"))
    assert uses, "the README no longer shows how to use the action"
    assert set(uses) == {f"v{_version()}"}, uses


def test_citation_carries_the_released_version_and_date() -> None:
    fields = dict(
        re.findall(
            r"^(version|date-released): \"?([^\"\n]+)\"?$",
            CITATION.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert fields.get("version") == _version(), fields
    assert fields.get("date-released") == _releases()[_version()], fields


def test_the_roadmap_names_exactly_the_changelogs_releases() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    releases = _releases()
    health = text.split("## Delivery health", 1)[1].split("\n## ", 1)[0]
    named = set(re.findall(r"`v(\d+\.\d+\.\d+)`", health))
    assert named == set(releases), (
        f"the ledger names {sorted(named)}; the CHANGELOG dates {sorted(releases)}"
    )
    for version, released in releases.items():
        assert released in health, f"the ledger does not date v{version} as {released}"
    count = len(releases)
    assert f"{count} releases in the" in health
    assert f"1 of {count}." in health or f"0 of {count}." in health


def test_the_roadmap_arithmetic_follows_from_its_own_timestamps() -> None:
    """The two derived figures are recomputed from the timestamps stated beside them."""
    health = ROADMAP.read_text(encoding="utf-8").split("## Delivery health", 1)[1]
    stamp = r"(\d{4}-\d{2}-\d{2}T[\d:]+Z)"
    restore = re.search(rf"\| Time to restore \| (\d+) minutes: .*?{stamp}.*?{stamp}", health)
    assert restore, "the Time to restore row has lost its timestamps"
    stated, first, second = restore.groups()
    elapsed = datetime.fromisoformat(second) - datetime.fromisoformat(first)
    assert int(stated) == round(elapsed.total_seconds() / 60)

    frequency = re.search(r"\| Deployment frequency \| \d+ releases in the (\d+) days", health)
    assert frequency, "the Deployment frequency row has lost its span"
    dates = sorted(date.fromisoformat(d) for d in _releases().values())
    assert int(frequency.group(1)) == (dates[-1] - dates[0]).days


def test_no_snippet_hardcodes_a_wheel_version() -> None:
    """web/README.md's local-run snippet once wrote "0.1.0" into wheel.json by hand."""
    assert not re.search(r'"version": "\d', WEB_README.read_text(encoding="utf-8"))
