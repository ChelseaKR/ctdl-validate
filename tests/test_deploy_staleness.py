"""The detector that answers "is the live playground the one this repo has?".

Written from both directions, because the failure this guards against is a
green gate. A detector that cannot fire is noise and gets deleted; a detector
that reports a number it did not really measure is worse than none, because the
number reads as a measurement and nobody re-derives it.

So the cases below cover the drift it must report AND every way the comparison
can be meaningless -- no deployment at all, a deployment that never succeeded,
a commit this clone does not contain, a history that has diverged. Each of
those must end in a refusal. None of them may end in a comfortable zero.

The case specific to this repository is
`test_every_path_that_triggers_a_publish_is_visitor_visible`. `pages.yml` is
path-filtered, so the filter *is* the publishing contract, and
`tools/deploy_staleness.py`'s `SITE_SOURCE_PREFIXES` is a second statement of
the same contract. Two statements of one thing drift apart silently; that test
is what stops them. It is deliberately one-directional -- the sentinel's list
must cover the filter, not equal it -- because `README.md` and `LICENSE` are
read by `uv build --wheel` and are not in the filter at all, which is the gap
`test_the_wheels_own_inputs_are_on_the_list_even_though_the_filter_omits_them`
pins down.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
SENTINEL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-staleness.yml"


def _tool(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution, not after: `@dataclass` resolves annotations
    # through `sys.modules[cls.__module__]`, so a module that is not there yet
    # raises on the decorator rather than on anything to do with this project.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


staleness = _tool("deploy_staleness")

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
DEPLOYED_AT = "2026-08-12T21:06:40Z"


def _deployment(**over: Any) -> dict[str, Any]:
    row = {
        "id": 5877359082,
        "sha": "c" * 40,
        "environment": "github-pages",
        "created_at": DEPLOYED_AT,
    }
    row.update(over)
    return row


def _succeeded(_id: Any) -> list[Mapping[str, Any]]:
    return [{"state": "success"}]


def _never_succeeded(_id: Any) -> list[Mapping[str, Any]]:
    return [{"state": "failure"}, {"state": "in_progress"}]


# --- what the deployment record is allowed to mean --------------------------


def test_the_newest_successful_deployment_is_the_live_build() -> None:
    record = staleness.newest_successful_deployment([_deployment()], _succeeded)
    assert record.sha == "c" * 40
    assert record.created_at.date().isoformat() == "2026-08-12"
    assert record.deployment_id == 5877359082


def test_the_newest_deployment_wins_over_an_older_one() -> None:
    newer = _deployment(id=2, sha="d" * 40, created_at="2026-09-13T16:04:41Z")
    record = staleness.newest_successful_deployment([_deployment(), newer], _succeeded)
    assert record.sha == "d" * 40


def test_no_deployment_at_all_is_a_refusal_not_a_zero() -> None:
    with pytest.raises(staleness.StalenessUnknown, match="no github-pages deployment"):
        staleness.newest_successful_deployment([], _succeeded)


def test_a_deployment_that_never_succeeded_is_a_refusal() -> None:
    """A deployment row is a request to publish, not a publish.

    `pages.yml` builds a wheel, assembles `site/` and then runs two verification
    steps before `deploy-pages`; a run that dies in any of them still leaves a
    `github-pages` deployment whose newest status is `failure`. Treating that
    commit as live would report the site as fresher than it is, which is the
    one direction of error this file exists to prevent.
    """
    with pytest.raises(staleness.StalenessUnknown, match="successful status"):
        staleness.newest_successful_deployment([_deployment()], _never_succeeded)


def test_a_failed_newer_deployment_does_not_hide_the_successful_older_one() -> None:
    """A failed republish leaves the previous build serving; that is the live one."""
    failed = _deployment(id=9, sha="e" * 40, created_at="2026-09-13T16:04:41Z")

    def statuses(deployment_id: Any) -> list[Mapping[str, Any]]:
        return [{"state": "failure"}] if deployment_id == 9 else [{"state": "success"}]

    record = staleness.newest_successful_deployment([_deployment(), failed], statuses)
    assert record.sha == "c" * 40


def test_a_row_without_a_commit_id_is_not_a_deployment() -> None:
    with pytest.raises(staleness.StalenessUnknown, match="no github-pages deployment"):
        staleness.newest_successful_deployment([_deployment(sha="not-a-sha")], _succeeded)


def test_a_skipped_publisher_leaves_no_deployment_to_read() -> None:
    """The reason this reads deployments and not `pages.yml`'s run history.

    The publisher is path-filtered, so most pushes to `main` produce no run at
    all, and the runs it does produce include `workflow_dispatch` and other
    refs. None of that distinguishes "nothing needed publishing" from "the
    publish never happened". A deployment exists only because bytes were
    uploaded, so the answer here stays the August build rather than moving to
    whenever a workflow last finished.
    """
    runs_that_published_nothing_create_no_deployments: list[Mapping[str, Any]] = [_deployment()]

    record = staleness.newest_successful_deployment(
        runs_that_published_nothing_create_no_deployments, _succeeded
    )

    assert record.created_at.date().isoformat() == "2026-08-12"


# --- which files change what a visitor receives -----------------------------


@pytest.mark.parametrize(
    "path",
    [
        "web/index.html",
        "web/social-card.png",
        "src/ctdl_validate/cli.py",
        "src/ctdl_validate/vendor/ctdl/schema.json",
        "pyproject.toml",
        ".github/workflows/pages.yml",
        "README.md",
        "LICENSE",
    ],
)
def test_the_publishers_inputs_ship_to_visitors(path: str) -> None:
    assert staleness.ships_to_visitors(path)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_deploy_staleness.py",
        "tests/fixtures/clean_framework.json",
        "tools/deploy_staleness.py",
        "tools/action_runner.py",
        "docs/adr/0001-vendored-schemas-zero-runtime-deps.md",
        "docs/findings/2026-08-21-registry-survey-at-scale.json",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "action.yml",
        ".github/workflows/ci.yml",
        "uv.lock",
    ],
)
def test_everything_else_does_not(path: str) -> None:
    assert not staleness.ships_to_visitors(path)


def _publish_filter_paths() -> list[str]:
    """The `paths:` filter on `pages.yml`'s push trigger, read as text.

    A regex rather than a YAML parse because this repository has no YAML
    dependency (`tests/test_secret_scan_tiers.py` reads its workflow the same
    way), and because the entries are what matter, not the document model.
    """
    source = PAGES_WORKFLOW.read_text(encoding="utf-8")
    block = re.search(r"^ *paths:\n((?: *- .*\n)+)", source, re.MULTILINE)
    assert block, "pages.yml no longer declares a paths: filter on its push trigger"
    entries = re.findall(r"^ *- *[\"']?([^\"'\n]+?)[\"']? *$", block.group(1), re.MULTILINE)
    assert entries, "pages.yml's paths: filter parsed as empty"
    return entries


def test_every_path_that_triggers_a_publish_is_visitor_visible() -> None:
    """The filter and the sentinel's list are two statements of one contract.

    `pages.yml`'s `paths:` decides what gets published; `SITE_SOURCE_PREFIXES`
    decides what the sentinel counts as worth publishing. A path added to the
    first and not the second is a change that deploys while the clock says
    nothing has happened -- drift in the direction that keeps the sentinel
    quiet, which is the only direction that matters. This fails the moment the
    two fall out of step.
    """
    for entry in _publish_filter_paths():
        sample = f"{entry[: -len('**')]}some-file" if entry.endswith("/**") else entry
        assert staleness.ships_to_visitors(sample), (
            f"pages.yml publishes on a change to {entry!r}, but deploy_staleness.py "
            f"does not count {sample!r} as visitor-visible"
        )


def test_the_wheels_own_inputs_are_on_the_list_even_though_the_filter_omits_them() -> None:
    """The gap the sentinel can see and the publish filter cannot.

    `pyproject.toml` says `readme = "README.md"`, so setuptools copies the
    README into the built wheel's `.dist-info/METADATA`, and its PEP 639
    default `license-files` glob copies `LICENSE` into
    `.dist-info/licenses/`. That wheel is published from this site's own origin
    and fetched by the page at boot, so both files are bytes a visitor
    receives -- and neither is in `pages.yml`'s `paths:`, so a commit touching
    only them never starts a deploy.

    This test asserts the asymmetry deliberately: on the sentinel's list, off
    the filter. If the filter is ever widened to include them the first
    assertion pair simply stops being interesting, and
    `test_every_path_that_triggers_a_publish_is_visitor_visible` keeps the
    sentinel in step. Widening the filter is a publishing-policy change and an
    owner decision; nothing here makes it.
    """
    entries = _publish_filter_paths()

    for wheel_input in ("README.md", "LICENSE"):
        assert staleness.ships_to_visitors(wheel_input)
        assert wheel_input not in entries


# --- the comparison against main, and every way it can be meaningless -------


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "clone"
    root.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    git("init", "-b", "main")
    git("config", "user.email", "sentinel@example.test")
    git("config", "user.name", "sentinel")
    return root


def _commit(root: Path, path: str, body: str = "x") -> str:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", f"touch {path}"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _repo(tmp_path)
    monkeypatch.setattr(staleness, "REPO_ROOT", root)
    return root


def _record(sha: str, created_at: datetime) -> Any:
    return staleness.DeployRecord(deployment_id=1, sha=sha, created_at=created_at)


def test_it_counts_the_commits_and_names_the_visitor_visible_ones(clone: Path) -> None:
    deployed = _commit(clone, "CHANGELOG.md")
    _commit(clone, "tests/test_x.py")
    _commit(clone, "src/ctdl_validate/checks/ctid.py")
    _commit(clone, "web/index.html")

    drift = staleness.measure(_record(deployed, NOW - timedelta(days=32)), "HEAD", NOW)

    assert drift.commits == 3
    assert drift.visitor_commits == 2
    assert drift.days == 32
    assert drift.overdue


def test_a_readme_only_commit_counts_because_the_wheel_carries_it(clone: Path) -> None:
    """The measured gap, end to end.

    Eight commits on `main` had exactly this shape. The publisher did not fire
    for any of them; the wheel served beside the page nevertheless changed. If
    the sentinel's list were a copy of the filter this would read as zero.
    """
    deployed = _commit(clone, "docs/ROADMAP.md")
    _commit(clone, "README.md")

    drift = staleness.measure(_record(deployed, NOW - timedelta(days=40)), "HEAD", NOW)

    assert drift.commits == 1
    assert drift.visitor_commits == 1
    assert drift.overdue


def test_age_alone_is_not_overdue(clone: Path) -> None:
    """A site nobody has republished because nothing it publishes changed is

    correct, not stale. This repository's publisher is path-filtered, so that
    is its ordinary state rather than an edge case: reporting on age alone
    would make the sentinel fire on every docs-only week, and a sentinel that
    always fires is one nobody reads.
    """
    deployed = _commit(clone, "README.md")
    _commit(clone, "docs/adr/0007-something.md")
    _commit(clone, "tests/test_y.py")

    drift = staleness.measure(_record(deployed, NOW - timedelta(days=200)), "HEAD", NOW)

    assert drift.commits == 2
    assert drift.visitor_commits == 0
    assert not drift.overdue


def test_inside_the_threshold_is_not_overdue(clone: Path) -> None:
    deployed = _commit(clone, "CHANGELOG.md")
    _commit(clone, "web/index.html")

    drift = staleness.measure(_record(deployed, NOW - timedelta(days=3)), "HEAD", NOW)

    assert drift.visitor_commits == 1
    assert not drift.overdue
    assert "Waiting" in staleness.render(drift)


def test_nothing_since_the_deploy_is_up_to_date(clone: Path) -> None:
    deployed = _commit(clone, "web/index.html")

    drift = staleness.measure(_record(deployed, NOW - timedelta(days=1)), "HEAD", NOW)

    assert drift.commits == 0
    assert drift.visitor_commits == 0
    assert not drift.overdue
    assert "Up to date" in staleness.render(drift)


def test_a_commit_this_clone_does_not_have_is_a_refusal(clone: Path) -> None:
    """The shallow-checkout case, which is the one that reports zero silently.

    `git log <absent>..HEAD` on a shallow clone lists nothing, so the site reads
    as current. This is why the sentinel checks out with `fetch-depth: 0`, and
    why the refusal exists rather than trusting that it did.
    """
    _commit(clone, "README.md")

    with pytest.raises(staleness.StalenessUnknown, match="not in this clone"):
        staleness.measure(_record("a" * 40, NOW - timedelta(days=32)), "HEAD", NOW)


def test_a_diverged_history_is_a_refusal(clone: Path) -> None:
    _commit(clone, "README.md")
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "-b", "other"], check=True, capture_output=True
    )
    orphan = _commit(clone, "orphan.txt")
    subprocess.run(["git", "-C", str(clone), "checkout", "main"], check=True, capture_output=True)

    with pytest.raises(staleness.StalenessUnknown, match="not an ancestor"):
        staleness.measure(_record(orphan, NOW - timedelta(days=32)), "HEAD", NOW)


def test_a_malformed_deployed_sha_is_a_refusal(clone: Path) -> None:
    _commit(clone, "README.md")

    with pytest.raises(staleness.StalenessUnknown, match="not a commit id"):
        staleness.measure(_record("nope", NOW), "HEAD", NOW)


# --- the report, and the exit code ------------------------------------------


def test_the_report_states_the_measurement_before_its_verdict(clone: Path) -> None:
    deployed = _commit(clone, "CHANGELOG.md")
    _commit(clone, "src/ctdl_validate/cli.py")
    drift = staleness.measure(_record(deployed, NOW - timedelta(days=32)), "HEAD", NOW)

    report = staleness.render(drift)

    assert deployed[:9] in report
    assert "32 days" in report
    assert "OVERDUE" in report
    assert report.index("Behind by") < report.index("OVERDUE")


def test_the_json_carries_every_number_the_report_states(clone: Path) -> None:
    deployed = _commit(clone, "CHANGELOG.md")
    _commit(clone, "web/index.html")
    drift = staleness.measure(_record(deployed, NOW - timedelta(days=32)), "HEAD", NOW)

    payload = staleness.as_json(drift)

    assert payload["deployed_sha"] == deployed
    assert payload["days"] == 32
    assert payload["commits"] == 1
    assert payload["visitor_commits"] == 1
    assert payload["overdue"] is True


def test_the_cli_refuses_with_a_nonzero_exit_when_it_cannot_measure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2, not 0 with a reassuring report.

    The sentinel workflow turns a measurement into an issue and a refusal into
    a red run, so this exit code is the whole difference between "the site is
    fine" and "nobody can tell".
    """
    payload = tmp_path / "deployments.json"
    payload.write_text('{"deployments": [], "statuses": {}}', encoding="utf-8")

    code = staleness.main(["--deployments-json", str(payload)])

    assert code == 2
    assert "cannot measure" in capsys.readouterr().err


