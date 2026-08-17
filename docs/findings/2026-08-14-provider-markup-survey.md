# What 32 credential provider pages actually publish

Survey run 2026-08-14 with `ctdl-validate extract` at commit-time `main`.
Evidence: [`2026-08-14-provider-markup-survey.json`](2026-08-14-provider-markup-survey.json),
written by [`tools/survey.py`](../../tools/survey.py) from the target list in
[`tools/survey-urls.txt`](../../tools/survey-urls.txt).

The tool was built first and pointed at reality second. This is what came
back. It is not encouraging, and the discouraging part is the finding.

## Headline

| | count | of pages read |
|---|---|---|
| URLs attempted | 32 | |
| Pages read | 29 | |
| Published any structured data (JSON-LD, microdata, or RDFa) | 18 | 62% |
| Published none at all | 11 | 38% |
| Declared a type describing the credential, program, or course itself | 5 | 17% |
| Produced at least one CTDL entity | 11 | 38% |
| Produced a CTDL entity for the thing being offered | 4 | 14% |
| Published a CTID | 0 | 0% |

Three URLs could not be read: one returned HTTP 403 to an identified,
robots-respecting client, and two returned HTTP 404 for URLs a search engine
still lists.

No origin in the sample disallowed this tool. Twenty-six of the 29 pages read
came from origins publishing a `robots.txt`; three came from origins returning
404 for it, which [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) section
2.3.1.3 (retrieved 2026-08-14) treats as permission to proceed.

## Method, and what it can and cannot support

**The sample is purposive, not random.** Thirty-two pages were chosen in
August 2026 to spread across the kinds of organization that publish
credentials: public two-year colleges (10), universities and university
continuing education (4), certification bodies (5), learning platforms (4),
private training providers (4), and employers running their own registered
apprenticeships (5). Each URL is the provider's own page for one credential,
program, or course, never an aggregator's listing. This design supports "here
is what a page of this kind tends to look like". It does not support a
population estimate, and no percentage below should be read as one.

**One page per provider, one moment in time.** A provider whose program page
carries no markup may publish markup elsewhere on its site. Pages change.

**Every page was fetched once, politely.** `robots.txt` first, an identifying
User-Agent naming the tool and linking to its repository, a two-second minimum
interval, one page per host. The posture is
[RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) sections 2.2.1 and 2.3.1
(retrieved 2026-08-14) and is described in the README.

**Only metadata was recorded.** Which formats a page carried, which vocabulary
terms it declared, how many CTDL entities came out, which notes fired, what
the validator then said. No value read from any page is stored in this
repository. The question here is whether pages publish machine-readable
structure, not what anyone's course catalog says.

