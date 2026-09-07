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

## The library

```python
import ctdl_validate

findings = ctdl_validate.validate_document(payload)
```

| Name | Signature | What it is |
|---|---|---|
| `validate_document` | `(data: Any, resolve: list[Path] \| None = None) -> list[Finding]` | Validate a decoded CTDL JSON-LD document: an object with `@graph`, a single entity, or an array of entities. Raises `graph.DocumentError` for shapes the tool does not read. |
| `Finding` | frozen dataclass | One finding: `code`, `severity`, `entity`, `prop`, `value`, `message`, `rule`. |
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
- `Finding` and `Rule` gain no required field, and lose no field;
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