def test_the_cli_reports_and_exits_zero_when_it_can_measure(
    clone: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deployed = _commit(clone, "web/index.html")
    payload = tmp_path / "deployments.json"
    payload.write_text(
        '{"deployments": [{"id": 7, "sha": "' + deployed + '", "environment": "github-pages", '
        '"created_at": "2026-09-13T00:00:00Z"}], "statuses": {"7": [{"state": "success"}]}}',
        encoding="utf-8",
    )

    code = staleness.main(["--deployments-json", str(payload), "--head", "HEAD", "--json"])

    assert code == 0
    assert '"visitor_commits": 0' in capsys.readouterr().out


# --- the workflow that runs it ----------------------------------------------


def _sentinel_workflow_directives() -> str:
    """`deploy-staleness.yml` with its comment lines removed.

    Written after the first draft of the test below passed on the sentinel's
    own prose: the workflow header says, in English, that it holds no
    `pages: write`, and a substring search found that sentence and called it a
    permission. Four conformance checks across this portfolio matched tool
    names in comments the same way and were green on every repository whether
    the tool ran or not. A comment is not a directive; this is the difference,
    and the reason the assertions below are worth anything.
    """
    source = SENTINEL_WORKFLOW.read_text(encoding="utf-8")
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))


def test_the_comment_stripper_actually_removes_the_prose() -> None:
    """The helper above is load-bearing, so it does not get to be untested.

    If it stopped stripping, every assertion in the two tests that follow would
    be searching the header prose instead of the workflow -- passing for the
    wrong reason, which is the failure mode it exists to close.
    """
    directives = _sentinel_workflow_directives()

    assert "It publishes NOTHING" in SENTINEL_WORKFLOW.read_text(encoding="utf-8")
    assert "It publishes NOTHING" not in directives
    assert "issues: write" in directives  # a real directive survives


def test_the_sentinel_checks_out_the_whole_history() -> None:
    """Without `fetch-depth: 0` the deployed commit is absent and the module

    refuses on every run. The refusal is the safety net; this is the thing it
    is a net for.
    """
    assert re.search(r"^ *fetch-depth: 0 *(?:#.*)?$", _sentinel_workflow_directives(), re.MULTILINE)


def test_the_sentinel_holds_no_credential_that_could_publish() -> None:
    """It reports the distance; it never closes it.

    `pages: write` or `id-token: write` here would turn a staleness report into
    a deploy, and whether this site publishes on a given commit is what the
    path filter decides. The sentinel does not get a vote.
    """
    directives = _sentinel_workflow_directives()

    assert "pages: write" not in directives
    assert "id-token: write" not in directives
    assert "deploy-pages" not in directives
    assert "upload-pages-artifact" not in directives
    assert "workflow_run" not in directives
