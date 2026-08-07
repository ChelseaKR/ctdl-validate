"""The vendored schema files must be exactly the ones SOURCES.md cites.

If a vendored file changes without its recorded hash changing, every
citation in every finding becomes suspect. This gate makes that impossible
to miss.
"""

from __future__ import annotations

import hashlib
import re
from importlib import resources

EXPECTED = {
    "ctdl/schema.json": "a2dd28cb08f9e5e0324fe155e7381c276d70e69cb95521dab120f042cc538776",
    "ctdl/context.json": "ddb6b4586c38df5fa43aa5f6a558de407dd7acdec9bc1329ce790e164bf40db5",
    "ctdlasn/schema.json": "8bacfcec140c03e144903acd04eeacc3f466c2245ca2a1bb703a322981fda0b7",
    "ctdlasn/context.json": "783a5a5e132deb0023f6a4ea5201b9b69e298e6c359c1fd8d3c595392f8e7e72",
}


def _vendor_bytes(relpath: str) -> bytes:
    path = resources.files("ctdl_validate").joinpath("vendor").joinpath(relpath)
    with path.open("rb") as handle:
        data: bytes = handle.read()
    return data


def test_vendored_files_match_recorded_hashes() -> None:
    for relpath, expected in EXPECTED.items():
        actual = hashlib.sha256(_vendor_bytes(relpath)).hexdigest()
        assert actual == expected, f"{relpath} does not match the hash recorded in SOURCES.md"


def test_sources_md_records_the_same_hashes() -> None:
    text = _vendor_bytes("SOURCES.md").decode("utf-8")
    for relpath, expected in EXPECTED.items():
        row = re.search(rf"`{re.escape(relpath)}`.*`([0-9a-f]{{64}})`", text)
        assert row is not None, f"SOURCES.md has no hash row for {relpath}"
        assert row.group(1) == expected
