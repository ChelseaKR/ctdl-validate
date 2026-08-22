# Vendored specification files

These files are unmodified copies of Credential Engine's published CTDL and
CTDL-ASN schema and JSON-LD context documents. They are the only source of
domain, range, inverse, and identifier-coercion rules in this tool. Nothing
is encoded from memory.

All four were retrieved on 2026-08-06 with plain HTTP GET.

| File | Source URL | SHA-256 |
|---|---|---|
| `ctdl/schema.json` | https://credreg.net/ctdl/schema/encoding/json | `a2dd28cb08f9e5e0324fe155e7381c276d70e69cb95521dab120f042cc538776` |
| `ctdl/context.json` | https://credreg.net/ctdl/schema/context/json | `ddb6b4586c38df5fa43aa5f6a558de407dd7acdec9bc1329ce790e164bf40db5` |
| `ctdlasn/schema.json` | https://credreg.net/ctdlasn/schema/encoding/json | `8bacfcec140c03e144903acd04eeacc3f466c2245ca2a1bb703a322981fda0b7` |
| `ctdlasn/context.json` | https://credreg.net/ctdlasn/schema/context/json | `783a5a5e132deb0023f6a4ea5201b9b69e298e6c359c1fd8d3c595392f8e7e72` |

Two prose sources are cited in findings but not vendored (they are HTML pages;
the exact sentences relied on are quoted in `ctdl_validate/rules.py`):

- "About the CTID", https://credreg.net/ctdl/ctid (page dated 5/10/2024,
  retrieved 2026-08-06). Defines the CTID grammar and the CTID-based URI
  structure.
- CTDL "All Schemas Handbook", https://credreg.net/ctdl/handbook (retrieved
  2026-08-06). Defines blank node identifier scope and documents that
  competency frameworks and their competencies are published in the same
  JSON-LD graph.
- RDF Schema 1.1, W3C Recommendation 25 February 2014, section 3.1,
  https://www.w3.org/TR/rdf11-schema/#ch_resource (retrieved 2026-08-22).
  "All things described by RDF are called resources, and are instances of the
  class rdfs:Resource ... This is the class of everything." Relied on to treat
  a `schema:rangeIncludes` naming only `rdfs:Resource` as constraining
  nothing, rather than as a range no CTDL class can satisfy. This is the one
  source that makes a check emit *fewer* findings rather than more, so it
  cites no finding of its own; see `schema.UNIVERSAL_RANGE_TERMS`.
- CTDL QData schema encoding,
  https://credreg.net/qdata/schema/encoding/json (retrieved 2026-08-22). Not
  vendored and not read by the validator: `qdata:` properties reach the tool
  through the CTDL encoding above, which declares them without declaring the
  `qdata:` classes they range on. Consulted once, during the hand
  verification behind
  `docs/findings/2026-08-21-registry-survey-at-scale.md`, to check whether
  `qdata:relevantDataSet` is declared for `ceterms:AggregateDataProfile` in
  its own home encoding. It is not: both encodings declare the same 61-class
  domain and both omit it.

The `extract` subcommand cites four further sources, also quoted in
`ctdl_validate/rules.py` rather than vendored. Nothing about the CTDL rules
depends on them; they define the formats a page publishes in and the manners
a fetcher observes.

- RFC 9309, "Robots Exclusion Protocol",
  https://www.rfc-editor.org/rfc/rfc9309 (retrieved 2026-08-14). Sections
  2.2.1 (the User-Agent line and the product token), 2.3.1.1 through 2.3.1.4
  (obeying parseable rules; five redirects; 4xx unavailable; 5xx complete
  disallow), and 2.5 (the 500 KiB parsing limit). `Crawl-delay` is *not* in
  RFC 9309; where a site declares one, this tool takes the larger of that and
  its own interval, which is recorded in the rule citation itself.
- HTML Living Standard, "Microdata",
  https://html.spec.whatwg.org/multipage/microdata.html (retrieved
  2026-08-14). Sections 5.2.3 (names) and 5.2.4 (values) are implemented case
  for case; 5.2.5 (`itemref`) is deliberately not implemented and is reported.
- RDFa Lite 1.1 (Second Edition), W3C Recommendation 17 March 2015,
  https://www.w3.org/TR/rdfa-lite/ (retrieved 2026-08-14). Defines the five
  attributes the RDFa reader implements, and by exclusion the RDFa 1.1 Core
  attributes it does not.
- schema.org JSON-LD context,
  https://schema.org/docs/jsonldcontext.json (retrieved 2026-08-14). Declares
  `{"@vocab": "http://schema.org/"}`, which is what makes a bare term under a
  schema.org context resolvable. The CTDL context declares the `schema` prefix
  as `https://schema.org/`; both forms are normalized to the CTDL one so the
  two published files agree.

The crosswalk the extractor uses is *not* an additional source. It is read out
of the four vendored files above, from their own `owl:equivalentClass`,
`owl:equivalentProperty`, `rdfs:subClassOf`, and `rdfs:subPropertyOf`
declarations, and `tests/test_extract_crosswalk.py` checks the index against
the files rather than against a copy.

To refresh the vendored files, re-download the four URLs above, update the
hashes and dates here, and re-run the test suite. A schema release can change
which findings this tool emits; that is by design.
