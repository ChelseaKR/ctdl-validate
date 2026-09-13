"""The full-history secret scan must stay capable of failing on a revoked leak.

Six properties of `.github/workflows/trufflehog.yml` are asserted here. Each one has silently
un-armed a secret scan somewhere in this portfolio, and none of them shows up
as a red build when it breaks -- the job goes green either way, which is the
whole problem.

1. **The result tiers include `unverified`.** TruffleHog sorts a finding into
   `verified` (it authenticated the credential against the live service),
   `unknown` (verification errored) and `unverified` (it asked, and the service
   said no). A credential that leaked and was later *revoked* -- the normal end
   state of a real incident, and the exact case a scheduled full-history sweep
   exists to catch -- answers "no" and is therefore `unverified`. A scan
   configured `--only-verified`, `--results=verified`, or
   `--results=verified,unknown` cannot fail on it. Measured 2026-09-06 on a
   throwaway clone with a real-shaped AWS key planted in one commit and deleted
   in the next: the first three exited 0 reporting nothing; adding `unverified`
   exited 183 with `unverified_secrets: 1`.

2. **No lane uses `--only-verified`.** It is the same hole under a different
   name, and it reads like a deliberate choice rather than a gap.

3. **The action ref and the `version:` input name the same release.** The
   `version:` input is what selects the scanning binary
   (`ghcr.io/trufflesecurity/trufflehog:${VERSION}`); the `uses:` SHA pins only
   the wrapper. Omitting the input entirely is worse than a mismatch, because
   the action then defaults to `latest` and the SHA pin describes nothing that
   scans. Dependabot edits `uses:` and never a `with:` input, so the two drift
   apart and each "upgrade" is a no-op that reads like one.

4. **`fetch-depth: 0` survives on the checkout.** This is a *necessary
   precondition* and not the cause. It decides how much history
   `actions/checkout` puts on DISK; it does not decide what the scanner reads,
   and history that was never fetched cannot be scanned by any invocation. This
   workflow is the proof that it is not sufficient: `fetch-depth: 0` was on the
   checkout the entire time the push and pull_request runs were scanning the
   event's diff under the name "full-history secret scan (all result tiers)".
   What the scanner READS is property 5.

5. **`base: ''` and `head: HEAD` survive on the trufflehog step.** These are the
   cause. The action chooses its range from the triggering event *unless* BASE
   or HEAD is set: `push` gets `--since-commit <event.before> --branch
   <event.after>`, `pull_request` gets `--since-commit <base.sha> --branch
   <head.sha>`, and only `schedule`/`workflow_dispatch` get BASE="" HEAD="",
   the whole history. So without these inputs the weekly cron read everything
   while every merge-gating run read a diff. `head` must be non-empty: the
   action's guard is `if [ -n "$BASE" ] || [ -n "$HEAD" ]`, so `base: ''` on its
   own leaves both empty and falls straight through to the unchanged event
   logic. `HEAD` rather than a branch name because a `pull_request` checkout is
   a detached merge ref with no local branch to name. Measured on a throwaway
   clone with a real-shaped AWS key planted in one commit and deleted in the
   next: the event-derived diff range exited 0 reporting nothing; `--since-commit
   "" --branch HEAD` exited 183.

6. **`path: ./` survives.** It is the step's `working-directory` and the
   directory the action bind-mounts into the scanner container (`-v .:/tmp`),
   so it is what selects the repository root as the thing being scanned.

The pin comment is a YAML comment and so is invisible to a YAML parser: these
assertions read the workflow as text on purpose. Property 5 is the exception
and reads the workflow with comments stripped, because the comment next to
those inputs quotes the very strings it asserts -- four conformance checks in
this portfolio have passed on a tool name that appeared only inside a comment.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "trufflehog.yml"

# The tier a revoked credential lands in. Its absence is the defect.
REQUIRED_RESULT_TIER = "unverified"

_PINNED = re.compile(
    r"trufflesecurity/trufflehog@[0-9a-f]{40}\s*#\s*v(\d+(?:\.\d+)*)",
)
_SELECTED = re.compile(r"^\s*version:\s*[\"']?(\d+(?:\.\d+)*)[\"']?\s*$", re.MULTILINE)
_EXTRA_ARGS = re.compile(r"^\s*extra_args:\s*(.+?)\s*$", re.MULTILINE)
_FETCH_DEPTH_ZERO = re.compile(r"^\s*fetch-depth:\s*0\s*(?:#.*)?$", re.MULTILINE)
_SCAN_PATH = re.compile(r"^\s*path:\s*\./\s*(?:#.*)?$", re.MULTILINE)
# Read against comment-stripped text, so no trailing-comment alternative here.
_BASE_EMPTY = re.compile(r"""^\s*base:\s*(?:''|"")\s*$""", re.MULTILINE)
_HEAD_LITERAL = re.compile(r"^\s*head:\s*HEAD\s*$", re.MULTILINE)


def _strip_yaml_comments(text: str) -> str:
    """Drop YAML comments, honouring quotes so a `#` inside a scalar survives.

    A comment starts at an unquoted `#` that begins the line or follows
    whitespace. Assertions about what the workflow *does* must not be
    satisfiable by a comment that merely talks about it.
    """
    stripped: list[str] = []
    for line in text.splitlines():
        quote = ""
        cut: int | None = None
        for index, char in enumerate(line):
            if quote:
                if char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "#" and (index == 0 or line[index - 1] in " \t"):
                cut = index
                break
        stripped.append(line if cut is None else line[:cut])
    return "\n".join(stripped)


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), (
        f"{WORKFLOW} is missing. If the full-history secret scan was deliberately "
        "removed or replaced, update this test with the replacement rather than "
        "deleting it -- an absent scan must be a decision, not a silence."
    )
    return WORKFLOW.read_text(encoding="utf-8")


def _lanes() -> list[str]:
    lanes = _EXTRA_ARGS.findall(_workflow_text())
    assert lanes, (
        f"no `extra_args:` found in {WORKFLOW.name}; this guard can no longer see "
        "which result tiers the scan reports on."
    )
    return lanes


def test_no_lane_uses_only_verified() -> None:
    for args in _lanes():
        assert "--only-verified" not in args, (
            "`--only-verified` cannot fail on a credential the provider has already "
            "revoked, which is the normal end state of a real leak and the case this "
            f"scan exists for. Offending args: {args!r}"
        )
        assert re.search(r"--results=[\w,]+", args), (
            f"expected an explicit `--results=` tier list, got {args!r}"
        )


def test_some_lane_reports_the_unverified_tier() -> None:
    tier_lists = [
        match.group(1).split(",")
        for args in _lanes()
        if (match := re.search(r"--results=([\w,]+)", args))
    ]
    assert any(REQUIRED_RESULT_TIER in tiers for tiers in tier_lists), (
        f"no lane of this scan reports `{REQUIRED_RESULT_TIER}` results (found "
        f"{tier_lists}), so nothing here can fail on a credential that leaked and "
        "was then revoked. Measured: verified and verified,unknown both exit 0 on a "
        "planted-then-deleted AWS key; adding unverified exits 183."
    )


def test_action_ref_and_version_input_name_the_same_release() -> None:
    text = _workflow_text()
    pinned = _PINNED.findall(text)
    selected = _SELECTED.findall(text)

    assert pinned, (
        "could not read a SHA-pinned trufflesecurity/trufflehog ref and its "
        f"`# vX.Y.Z` comment in {WORKFLOW.name}"
    )
    assert selected, (
        f"no `version:` input on the trufflehog step in {WORKFLOW.name}. Without it "
        'the action defaults to "latest", so the SHA pin above it pins only the '
        "wrapper and not the binary that actually scans."
    )
    assert len(pinned) == len(selected), (
        f"{len(pinned)} pinned trufflehog ref(s) but {len(selected)} `version:` "
        "input(s); every trufflehog step needs its own pinned version"
    )
    for ref_version, input_version in zip(pinned, selected, strict=True):
        assert ref_version == input_version, (
            f"the action is pinned to v{ref_version} but `version: {input_version}` "
            f"is what downloads the scanner, so the scan runs {input_version} and the "
            f"bump to v{ref_version} changed nothing. Set them to the same release."
        )


def test_checkout_keeps_full_history() -> None:
    """`fetch-depth: 0` is the necessary precondition, never the cause.

    Without it actions/checkout fetches a single commit and there is no history
    on disk for any invocation to walk. With it, nothing is guaranteed: this
    workflow carried `fetch-depth: 0` throughout the period its push and
    pull_request runs scanned only the event's diff. The invocation is asserted
    separately, by `test_scan_range_is_the_whole_history_on_every_event`.
    """
    text = _workflow_text()
    assert "actions/checkout@" in text, "the scan no longer checks the repository out"
    assert _FETCH_DEPTH_ZERO.search(text), (
        "`fetch-depth: 0` is missing from the checkout. actions/checkout then fetches "
        "a single commit, so no history reaches the runner and the scan range asserted "
        "by test_scan_range_is_the_whole_history_on_every_event has nothing to walk. "
        "Necessary, not sufficient -- restoring it does not by itself make this a "
        "history scan."
    )


def test_scan_range_is_the_whole_history_on_every_event() -> None:
    """The action must take its explicit-range branch, not its event logic.

    Read against comment-stripped text on purpose: the comment beside these
    inputs quotes `base: ''` and `head: HEAD` while explaining them, and a
    check that matches its own documentation asserts nothing.
    """
    text = _strip_yaml_comments(_workflow_text())

    assert _HEAD_LITERAL.search(text), (
        "`head: HEAD` is missing from the trufflehog step. The action then picks its "
        "range from the triggering event -- `--since-commit <event.before> --branch "
        "<event.after>` on push, the PR's own diff on pull_request -- so every "
        "merge-gating run reads a diff while reporting under a name that says full "
        "history. Only `schedule` and `workflow_dispatch` walk everything without it. "
        "`HEAD` and not a branch name: a pull_request checkout is a detached merge ref."
    )
    assert _BASE_EMPTY.search(text), (
        "`base: ''` is missing from the trufflehog step. The scan must start from the "
        "root commit; any other base makes this a range scan again."
    )
    assert not re.search(r"^\s*base:\s*(?!(?:''|\"\")\s*$)\S", text, re.MULTILINE), (
        "`base:` is set to something other than the empty string, which bounds the "
        "scan below and stops it from reaching the root commit."
    )


def test_scan_walks_the_whole_repository() -> None:
    assert _SCAN_PATH.search(_workflow_text()), (
        "`path: ./` is missing; with path, base and head all unset the action exits "
        'on its own "BASE and HEAD commits are the same" guard having scanned nothing.'
    )
