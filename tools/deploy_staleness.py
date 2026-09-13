#!/usr/bin/env python3
"""Is the playground a visitor gets the playground this repository has?

The site at https://chelseakr.github.io/ctdl-validate/ is not a copy of a
committed directory. `.github/workflows/pages.yml` builds it: it runs
`uv build --wheel`, copies `web/index.html` and `web/social-card.png` beside
the wheel, writes a `wheel.json` manifest naming it, and uploads that
directory. The published bytes are therefore a *function of a commit's source
tree*, which makes this publishing model case (1): **GitHub Pages built by a
workflow from source** (`build_type: workflow`). The comparison implemented
here is accordingly deployed-SHA versus `origin/main`, counting the commits in
between that touched something the build reads. A committed-tree comparison --
`git rev-parse <sha>:<path>` against head's -- would be meaningless here,
because no committed path holds the published bytes.

Why the deployment record and not `pages.yml`'s run history
-----------------------------------------------------------
`pages.yml` is path-filtered. It does not run on most pushes to `main`, and
when it does not run it leaves no trace that distinguishes "nothing needed
publishing" from "the publish never happened". Its run list is also full of
runs from other refs and from `workflow_dispatch`. A `github-pages` deployment
exists only because bytes were published, it names the commit they were built
from, and its statuses say whether the publish actually succeeded. That is the
one place the true answer is written down.

The path filter is the publishing contract, and it is incomplete
-----------------------------------------------------------------
`pages.yml` publishes on a push to `main` touching `web/**`, `src/**`,
`pyproject.toml` or `.github/workflows/pages.yml`. That list is one statement
of what the page is built from; `SITE_SOURCE_PREFIXES` below is a second
statement of the same thing, and on 2026-09-13 the two did not agree.

`uv build --wheel` reads two files the filter does not name. `pyproject.toml`
declares `readme = "README.md"`, so setuptools copies the README verbatim into
the wheel's `.dist-info/METADATA` (13,125 bytes of it in the wheel built at
`0.1.0`), and setuptools' PEP 639 default `license-files` glob copies `LICENSE`
into `.dist-info/licenses/LICENSE`. Both are published: the wheel is served
from this site's own origin and the page fetches it at boot. A commit that
touches only `README.md` therefore changes the bytes a visitor receives and
does not start a deploy. Eight of the 85 commits on `main` between 2026-08-06
and 2026-09-13 were exactly that shape. None of them went stale past the
threshold -- each was carried out later by an unrelated commit that did match
the filter, the longest wait being three days and twenty-three hours -- but
that is this repository publishing often for other reasons, not the contract
being right.

So this list covers what the build really reads, which means the sentinel can
see that gap. It is deliberately a *superset* of the filter and must stay one:
`tests/test_deploy_staleness.py` fails if a path is added to `pages.yml`'s
`paths:` and not here. The filter itself is untouched -- widening it changes
publishing policy, which is an owner decision, and this file changes nothing
about publishing.

The one place the two lists are loose in the other direction is `web/`:
`web/README.md` and `web/a11y/audit.mjs` sit under the filter's `web/**` but
are never copied into `site/`. Keeping the whole directory here rather than
naming the two copied files keeps this list a superset of the filter and makes
the failure direction over-reporting, which a reader can check in a minute. The
opposite error is a sentinel that stays quiet while the site is stale, which is
the failure this file exists to prevent.

The rule this file follows: a detector that cannot tell must refuse, never
report a comfortable zero. Every unmeasurable case below raises
`StalenessUnknown` rather than returning a number that would read as a
measurement.

Standard library only, and it imports nothing from the rest of this repository
-- not even `ctdl_validate` -- so the sentinel runs on a bare `python3` with no
dependency resolution and cannot be broken by one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REPO = "ChelseaKR/ctdl-validate"

#: The Pages environment a deployment has to belong to. A repository can carry
#: deployments for other environments; only this one is the published site.
PAGES_ENVIRONMENT = "github-pages"

#: How long an unpublished visitor-visible commit may wait before this reports.
#: Generous on purpose: it exists to catch a site that has gone months behind,
#: not to complain about an afternoon.
DEFAULT_MAX_AGE_DAYS = 14

#: Everything `.github/workflows/pages.yml` reads to produce the bytes it
#: uploads, and nothing else. The tests, the ADRs, the findings write-ups and
#: the CHANGELOG change `main` constantly without changing a published byte,
#: and counting them would make this number meaningless well before it made it
#: alarming.
#:
#: A trailing "/" means a directory prefix; anything else is an exact path.
#:
#: - ``web/`` and ``src/``, ``pyproject.toml`` and ``pages.yml`` itself are the
#:   publish filter, verbatim. ``pages.yml`` is on it because that workflow is
#:   the renderer: the assembly step is the only place the site's shape lives.
#: - ``README.md`` and ``LICENSE`` are **not** in the filter. They are here
#:   because ``uv build --wheel`` embeds them in the published wheel's
#:   ``.dist-info``; see the module docstring. This is the gap the sentinel can
#:   see and the filter cannot.
SITE_SOURCE_PREFIXES = (
    "web/",
    "src/",
    "pyproject.toml",
    ".github/workflows/pages.yml",
    "README.md",
    "LICENSE",
)

_SHA = re.compile(r"^[0-9a-f]{40}$")


class StalenessUnknown(Exception):
    """The comparison could not be made, so no number is reported.

    Raised in preference to returning zero anywhere the inputs do not support a
    measurement. The caller turns this into a red run: a sentinel that cannot
    tell is a broken sentinel, and it has to look broken.
    """


@dataclass(frozen=True)
class DeployRecord:
    """The published build: which commit it came from, and when it went out."""

    deployment_id: int
    sha: str
    created_at: datetime


@dataclass(frozen=True)
class Drift:
    """How far the published build is behind `main`."""

    deployed: DeployRecord
    head: str
    days: int
    commits: int
    visitor_commits: int
    max_age_days: int

    @property
    def overdue(self) -> bool:
        """Report only when something a visitor would receive is waiting.

        Age alone is not the signal. A site that has not been republished for a
        month because nothing it publishes has changed is correct, not stale --
        and this repository's publisher is path-filtered, so that is its normal
        state rather than an edge case.
        """
        return self.visitor_commits > 0 and self.days > self.max_age_days


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def newest_successful_deployment(
    deployments: Iterable[Mapping[str, Any]],
    statuses_for: Any,
) -> DeployRecord:
    """The most recent `github-pages` deployment that actually published.

    `statuses_for` is called with a deployment id and returns that deployment's
    statuses. A deployment row is a *request* to publish; its statuses are what
    say whether bytes landed. A deployment whose newest status is `failure`,
    `error` or `in_progress` never became a site, and treating its commit as
    the live one would report the site as fresher than it is -- the precise
    direction of error this whole file exists to prevent.
    """
    candidates = [
        d
        for d in deployments
        if d.get("environment") in (None, PAGES_ENVIRONMENT) and _SHA.match(str(d.get("sha", "")))
    ]
    if not candidates:
        raise StalenessUnknown(
            "no github-pages deployment in this repository's history: there is no published "
            "build to compare main against"
        )
    candidates.sort(key=lambda d: _parse_timestamp(str(d["created_at"])), reverse=True)

    for deployment in candidates:
        states = [str(s.get("state", "")) for s in statuses_for(deployment["id"])]
        if states and states[0] == "success":
            return DeployRecord(
                deployment_id=int(deployment["id"]),
                sha=str(deployment["sha"]),
                created_at=_parse_timestamp(str(deployment["created_at"])),
            )

    raise StalenessUnknown(
        f"none of the {len(candidates)} github-pages deployment(s) reports a successful status: "
        "nothing here proves any build was ever published"
    )


def ships_to_visitors(path: str) -> bool:
    """Does changing this file change the bytes the published site serves?"""
    return any(
        path.startswith(prefix) if prefix.endswith("/") else path == prefix
        for prefix in SITE_SOURCE_PREFIXES
    )


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _git(*args: str) -> str:
    result = _run_git(*args)
    if result.returncode != 0:
        raise StalenessUnknown(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _has_commit(sha: str) -> bool:
    """Whether this clone contains the commit, without raising on absence.

    `git cat-file` exits non-zero for a commit that is simply not here, which
    is the ordinary shallow-clone case and not a git failure. Routing it
    through `_git` would report it as one, and the refusal the caller raises --
    the one that names the shallow checkout and says why a zero would be wrong
    -- would never be reached.
    """
    return _run_git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def require_comparable(deployed_sha: str, head: str) -> None:
    """Refuse unless this clone can actually place the deployed commit on `main`.

    Both failures below report zero drift if they are not caught, and both are
    ordinary. A shallow checkout does not contain a commit from three weeks
    ago, so `git log <deployed>..HEAD` lists nothing and the site reads as up to
    date -- which is why the sentinel workflow checks out with `fetch-depth: 0`
    and why this refuses rather than trusting that it did. A force-push or a
    rebase leaves the deployed commit off `main` entirely, where "commits since"
    is not a question with an answer.
    """
    if not _SHA.match(deployed_sha):
        raise StalenessUnknown(f"deployed commit {deployed_sha!r} is not a commit id")
    if not _has_commit(deployed_sha):
        raise StalenessUnknown(
            f"deployed commit {deployed_sha[:9]} is not in this clone: the checkout is shallow, "
            "and a comparison against a history that does not reach the published build would "
            "report no drift at all"
        )
    merge_base = _git("merge-base", deployed_sha, head)
    if merge_base != _git("rev-parse", deployed_sha):
        raise StalenessUnknown(
            f"deployed commit {deployed_sha[:9]} is not an ancestor of {head}: the history has "
            "diverged and 'commits since the deploy' has no answer"
        )


def commits_between(deployed_sha: str, head: str) -> list[tuple[str, list[str]]]:
    """Each commit after the deployed one, with the paths it touched."""
    raw = _git("log", "--format=%x00%H", "--name-only", f"{deployed_sha}..{head}")
    commits: list[tuple[str, list[str]]] = []
    for block in raw.split("\x00"):
        stripped = block.strip("\n")
        if not stripped:
            continue
        lines = [line for line in stripped.splitlines() if line.strip()]
        commits.append((lines[0], lines[1:]))
    return commits


def measure(
    deployed: DeployRecord,
    head: str,
    now: datetime,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Drift:
    """Place the published build against `main`, or refuse."""
    head_sha = _git("rev-parse", head)
    require_comparable(deployed.sha, head_sha)
    commits = commits_between(deployed.sha, head_sha)
    visitor = [c for c in commits if any(ships_to_visitors(p) for p in c[1])]
    return Drift(
        deployed=deployed,
        head=head_sha,
        days=(now - deployed.created_at).days,
        commits=len(commits),
        visitor_commits=len(visitor),
        max_age_days=max_age_days,
    )


def render(drift: Drift) -> str:
    """The report. States the measurement before its verdict, always."""
    lines = [
        f"Published build:  {drift.deployed.sha[:9]}  "
        f"({drift.deployed.created_at.date().isoformat()}, "
        f"deployment {drift.deployed.deployment_id})",
        f"main:             {drift.head[:9]}",
        f"Behind by:        {drift.days} days, {drift.commits} commits, "
        f"{drift.visitor_commits} of them changing what a visitor receives",
    ]
    if drift.overdue:
        lines.append(
            f"\nOVERDUE: {drift.visitor_commits} visitor-visible commit(s) have waited "
            f"{drift.days} days, past the {drift.max_age_days}-day threshold. "
            "The live playground is not what this repository says it is."
        )
    elif drift.visitor_commits:
        lines.append(
            f"\nWaiting: {drift.visitor_commits} visitor-visible commit(s), "
            f"{drift.days} days, within the {drift.max_age_days}-day threshold."
        )
    else:
        lines.append("\nUp to date: nothing published has changed since the live build.")
    return "\n".join(lines)


def as_json(drift: Drift) -> dict[str, Any]:
    return {
        "deployed_sha": drift.deployed.sha,
        "deployed_at": drift.deployed.created_at.isoformat(),
        "deployment_id": drift.deployed.deployment_id,
        "head": drift.head,
        "days": drift.days,
        "commits": drift.commits,
        "visitor_commits": drift.visitor_commits,
        "overdue": drift.overdue,
    }


def _gh(path: str) -> Any:
    """Read the API through `gh`, which the runner already authenticates."""
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise StalenessUnknown(f"gh api {path} failed: {result.stderr.strip()}")
    loaded: Any = json.loads(result.stdout)
    return loaded


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--head", default="origin/main")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--json", action="store_true", help="emit the measurement as JSON")
    parser.add_argument(
        "--deployments-json",
        type=Path,
        help="read deployments from a file instead of the API (offline use and tests)",
    )
    args = parser.parse_args(argv)

    try:
        if args.deployments_json:
            payload = json.loads(args.deployments_json.read_text(encoding="utf-8"))
            deployments = payload["deployments"]
            statuses = payload["statuses"]

            def statuses_for(deployment_id: Any) -> list[Mapping[str, Any]]:
                recorded: list[Mapping[str, Any]] = statuses.get(str(deployment_id), [])
                return recorded
        else:
            deployments = _gh(
                f"repos/{args.repo}/deployments?environment={PAGES_ENVIRONMENT}&per_page=20"
            )

            def statuses_for(deployment_id: Any) -> list[Mapping[str, Any]]:
                fetched: list[Mapping[str, Any]] = _gh(
                    f"repos/{args.repo}/deployments/{deployment_id}/statuses?per_page=10"
                )
                return fetched

        deployed = newest_successful_deployment(deployments, statuses_for)
        drift = measure(deployed, args.head, datetime.now(UTC), args.max_age_days)
    except StalenessUnknown as exc:
        print(f"cannot measure deploy staleness: {exc}", file=sys.stderr)
        _write_github_output(None, str(exc))
        return 2

    print(json.dumps(as_json(drift), indent=2) if args.json else render(drift))
    _write_github_output(drift, None)
    return 0


def _write_github_output(drift: Drift | None, error: str | None) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        if drift is None:
            handle.write("measured=false\n")
            handle.write(f"error={error or 'unknown'}\n")
        else:
            handle.write("measured=true\n")
            handle.write(f"overdue={str(drift.overdue).lower()}\n")
            handle.write(f"days={drift.days}\n")
            handle.write(f"commits={drift.commits}\n")
            handle.write(f"visitor_commits={drift.visitor_commits}\n")
            handle.write(f"deployed_sha={drift.deployed.sha}\n")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
