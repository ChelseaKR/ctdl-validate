# 1. Vendor the CTDL schemas; zero runtime dependencies; no network at validation time

## Status

Accepted

## Context

The tool's value proposition is that a publisher can run it in CI against
data they are about to publish and trust the result. That requires three
properties at once: the result must be reproducible (same input, same
output, on any machine), the rules must be citable (a finding that cannot
point at the published rule it enforces is an opinion), and the gate must
not flake (a validation run that depends on credreg.net being up, or on a
transitive dependency resolving, is a gate teams learn to skip).

The upstream sources (the CTDL and CTDL-ASN schema encodings and JSON-LD
contexts on credreg.net) change over time without archived versioned
snapshots the tool could pin to.

## Decision

- The four upstream files (schema and context for CTDL and CTDL-ASN) are
  vendored unmodified in `src/ctdl_validate/vendor/`, with source URLs,
  retrieval dates, and SHA-256 hashes recorded in `vendor/SOURCES.md` and
  enforced by `tests/test_vendor_integrity.py`. Prose rules that exist only
  as documentation pages (the CTID grammar, blank-node scope) are quoted in
  `src/ctdl_validate/rules.py` with their page URLs and retrieval dates. No
  rule is encoded from memory.
- The package has zero runtime dependencies: standard library only.
- The tool performs no network calls at validation time. References that
  cannot be resolved inside the payload are reported as UNVERIFIABLE, a
  severity that never gates the exit code, rather than being fetched.

## Consequences

- The snapshot can lag an upstream schema release. Terms in `ceterms:` or
  `ceasn:` namespaces that the snapshot does not declare therefore produce
  WARNINGs, not ERRORs. Refreshing the rules means re-vendoring the files
  and re-recording their hashes, a visible, reviewable diff.
- Zero runtime dependencies keeps the supply-chain surface minimal and the
  tool installable anywhere Python 3.12 runs.
- The tool can never claim more than the payload shows: external references
  stay UNVERIFIABLE by design, which is a deliberate limit on the tool's
  authority, not a missing feature.