**What "produced a CTDL entity" means.** The extractor maps a term onto CTDL
only where Credential Engine's published schema encoding declares an
equivalence for it, read from the vendored snapshot retrieved 2026-08-06
([CTDL](https://credreg.net/ctdl/schema/encoding/json),
[CTDL-ASN](https://credreg.net/ctdlasn/schema/encoding/json)). Nothing is
inferred from prose, layout, or a model. So these numbers describe two things
at once: what providers publish, and how far the published crosswalk reaches.
Both are separated out below.

## Finding 1: most program pages publish nothing structured at all

Eleven of 29 pages (38%) carried no JSON-LD, no microdata, and no RDFa. Every
one of them describes its credential in prose and page layout only: headings,
bullet lists, a tuition table, a phone number.

This is the finding that matters most for anyone proposing to extract
credential data at scale, because no amount of parser sophistication changes
it. There is nothing to parse. A deterministic extractor returns an empty
graph and says so; a model would return a plausible credential assembled from
the prose, and nothing downstream could tell the two apart.

The eleven: `durhamtech.edu`, `yccc.edu`, `gatewaycc.edu`, `northampton.edu`,
`snhu.edu`, `distancelearning.txst.edu`, `isc2.org`, `pmi.org`,
`healthpointchc.org`, `wacommunityhealth.org`, `kaiserpermanentejobs.org`.

## Finding 2: where structured data exists, it is mostly page furniture

The 18 pages that published structured data declared 42 distinct types between
them, all in the schema.org namespace. The most common were not about
credentials:

| Type | Pages |
|---|---|
| `schema:BreadcrumbList` / `schema:ListItem` | 12 |
| `schema:Organization` | 9 |
| `schema:ImageObject` | 8 |
| `schema:WebPage` | 6 |
| `schema:WebSite` | 5 |
| `schema:FAQPage` / `schema:Question` / `schema:Answer` | 5 |
| `schema:Course` | 4 |
| `schema:CourseInstance` | 3 |
| `schema:EducationalOccupationalProgram` | 2 |
| `schema:EducationalOccupationalCredential` | 2 |

Breadcrumbs, site search boxes, logos, and FAQ accordions are markup a content
management system emits for search engines. It is real structured data and it
says nothing about the credential on the page.

Seven pages produced a CTDL entity that describes **the provider** and not the
offering: `schema:Organization` maps to `ceterms:Organization` by declared
equivalence, so a college whose CMS emits an Organization block yields a CTDL
extract naming the college, with no credential attached.

## Finding 3: five pages described the offering; four survived the crosswalk

Five of 29 pages (17%) declared a type describing the credential, program, or
course itself:

| Page | Declared | CTDL entities produced |
|---|---|---|
| `wgu.edu` | `schema:Course`, `schema:EducationalOccupationalProgram`, `schema:EducationalOccupationalCredential` | 37 × `ceterms:Course` |
| `coursera.org` (professional certificate) | `schema:Course` | 10 × `ceterms:Course` |
| `coursera.org` (single course) | `schema:Course`, `schema:EducationalOccupationalCredential`, `schema:Syllabus` | `ceterms:Course`, `ceterms:Organization` |
| `springboard.com` | `schema:Course` | `ceterms:Course`, `ceterms:Organization` |
| `pearsonvue.com` | `schema:EducationalOccupationalProgram` | none |

Four pages out of 29 produced a CTDL entity for the thing being offered, and
in every case the CTDL class was `ceterms:Course`.

## Finding 4: the two types that describe a credential most precisely reach nothing

`schema:EducationalOccupationalProgram` and
`schema:EducationalOccupationalCredential` are the schema.org types built for
exactly this domain, and both appeared in the sample. Neither produced a CTDL
entity, because the vendored encodings declare no `owl:equivalentClass` for
either. What they do declare, for the first, is a relation in the other
direction:

> `ceterms:LearningProgram rdfs:subClassOf schema:EducationalOccupationalProgram`
> — [CTDL schema encoding](https://credreg.net/ctdl/schema/encoding/json),
> retrieved 2026-08-06

Every `ceterms:LearningProgram` is a `schema:EducationalOccupationalProgram`.
The reverse does not follow, and a tool that reads it as though it did would
be asserting a CTDL class the page never claimed. The extractor reports the
relation as INFO (`CLASS_RELATED_NOT_EQUIVALENT`, 23 occurrences across the
sample) and emits nothing.

The same shape governs classes. Of schema.org's vocabulary, the snapshot
declares an equivalence for six classes: `Course`, `Organization`,
`ContactPoint`, `Place`, `PostalAddress`, `GeoCoordinates`. So
`schema:CollegeOrUniversity`, which two pages published, maps to nothing:
schema.org declares it a subclass of `schema:Organization`, but resolving that
requires schema.org's own class hierarchy, which this tool deliberately does
not load. `CLASS_NOT_MAPPED` fired 381 times across the sample.

And properties. `PROPERTY_NOT_MAPPED` fired 135 times. On the five pages that
described their offering, the dropped properties include exactly the fields a
credential registry exists to carry:

`schema:educationalCredentialAwarded` (3 pages), `schema:educationalLevel`
(3), `schema:hasCourseInstance` (3), `schema:offers` (3), `schema:timeRequired`
(2), `schema:coursePrerequisites` (1), `schema:financialAidEligible` (1),
`schema:teaches` (1).

That last one is worth stopping on. `schema:teaches` is where a provider
publishes what a learner will be able to do, which is the competency data
CTDL-ASN is built for, and one page in the sample published it.

## Finding 5: a faithful extract can still be an invalid payload

Eleven pages produced CTDL entities. The validator was run on each extract in
the same pass. Nine had no ERROR findings. Two did, and neither was an
extraction mistake:

```
ERROR  DOMAIN_VIOLATION  entity=https://www.coursera.org/learn/foundations-data
    ceterms:image = @type=[ceterms:Course]
    ceterms:image is not declared for class(es) [ceterms:Course].
    rule: ceterms:image declares schema:domainIncludes [... 58 classes ...]
```

`schema:image` is declared equivalent to `ceterms:image`, so a course with a
picture maps through a published equivalence, and the result violates
`ceterms:image`'s declared domain, which does not list `ceterms:Course`. The
same shape appears with addresses: `schema:Organization` and
`schema:PostalAddress` each carry a declared equivalence, and
`schema:address` maps to `ceterms:address`, whose declared range is
`ceterms:Place` rather than `ceterms:PostalAddress`.

A term-by-term crosswalk is not closed under the vocabulary's own domain and
range declarations. Every individual step is licensed by a published
declaration and the composition is still invalid. This is the entire argument
for validating an extract before publishing it, and it is not an argument
anyone has to take on faith: it fell out of running the two halves of the
pipeline on a real page.

Nine extracts also carried `INVERSE_ONE_DIRECTION` (INFO): one direction of a
declared inverse pair with no counterpart, which is what an extract from a
single page necessarily looks like.

## Finding 6: JSON-LD won, and RDFa is gone

| Format | Pages |
|---|---|
| JSON-LD (`<script type="application/ld+json">`) | 15 |
| Microdata | 6 |
| RDFa | 0 |

Three pages carried both JSON-LD and microdata. Not one page in the sample
used RDFa, in any profile.

That result found a bug in this tool's own reporting. The first survey run
flagged all 29 pages as using RDFa 1.1 Core attributes outside the RDFa Lite
profile, because `rel` is both an RDFa attribute and an ordinary HTML one, and
every page on the web has `<link rel="stylesheet">`. The note now fires only
where an element mixes a Core attribute with an RDFa Lite one. Pointing a
checker at reality is how you find out that your report is wrong; a checker
that has only ever seen its own fixtures is a checker you are trusting on
faith.

## Finding 7: nobody publishes a CTID, so nobody can be linked

`CTID_ABSENT` fired on all 11 extracts that produced entities. No page in the
sample carried a Credential Registry identifier in its markup.

That is expected, and it is the reason an extract is a draft rather than a
payload. A CTID is the identifier a Registry resource is known by, and its
CTID-based URI is built from it ([About the CTID](https://credreg.net/ctdl/ctid),
retrieved 2026-08-06). The extractor generates none, ever: a minted identifier
is indistinguishable from a real one downstream, and the difference between
"this credential has no Registry identity yet" and "this credential has one"
is not a difference a tool should invent.

## What this means for extraction

1. **Coverage is bounded by publishers, not by parsers.** Thirty-eight percent
   of these pages publish nothing to parse. The ceiling on deterministic
   extraction from this sample is not a software problem, and pretending
   otherwise is how a pipeline starts producing credentials nobody offered.
2. **The gap between "has structured data" and "has credential data" is the
   real gap.** Sixty-two percent published something; 17% published something
   about the offering. Most of what exists is search-engine furniture.
3. **The published crosswalk reaches six schema.org classes.** A deterministic
   mapper cannot exceed that without either loading schema.org's own class
   hierarchy, which is a real and bounded option, or guessing, which is not.
4. **Whatever produces the extract, something has to check it.** Two of eleven
   extracts here were invalid CTDL, produced entirely from published
   equivalences, with no model and no heuristic anywhere in the path. An
   extractor that is willing to infer will produce more of these, not fewer,
   and will be less able to say which are which.

The honest summary of a deterministic, model-free extractor is: it will
under-report, visibly, every time. The honest summary of the alternative is
that it will over-report, invisibly, some of the time. For a public credential
registry those are not symmetric risks.

## Every page, as it was on 2026-08-14

Grades below are of markup, not of institutions. A page with no structured
data is a page built for people to read, which is what almost every page is
for.

| Category | Host | Formats | Types declared | CTDL entities | CTDL classes |
|---|---|---|---|---|---|
| community college | durhamtech.edu | none | 0 | 0 | |
| community college | elgin.edu | microdata | 1 | 0 | |
| community college | carrollcc.edu | json-ld | 10 | 1 | `ceterms:Organization` |
| community college | ccm.edu | json-ld | 10 | 1 | `ceterms:Organization` |
| community college | yccc.edu | none | 0 | 0 | |
| community college | gatewaycc.edu | none | 0 | 0 | |
| community college | northampton.edu | none | 0 | 0 | |
| community college | wcc.yccd.edu | json-ld + microdata | 11 | 1 | `ceterms:Organization` |
| community college | smccme.edu | json-ld | 9 | 0 | |
| community college | arapahoe.edu | not read (HTTP 403) | | | |
| university | wgu.edu | json-ld + microdata | 9 | 37 | `ceterms:Course` |
| university | snhu.edu | none | 0 | 0 | |
| university | distancelearning.txst.edu | none | 0 | 0 | |
| university | georgiacenter.uga.edu | not read (HTTP 404) | | | |
| certification body | comptia.org | json-ld | 4 | 0 | |
| certification body | isc2.org | none | 0 | 0 | |
| certification body | aws.amazon.com | json-ld | 7 | 0 | |
| certification body | pmi.org | none | 0 | 0 | |
| certification body | pearsonvue.com | json-ld | 1 | 0 | |
| learning platform | coursera.org (certificate) | json-ld | 11 | 10 | `ceterms:Course` |
| learning platform | coursera.org (course) | json-ld | 15 | 3 | `ceterms:Course`, `ceterms:Organization` |
| learning platform | grow.google | json-ld | 9 | 2 | `ceterms:Organization` |
| learning platform | edx.org | not read (HTTP 404) | | | |
| training provider | medcerts.com | microdata | 1 | 0 | |
| training provider | dhcareerinstitute.org | json-ld | 5 | 1 | `ceterms:Organization` |
| training provider | springboard.com | json-ld | 13 | 2 | `ceterms:Course`, `ceterms:Organization` |
| training provider | generalassemb.ly | json-ld | 1 | 1 | `ceterms:Organization` |
| employer apprenticeship | healthpointchc.org | none | 0 | 0 | |
| employer apprenticeship | chas.org | json-ld + microdata | 10 | 11 | `ceterms:Organization`, `schema:QuantitativeValue` |
| employer apprenticeship | fredhutch.org | microdata | 2 | 0 | |
| employer apprenticeship | wacommunityhealth.org | none | 0 | 0 | |
| employer apprenticeship | kaiserpermanentejobs.org | none | 0 | 0 | |

## Reproducing this

```sh
uv sync --locked
uv run python tools/survey.py tools/survey-urls.txt out.json
```

It fetches each page once, honoring `robots.txt`, at two seconds per host. The
numbers will drift as pages change; the JSON alongside this file is the run of
2026-08-14. To inspect a single page:

```sh
ctdl-validate extract <url> --validate
```

## Limits of this survey, stated plainly

- Purposive sample of 32, not random. No population estimate follows from it.
- One page per provider, at one moment.
- US-only, English-only, and weighted toward two occupational areas (welding
  and medical assisting) plus technology certifications.
- Three URLs were not read at all and are excluded from every percentage.
- "Produced a CTDL entity" measures this tool's crosswalk, which is read from
  Credential Engine's published equivalence declarations as of the 2026-08-06
  snapshot, against pages as they were on 2026-08-14. A different snapshot
  moves the number.
- The tool reads RDFa Lite only, and does not follow microdata `itemref`.
  Neither limit bound on this sample: no page used RDFa in any profile, and no
  page used `itemref`.
- The tool does not load schema.org's class hierarchy, so a type that
  schema.org declares a subclass of a mapped class (`CollegeOrUniversity`,
  on two pages) reaches nothing. That is a limit of this tool, not of the
  pages, and it is recorded as an open decision in
  [docs/ROADMAP.md](../ROADMAP.md).
