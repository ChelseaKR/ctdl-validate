# ctdl-validate

Deterministic structural validation for [CTDL](https://credreg.net/ctdl/handbook)
JSON-LD payloads, meant to run before publication to the Credential Registry.
Point it at the document you are about to publish; it checks the things a
publisher can get wrong silently: identifier kinds, reference targets, and
class pairings.

No network calls at validation time. No model calls, ever. Same input, same
output, byte for byte. Every finding cites the published rule it came from.

**Status:** Beta. Version `0.1.0`, first signed tag not yet cut. The
rule set, the CLI, and its text and JSON reporters are complete and
covered by tests. Nothing here has been published to the Credential
Registry, and this project is not affiliated with or endorsed by
Credential Engine.

```
$ ctdl-validate my-framework.json
ERROR        CTID_BARE_UUID  entity=$.@graph[0]
    ceterms:ctid = b55f88e3-dfd4-430b-ab47-3e5f9986e1e4
    Bare UUID where a CTID belongs: the ce- prefix is missing. Expected grammar:
    ce- followed by a UUID v4 in 8-4-4-4-12 form, 39 characters, lower case
    hexadecimal, e.g. ce-e8a41a52-6ff6-48f0-9872-889c87b093b7.
    rule: About the CTID, section "CTID Structure": ...
    source: https://credreg.net/ctdl/ctid (retrieved 2026-08-06)
```

Exit code 0 when there are no ERROR findings, 1 when there are, 2 when the
input cannot be read at all. `--format json` produces machine-readable output
with the same content.

## Why this exists

Two publicly reported bug classes on CTDL extraction tooling motivated it:

1. A generated UUID written where a CTID belongs. The ce- prefix and the
   CTID semantics are silently lost; every downstream reference is wrong.
2. A competency extract whose `ceasn:isPartOf` carries an identifier that is
   not its framework's. The extract looks fine locally and is wrong globally.

Both are symptoms of one absence: nothing checks, before an extract is
written, that an identifier is of the expected kind and that a reference
resolves to an entity of the expected class. This tool is that check, as a
standalone gate any publisher can run against their own data.

`tests/fixtures/bug_class_250_bare_uuid_for_ctid.json` and
`tests/fixtures/bug_class_252_wrong_framework_identifier.json` reproduce the
two bug classes generically. They are original test data built for this
repository; nothing is copied from any upstream repository or issue tracker.

## Install and run

Python 3.12+, no runtime dependencies.

```
pip install .
ctdl-validate <file.json>
ctdl-validate <file.json> --format json
```

Input can be a JSON-LD object with `@graph`, a single entity object, or an
array of entities.

## What it checks (v0)

| # | Check | Codes | Rule source |
|---|---|---|---|
| 1 | CTID grammar on `ceterms:ctid`, on `@id`, and on the tail of every Registry resource/graph URI; `ctid` must match the `@id` tail | `CTID_BARE_UUID`, `CTID_MALFORMED`, `CTID_UPPERCASE`, `CTID_NOT_UUIDV4`, `REGISTRY_URI_MALFORMED`, `CTID_URI_MISMATCH` | [About the CTID](https://credreg.net/ctdl/ctid), sections "CTID Structure" and "CTID-Based URI Structure" |
| 2 | Identifier kind: properties the CTDL context declares as `{"@type": "@id"}` with entity ranges must carry IRIs or blank node ids, not bare UUIDs or bare CTIDs | `REF_BARE_UUID`, `REF_BARE_CTID`, `REF_NOT_IRI` | [CTDL context](https://credreg.net/ctdl/schema/context/json), [CTDL-ASN context](https://credreg.net/ctdlasn/schema/context/json) |
| 3 | Reference resolution inside the payload; undefined blank nodes are errors, external IRIs are UNVERIFIABLE | `REF_UNRESOLVED_BNODE`, `REF_OUTSIDE_PAYLOAD` | Handbook, "Blank Node Identifier"; tool policy (below) |
| 4 | Domain and range per `schema:domainIncludes` / `schema:rangeIncludes`, with `rdfs:subClassOf` closure, plus the wrong-framework `isPartOf` pattern | `DOMAIN_VIOLATION`, `RANGE_VIOLATION`, `ISPARTOF_FRAMEWORK_MISMATCH`, `UNKNOWN_CLASS`, `UNKNOWN_PROPERTY`, `RANGE_DOCS_CONFLICT` | [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json), [CTDL-ASN schema encoding](https://credreg.net/ctdlasn/schema/encoding/json) |
| 5 | Inverse consistency for pairs the schema declares with `owl:inverseOf`; both directions present must agree, one direction alone is INFO | `INVERSE_MISMATCH`, `INVERSE_ONE_DIRECTION` | schema encodings, `owl:inverseOf` declarations |

Every finding carries its rule citation, source URL, and retrieval date in
the output itself, in both text and JSON formats.

## Methodology

### Severities, honestly defined

- **ERROR**: the payload violates a cited structural rule. Gates the exit
  code.
- **WARNING**: a cited signal that something is very likely wrong, where the
  rule is not absolute or Registry enforcement of it is not documented.
  Example: a CTID with upper case hex matches the shape but not the published
  examples; the Registry's case handling is not documented, so the tool does
  not claim it will be rejected.
- **INFO**: worth a human look, not a defect. Example: one direction of a
  declared inverse pair without the other.
- **UNVERIFIABLE**: the answer cannot be determined from the payload alone.
  A reference to an entity outside the payload may be perfectly valid; the
  tool does not fetch anything, so it says so instead of guessing. Never
  rendered as a pass or a fail, and never gates the exit code.

The rule behind UNVERIFIABLE is the rule behind the whole tool: never punish
what you cannot see, and never bless it either.

### Break the gate before trusting it

`tests/test_break_the_gate.py` starts from a proven-clean fixture, corrupts
one thing at a time (strips a ce- prefix, points `isPartOf` at the wrong
identifier, breaks an inverse pair, retypes the framework, corrupts a
Registry URI), and asserts each corruption is caught. A gate that has not
been deliberately broken is a gate you are trusting on faith.

### Determinism

`tests/test_determinism.py` asserts byte-identical output for repeated runs,
including across separate interpreter processes. There is nothing to seed:
no sampling, no timestamps, no network.

## Where the rules come from

The schema and context files are vendored unmodified in
`src/ctdl_validate/vendor/`, with source URLs, retrieval dates, and SHA-256
hashes recorded in [SOURCES.md](src/ctdl_validate/vendor/SOURCES.md) and
enforced by `tests/test_vendor_integrity.py`. All four were retrieved
2026-08-06. Prose rules (the CTID grammar, blank node scope, framework
publication) are quoted in `src/ctdl_validate/rules.py` with their page URLs.
No rule is encoded from memory.

## Scope, honestly

Covered in v0: the CTDL (`ceterms:`) and CTDL-ASN (`ceasn:`) vocabularies as
published in the encodings above, which includes the classes and properties
declared there for credentials, organizations, learning opportunities,
competency frameworks, and competencies, plus the SKOS terms those encodings
declare.

Not covered in v0, deliberately:

- Required-property checking (the Registry's Minimum Data and Currency
  Policy). v0 checks what is present, not what is missing.
- Concept scheme membership (`meta:targetScheme` declarations exist for 45
  properties and would support a real check; cut for scope).
- Literal datatype validation beyond the CTID (dates, durations, language
  map shapes).
- Vocabularies beyond CTDL and CTDL-ASN (QData and other profiles).
- Fetching anything. References outside the payload are UNVERIFIABLE by
  design, not a network call away from being verified.

Terms in `ceterms:`/`ceasn:` namespaces that the vendored snapshot does not
declare produce WARNINGs, not ERRORs, because the snapshot can lag a schema
release. Terms in foreign namespaces (schema.org, Dublin Core) are not
CTDL's to judge and are skipped.

## Conflicts found in the published spec

Encoding the rules surfaced three places where Credential Engine's published
sources disagree with each other. The tool handles each explicitly rather
than picking a side silently:

1. `ceasn:isChildOf` does not list `ceasn:CompetencyFramework` in its
   declared range, but the `ceasn:isPartOf` usage note instructs top-level
   statements to use `isChildOf`, and the Handbook's own examples point it at
   the framework. Reported as `RANGE_DOCS_CONFLICT` (INFO), citing both
   sources.
2. `ceasn:hasTopChild` and `ceasn:isTopChildOf` read like an inverse pair
   but carry no `owl:inverseOf` declaration, so the tool does not treat them
   as one (`tests/test_inverses.py::test_undeclared_pairs_are_not_invented`).
3. Some Handbook example URIs omit the ce- prefix inside Registry resource
   URIs, which the About the CTID page (updated 2024) contradicts. The tool
   follows About the CTID and flags such URIs.

## Development

Uses [`uv`](https://docs.astral.sh/uv/) with a locked toolchain
(Python 3.12, see `.python-version`):

```
uv sync --frozen
make verify   # lint + format + strict types + coverage-gated tests + pip-audit
```

`make verify` is the exact gate CI runs; see
[CONTRIBUTING.md](CONTRIBUTING.md) for the individual targets.

## Disclosure

This tool was built quickly with AI assistance (Claude), then reviewed and
tested by a human. The spec research was done first: the CTID grammar, the
context coercions, and every domain/range/inverse declaration were pulled
from credreg.net on 2026-08-06 and vendored before any check was written,
and the fixtures were built to reproduce two real bug classes without
copying any upstream data. Read the findings' citations critically; if a
cited source has changed since retrieval, the vendored snapshot, not this
tool's opinion, is what to update.

## Standards Conformance

This repository is part of a portfolio with shared engineering standards.
Status against each, with an explicit reason wherever a standard does not
apply; the enforcement ledger with targets and owners is
[docs/ROADMAP.md](docs/ROADMAP.md).

| Standard | Status | Evidence |
|---|---|---|
| Responsible-Tech Framework | Applies | [docs/RESPONSIBLE-TECH-AUDITS.md](docs/RESPONSIBLE-TECH-AUDITS.md): the harm surface is false confidence, and the controls (severity contract, break-the-gate suite, cited rules) target it directly. |
| Code Quality | Applies | Floors in `pyproject.toml`: Python >= 3.12, ruff >= 0.15, mypy >= 1.18 (strict), complexity <= 10, branch coverage >= 90%; locked with `uv.lock`; reproduced locally by `make verify`. |
| Security & Supply-Chain | Applies | [SECURITY.md](SECURITY.md); SHA-pinned Actions; Semgrep and full-history TruffleHog in CI; pip-audit in `make verify`; Dependabot; gitleaks in pre-commit. |
| CI/CD | Applies | `ci.yml` runs the same `make verify` gate as local development; trusted-main release workflow (signed tag, re-verified at the tagged commit) wired ahead of the first tag. |
| Observability | N/A (offline single-shot CLI; no service, no telemetry; the deterministic report on stdout is the entire observable surface) | Exit-code contract and JSON output are tested in `tests/test_cli.py`. |
| Accessibility | N/A (no graphical or web surface; plain-text terminal output plus `--format json` for tooling) | Revisit if any web or GUI surface is added. |
| Internationalization | N/A (findings quote English-language spec prose verbatim; see [docs/I18N.md](docs/I18N.md) for the reason and the flip-to-applies trigger) | Multilingual payload *data* validates identically; the declaration covers operator-facing strings only. |
| AI Evaluation | N/A (deterministic rule engine; no model, prompt, retrieval, or LLM call anywhere; AI-assisted authoring is disclosed under [Disclosure](#disclosure)) | Zero runtime dependencies makes the no-model claim mechanically checkable. |
| Documentation | Applies | This README, [CHANGELOG.md](CHANGELOG.md), ADRs in [docs/adr/](docs/adr/), [CITATION.cff](CITATION.cff), [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md). |
| Quality & Metrics | Applies | [docs/ROADMAP.md](docs/ROADMAP.md) names every gate as AUTO, REVIEW, or a reasoned exception; nothing is silently skipped. |
| Release & Versioning | Applies | SemVer; `CHANGELOG.md` kept current; trusted-main signed-tag release workflow. No release has been made yet. |

## License

Apache-2.0. CTDL and CTDL-ASN are Credential Engine's, published under
Creative Commons Attribution 4.0; the vendored files retain their origin in
SOURCES.md. This project is not affiliated with or endorsed by Credential
Engine.
