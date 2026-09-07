# SARIF goldens and the vendored SARIF schema

| File | What it is | Provenance |
|---|---|---|
| `sarif-schema-2.1.0.json` | The OASIS JSON Schema for SARIF 2.1.0 (errata 01), used by `tests/test_sarif.py` to validate every SARIF report offline | `https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json`, retrieved 2026-08-22, SHA-256 `c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e`; its own `id` is `https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json`. OASIS Standards Final Deliverable; copyright OASIS Open, reproduced under the OASIS IPR Policy's permission to copy and distribute. |
| `bug_class_250.sarif.out` | `ctdl-validate tests/fixtures/bug_class_250_bare_uuid_for_ctid.json --format sarif`, run from the repository root: two ERROR findings carrying the CTID citation | Captured by `capture.py` |
| `bug_class_252.sarif.out` | `ctdl-validate tests/fixtures/bug_class_252_wrong_framework_identifier.json --format sarif`, run from the repository root: one ERROR, one WARNING and one UNVERIFIABLE, so all three SARIF levels appear | Captured by `capture.py` |

Regenerate the two goldens with `uv run python tests/sarif/capture.py`, only
from a commit whose SARIF output is the one to preserve, and commit the
change with its reason. The schema file is not regenerated; re-vendor it by
hand if OASIS publishes a new errata, and update the hash above.
