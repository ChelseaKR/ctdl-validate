# Public API

Two surfaces are public: the JSON report, and the names exported from
`ctdl_validate`. Everything else — every other module, function, class and
attribute — is internal, and may be renamed or removed in any release without
notice.

`tests/test_public_api.py` pins the names and their signatures, and
`tests/test_report_schema.py` pins the report shape, so changing either is a
deliberate act with a red suite in front of it.

## The report

`ctdl-validate <file> --format json` writes a document that conforms to
[`report.schema.json`](../src/ctdl_validate/report.schema.json), shipped as
package data and printed by `ctdl-validate --report-schema`.

Every report carries `report_schema_version`. It is the version of the report
shape, **not** of the tool, and the two move independently:

| Change | Version part |
|---|---|
| A key is removed or renamed, a type changes, or a key that was always present becomes optional | major |
| A key is added that an existing consumer may ignore | minor |
| Only the schema's own prose changes | patch |

The schema sets `additionalProperties: false` throughout. That is on purpose:
a consumer that validates its input learns about a new key instead of passing
over it.

The playground at `web/index.html` is a second consumer in a second runtime.
It does not build a report of its own — its Download button hands over the
output of the same `render_findings_json`, through Pyodide — so it carries
`report_schema_version` for the same reason the CLI does.

### What a consumer must not do

Do not read a count with a default:

```python
errors = report["summary"].get("ERROR", 0)  # NO
errors = report["summary"]["ERROR"]  # yes
```

Every severity is always present, including the ones that are zero, precisely
so that a missing key is a broken report rather than a count of none. Reading
it with a default turns a contract change into a silently clean gate.
`tools/action_runner.py` did exactly that until 2026-09-06; it now refuses a
report it cannot fully read, and exits 2.

An empty `findings` array means the payload tripped no rule. It does **not**
mean the payload was fully checked: what could not be settled from the payload
alone is reported as `UNVERIFIABLE`, and a consumer that treats an empty list
as a clean bill of health is making the claim the tool declined to make.

Nor does it mean there was anything to check. `document.checked_entities` says
how many entities declared a `ceterms:` or `ceasn:` term — as a `@type` or as a
property key — and **zero means the run had nothing in scope at all**. Until
report schema 1.1.0 a report over `package.json` was byte-identical to a report
over a clean CTDL payload, which is what makes a wide `pre-commit` `files:`
pattern a gate that cannot fail. The exit code is deliberately unchanged: a
document that parses is not a document that could not be read, so exit 2 stays
what it always was.

`document.entities` and `document.checked_entities` are `integer` **or `null`**,
and the two are different facts. `null` means the producer did not measure the
scope — a caller rendering findings it assembled by hand has no document to
measure — and a consumer must not read it as zero. Three states, not two.

### `suggestions` on a finding

Added in report schema **1.2.0**, and a minor bump under the table above: a
key an existing consumer may ignore.

A finding carries `suggestions` only when `--suggest` was passed *and* this
run determined at least one candidate. It is an array of
`{"value", "difference"}` objects: `value` is a string already written
somewhere in the run's own input, `difference` says what a reader would have
to change, in the tool's own vocabulary. Neither field asserts that `value` is
what was meant.

**An empty array is never written.** The schema declares `minItems: 1`, so
"nothing was derived" and "nothing was asked" are both spelled as the absence
of the key rather than one of them being spelled as an empty list. A consumer
must not read the absence of `suggestions` as "there is no correction"; it
means only that this run did not publish one.

Four codes can carry a suggestion, because their correction is fully
determined by the payload rather than searched for:

| Code | The candidate |
|---|---|
| `CTID_UPPERCASE` | the same CTID in lower case |
| `CTID_URI_MISMATCH` | the CTID in this entity's own `@id`; on the `@graph` envelope's own `@id`, the envelope URI re-spelled with the payload's one declared CTID, and only when it declares exactly one |
| `REF_BARE_CTID` | the `@id` of the entity in this run — payload or `--resolve` document — that declares that CTID |
| `ISPARTOF_FRAMEWORK_MISMATCH` | the `@id` of the one `ceasn:CompetencyFramework` in reach |

Where the run holds more than one candidate, or none, nothing is offered.

Three refusals are permanent, and they are written down in
[`suggest.py`](../src/ctdl_validate/suggest.py) with the reason as the value
of `NEVER_SUGGESTED`:

- `CTID_BARE_UUID` and `REF_BARE_UUID` — prefixing the UUID with `ce-` would
  produce a well-formed CTID, which is exactly the problem: it asserts that a
  generated UUID names a Registry resource. A bare UUID is evidence that
  something other than a CTID was written, not evidence about which CTID was
  meant.
- `LANGUAGE_MAP_EXPECTED` — wrapping a literal needs a language tag, and the
  document does not say which one.

And no UNVERIFIABLE finding of any code carries one: UNVERIFIABLE means the
payload alone cannot settle the question, and a candidate computed from that
same payload cannot settle it either.

`--format sarif` carries the same objects in each result's `properties`
bag rather than in SARIF's `fixes`, which wants a source region this tool does
not yet report (issue #66); a `fixes` entry with no region would be a repair a
consumer cannot apply.

## The library

```python
import ctdl_validate

findings = ctdl_validate.validate_document(payload)
```

| Name | Signature | What it is |
|---|---|---|
| `validate_document` | `(data: Any, resolve: list[Path] \| None = None, *, suggest: bool = False) -> list[Finding]` | Validate a decoded CTDL JSON-LD document: an object with `@graph`, a single entity, or an array of entities. Raises `graph.DocumentError` for shapes the tool does not read. `suggest` is additive: it attaches determined re-spellings and changes nothing else. |
| `Finding` | frozen dataclass | One finding: `code`, `severity`, `entity`, `prop`, `value`, `message`, `rule`, and `suggestions` — an empty tuple unless `suggest=True` derived one. |
| `Rule` | frozen dataclass | The published rule a finding is made under: `citation`, `url`, `retrieved`. |
| `Severity` | `StrEnum` | `ERROR`, `WARNING`, `INFO`, `UNVERIFIABLE`. |
| `REPORT_SCHEMA_VERSION` | `str` | The version of the report schema this package writes. |
| `read_report_schema` | `() -> str` | The schema as published, byte for byte. |
| `__version__` | `str` | The tool's version, read back from the installed distribution. |

`validate_document` is what the browser build imports, and naming it here is
what makes that a promise rather than an accident.

### Stability

The package follows Semantic Versioning. Within a major version:

- no name in the table above is removed or renamed;
- no parameter is removed, reordered, or made required;
- `Finding` and `Rule` gain no required field, and lose no field. `Finding`
  may gain a field with a default, as `suggestions` did; a consumer
  constructing one positionally is unaffected, and one reading it by name gets
  a value that is empty until it is asked for;
- `Severity` may gain a member. A consumer that switches on severity should
  have a branch for one it does not know, and must not treat an unknown
  severity as a pass.

A change to any of the above is a major release, listed in the CHANGELOG under
`Changed` or `Removed` before it ships.

### What is deliberately not promised

- The text output. It is for people, and its layout may change in any release;
  parse `--format json`.
- Exit codes are the CLI's contract, not the library's: 0 no ERROR findings,
  1 at least one, 2 the input could not be read. Those are stable.
- Finding `message` strings. The `code` is the stable identifier; the message
  is prose and may be reworded to say the same thing better.
- The `extract` subcommand's envelope, which is a separate shape and is not
  covered by this schema.
