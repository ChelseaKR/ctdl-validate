# 7. The published playground counts visits with Google Analytics 4

## Status

Accepted, 2026-09-17

## Context

On 2026-09-17 the owner decided that every public site in the portfolio gets
Google Analytics 4, with its privacy pages and claims updated to match. The
playground at https://chelseakr.github.io/ctdl-validate/ is one of those sites.

This page is not an ordinary site to put analytics on. Its argument is that
unpublished credential and competency data never leaves the visitor's machine,
and the Content-Security-Policy was the control that held that: two network
origins, jsDelivr for the runtime and this origin for the wheel. GA4 adds a
second script origin, Google, running in the same page as the payload.

Measured before deciding the shape (2026-09-17, headless Chrome, the real
container for this property, every request to Google recorded and aborted so
nothing reached the property): loading the page at `#p=<payload>`, typing into
the payload box, changing the fragment twice and clicking an outbound link
sent Google one `page_view` whose `dl` was
`https://chelseakr.github.io/ctdl-validate/`, with no fragment and no text from
the page. A fragment-only change sent no further `page_view`.

## Decision

The page loads GA4 from an inline script in the head of `web/index.html`
(`<script id="analytics">`), with the measurement ID `G-QQV001MBJ7` in its
`GA4_ID` constant. `web/privacy.html` carries a byte-for-byte copy, so its
footer offers the same opt-out. The script loads nothing, not even a
`dataLayer`, unless all of these hold:

1. a measurement ID is set;
2. the page is `https://chelseakr.github.io/ctdl-validate/`, so local servers,
   the accessibility and performance gates on 127.0.0.1, and forks never load
   it;
3. the browser sends neither Global Privacy Control nor Do Not Track;
4. the visitor has not opted out with the footer button, which sets
   `ctdl-validate:analytics-opt-out` in localStorage. The key names this
   project because every `chelseakr.github.io` project site shares one origin.

When it loads, it sets Consent Mode v2 defaults (the three ad signals denied
everywhere; `analytics_storage` denied in the EEA, the UK and Switzerland,
where GA sends cookieless pings, and granted elsewhere), turns off Google
signals and ad personalization, and sends `page_location` as the origin and
path only. It does not read the payload, the loaded files or the report.

The Content-Security-Policy gains the minimum GA4 needs with Google signals
off: `www.googletagmanager.com` for the loader, and `*.google-analytics.com`
and `*.analytics.google.com` for measurement. `www.google.com` and
`doubleclick.net` stay out, so anything gtag.js tries to send there is refused.
`tests/test_playground_catalog.py` lists the validator's origins and the
analytics origins separately, so that neither set can grow unnoticed.

The command-line tool, the GitHub Action and the pre-commit hook carry no
analytics. This decision is about the web page only.

## Consequences

- The page now runs a script it did not write. The guard and the CSP limit what
  it can reach, not what it could read if Google changed it; that is the cost
  the owner accepted. The lede's claim is kept to what stays true: nothing the
  visitor validates is uploaded.
- `web/privacy.html` is new, linked from the footer and published by
  `pages.yml`, which fails if the link or the file goes missing.
- `tests/test_playground_analytics.py` runs the script under Node: no ID, the
  wrong host or path, GPC, each form of DNT and the opt-out each load nothing;
  otherwise GA loads with the configuration above. Its negative controls
  remove a guard, assert that the removal landed, and assert that GA then
  loads.
- Owner follow-up in the GA4 property: user-provided data collection off, data
  sharing off, and the Data Processing Terms accepted. None of these has an API.
