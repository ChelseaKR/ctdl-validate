<!--
Thanks for a PR. CONTRIBUTING.md has the local gate: `uv sync --locked`, then
`make verify`, which runs exactly what CI runs. Delete any section that does not
apply; most PRs are not a new rule.
-->

## What and why

<!-- What changed, and why. Link an issue if one exists. -->

## Checks

- [ ] `make verify` passes locally (ruff lint, ruff format, mypy --strict,
      pytest with branch coverage >= 90%, pip-audit)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if behaviour changed

### If this adds or changes a validation rule

- [ ] A fixture that fails without the change and passes with it, under `tests/fixtures/`
- [ ] The finding cites a real, quotable line from a published source, with the
      date it was retrieved. A rule this tool cannot cite is a rule it should not
      enforce.
- [ ] Severity is justified: `ERROR` only where the spec is unambiguous, and
      `UNVERIFIABLE` rather than a guess where the payload alone cannot settle it

### If this changes CLI output

- [ ] Text and JSON reporters both updated, and the determinism tests still pass.
      Same input, same bytes out, is a promise this tool makes.
