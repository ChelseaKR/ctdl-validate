# Security policy

ctdl-validate is a deterministic, offline validator: it reads a JSON file,
checks it against vendored schema snapshots, and prints findings. It makes no
network calls at validation time and has zero runtime dependencies. Security
here is mostly integrity: the tool must not misreport what a payload
contains, and crafted input must not escape the documented failure modes.

## Supported versions

This is a pre-1.0 tool; there is no tagged release yet. Security fixes land
on `main` and, once one exists, the latest tagged release.

| Version | Supported |
| ------- | --------- |
| `main` / latest tag | yes |
| older tags | no |

## Reporting a vulnerability

Preferred: GitHub private vulnerability reporting (this repository's
*Security* tab, "Report a vulnerability"). Alternatively, email
ckellyreif@gmail.com with `ctdl-validate security` in the subject. Expect an
acknowledgement within 72 hours; this is a volunteer project, so please do
not disclose publicly until a fix is available.

Reproduce issues with synthetic payloads like the fixtures under
`tests/fixtures/`; never attach credentials or non-public organizational
data.

## What we consider a vulnerability

In addition to the usual (code execution from input data, secret exposure,
supply-chain compromise), the following are first-class security bugs here:

- Crafted JSON input that crashes outside the documented exit-code contract
  (0 = no ERROR findings, 1 = ERROR findings, 2 = unreadable input), hangs,
  or consumes unbounded resources.
- Any path by which the tool reports a clean pass on a payload that violates
  a rule it claims to check. A false clean report is an integrity bug, not a
  cosmetic one: this tool exists to gate publication.
- Any way to alter the vendored schema snapshots that
  `tests/test_vendor_integrity.py` and the recorded SHA-256 hashes in
  `src/ctdl_validate/vendor/SOURCES.md` would not catch.

## Our commitments

- Dependencies are locked (`uv.lock`) and audited with pip-audit in
  `make verify` and CI, plus Dependabot updates; Semgrep and a full-history
  TruffleHog sweep run in CI; every GitHub Action is pinned to a full commit
  SHA. `make verify` is the same gate locally and in CI.
- Integrity regressions (false clean reports) are fixed with the highest
  priority.
- We credit reporters who want credit, and respect those who want anonymity.
